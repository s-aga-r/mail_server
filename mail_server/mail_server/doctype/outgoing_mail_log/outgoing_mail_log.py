# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from email import message_from_string

import frappe
import requests
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint
from uuid_utils import uuid7

from mail_server.mail_server.doctype.spam_check_log.spam_check_log import create_spam_check_log
from mail_server.utils import convert_to_utc
from mail_server.utils.cache import get_user_owned_domains
from mail_server.utils.user import is_system_manager


class OutgoingMailLog(Document):
	def autoname(self) -> None:
		self.name = str(uuid7())

	def validate(self) -> None:
		self.validate_status()
		self.set_ip_address()
		self.validate_message()
		self.validate_domain_name()

	def after_insert(self) -> None:
		frappe.enqueue_doc(
			self.doctype, self.name, "check_for_spam", queue="short", enqueue_after_commit=True
		)

	def validate_status(self) -> None:
		"""Set status to `In Progress` if not set."""

		if not self.status:
			self.status = "In Progress"

	def set_ip_address(self) -> None:
		"""Set IP Address to current request IP."""

		self.ip_address = frappe.local.request_ip

	def validate_message(self) -> None:
		"""Validate message and extract domain name."""

		message = message_from_string(self.message)
		self.domain_name = message["From"].split("@")[1].replace(">", "")
		self.message_id = message["Message-ID"]
		self.message_size = len(self.message)

		if not message["DKIM-Signature"]:
			frappe.throw(_("Message does not contain DKIM Signature."))

	def validate_domain_name(self) -> None:
		"""Validate domain name and check if it is verified."""

		user = frappe.session.user
		if is_system_manager(user):
			return

		if self.domain_name in get_user_owned_domains(user):
			if frappe.get_cached_value("Mail Domain Registry", self.domain_name, "is_verified"):
				return

			frappe.throw(_("Domain {0} is not verified.").format(self.domain_name))

		frappe.throw(
			_("You are not authorized to send emails from domain {0}.").format(self.domain_name),
			frappe.PermissionError,
		)

	def check_for_spam(self) -> None:
		"""Check if the email is spam and set status accordingly."""

		ms_settings = frappe.get_cached_doc("Mail Server Settings")

		if ms_settings.enable_spam_detection and ms_settings.enable_spam_detection_for_outbound:
			log = create_spam_check_log(self.message)
			kwargs = {
				"spam_score": log.spam_score,
				"spam_check_response": log.spamd_response,
				"is_spam": cint(log.spam_score > ms_settings.outbound_spam_threshold),
			}
			if kwargs["is_spam"] and ms_settings.block_outbound_spam:
				kwargs.update(
					{
						"status": "Blocked",
						"error_message": _(
							"This email was blocked because it was flagged as spam by our system. The spam score exceeded the allowed threshold. Please review the content of your email and try removing any suspicious links or attachments, or contact support for further assistance."
						),
					}
				)
			elif "DKIM_INVALID" in kwargs["spam_check_response"]:
				kwargs.update({"status": "Blocked", "error_message": _("DKIM Signature is invalid.")})
			else:
				kwargs["status"] = "Accepted"

			self._db_set(notify_update=True, **kwargs)

			if kwargs["status"] == "Blocked":
				self.update_delivery_status_in_mail_client()
		else:
			self._db_set(status="Accepted", notify_update=True)

	def update_delivery_status_in_mail_client(self) -> None:
		"""Update delivery status in Mail Client."""

		if host := frappe.get_cached_value("Mail Domain Registry", self.domain_name, "mail_client_host"):
			data = self.get_delivery_status()
			try:
				requests.post(f"{host}/api/method/mail.api.outbound.update_delivery_status", json=data)
			except Exception:
				frappe.log_error(
					title="Mail Client Delivery Status Update Failed", message=frappe.get_traceback()
				)

	def get_delivery_status(self) -> dict:
		"""Returns the delivery status of the outgoing mail."""

		status = "Queued"
		if self.status in ["Blocked", "Deferred", "Bounced", "Partially Sent", "Sent"]:
			status = self.status

		return {
			"status": status,
			"token": self.name,
			"error_message": self.error_message,
			"outgoing_mail": self.outgoing_mail,
			"recipients": [
				{
					"email": rcpt.email,
					"status": rcpt.status,
					"action_at": str(convert_to_utc(rcpt.action_at)),
					"retries": rcpt.retries,
					"response": rcpt.response,
				}
				for rcpt in self.recipients
				if rcpt.status
			],
		}

	def _db_set(
		self,
		update_modified: bool = True,
		commit: bool = False,
		notify_update: bool = False,
		**kwargs,
	) -> None:
		"""Updates the document with the given key-value pairs."""

		self.db_set(kwargs, update_modified=update_modified, commit=commit)

		if notify_update:
			self.notify_update()


def create_outgoing_mail_log(
	outgoing_mail: str, recipients: str | list[str], message: str
) -> "OutgoingMailLog":
	"""Create Outgoing Mail Log."""

	log = frappe.new_doc("Outgoing Mail Log")
	log.outgoing_mail = outgoing_mail

	if isinstance(recipients, str):
		recipients = recipients.split(",")

	for rcpt in list(set(recipients)):
		log.append("recipients", {"email": rcpt})

	log.message = message
	log.insert(ignore_permissions=True)
	return log
