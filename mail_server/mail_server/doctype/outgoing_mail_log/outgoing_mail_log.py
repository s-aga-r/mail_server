# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import json

import frappe
import requests
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, now, time_diff_in_seconds
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
		self.validate_priority()

	def after_insert(self) -> None:
		self.enqueue_check_for_spam()

	def validate_status(self) -> None:
		"""Set status to `In Progress` if not set."""

		if not self.status:
			self.status = "In Progress"

	def set_ip_address(self) -> None:
		"""Set IP Address to current request IP."""

		self.ip_address = frappe.local.request_ip

	def validate_message(self) -> None:
		"""Validate message and extract domain name."""

		from mail_server.utils.email_parser import EmailParser

		parser = EmailParser(self.message)
		parser.update_header("X-FM-OML", self.name)
		self.priority = cint(parser.get_header("X-Priority"))
		self.created_at = parser.get_date()
		self.message_id = parser.get_message_id()
		self.received_at = now()
		self.domain_name = parser.get_sender()[1].split("@")[1]
		self.message_size = parser.get_size()
		self.is_newsletter = cint(parser.get_header("X-Newsletter"))
		self.received_after = time_diff_in_seconds(self.received_at, self.created_at)
		self.message = parser.get_message()

		if not parser.get_header("DKIM-Signature"):
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

	def validate_priority(self) -> None:
		"""Validate priority and set it to a value between 0 and 3."""

		self.priority = min(max(int(self.priority), 0), 3)

	def enqueue_check_for_spam(self) -> None:
		"""Enqueue spam check if spam detection is enabled."""

		if is_spam_detection_enabled_for_outbound():
			frappe.enqueue_doc(
				self.doctype, self.name, "check_for_spam", queue="short", enqueue_after_commit=True
			)
		else:
			processed_at = now()
			processed_after = time_diff_in_seconds(processed_at, self.received_at)
			self._db_set(
				status="Accepted",
				processed_at=processed_at,
				processed_after=processed_after,
				notify_update=True,
			)

			if self.priority == 3:
				self.push_to_queue()

	def check_for_spam(self) -> None:
		"""Check if the email is spam and set status accordingly."""

		if is_spam_detection_enabled_for_outbound():
			log = create_spam_check_log(self.message)
			ms_settings = frappe.get_cached_doc("Mail Server Settings")
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

			kwargs["processed_at"] = now()
			kwargs["processed_after"] = time_diff_in_seconds(kwargs["processed_at"], self.received_at)
			self._db_set(notify_update=True, **kwargs)

			if kwargs["status"] == "Blocked":
				self.update_delivery_status_in_mail_client()
		else:
			processed_at = now()
			processed_after = time_diff_in_seconds(processed_at, self.received_at)
			self._db_set(
				status="Accepted",
				processed_at=processed_at,
				processed_after=processed_after,
				notify_update=True,
			)

		if self.status == "Accepted" and self.priority == 3:
			self.push_to_queue()

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

	@frappe.whitelist()
	def retry_failed(self) -> None:
		"""Retries failed email."""

		if self.status == "Failed":
			self._db_set(status="Accepted", error_log=None, error_message=None, commit=True)
			self.push_to_queue()

	@frappe.whitelist()
	def retry_bounced(self) -> None:
		"""Retries bounced email."""

		if not is_system_manager(frappe.session.user):
			frappe.throw(_("Only System Manager can retry bounced mail."))

		if self.status == "Bounced":
			self._db_set(status="Accepted", error_log=None, error_message=None, commit=True)
			self.push_to_queue()

	@frappe.whitelist()
	def push_to_queue(self) -> None:
		"""Pushes the email to the queue for sending."""

		if not frappe.flags.force_push_to_queue:
			self.load_from_db()

			# Ensure the document is "Accepted"
			if self.status != "Accepted":
				return

		from mail_server.rabbitmq import OUTGOING_MAIL_QUEUE, rabbitmq_context

		self._db_set(
			status="Queuing (RMQ)",
			notify_update=False,
			commit=True,
		)

		recipients = [r.email for r in self.recipients]
		data = {
			"outgoing_mail_log": self.name,
			"recipients": recipients,
			"message": self.message,
		}

		try:
			with rabbitmq_context() as rmq:
				rmq.declare_queue(OUTGOING_MAIL_QUEUE, max_priority=3)
				rmq.publish(OUTGOING_MAIL_QUEUE, json.dumps(data), priority=3)

			queued_at = now()
			queued_after = time_diff_in_seconds(queued_at, self.processed_at)
			self._db_set(
				status="Queued (RMQ)",
				queued_at=queued_at,
				queued_after=queued_after,
				notify_update=False,
				commit=True,
			)
		except Exception:
			error_log = frappe.get_traceback(with_context=False)
			self._db_set(status="Failed", error_log=error_log, commit=True)


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


def is_spam_detection_enabled_for_outbound() -> bool:
	"""Returns True if spam detection is enabled for outbound emails else False."""

	ms_settings = frappe.get_cached_doc("Mail Server Settings")
	return ms_settings.enable_spam_detection and ms_settings.enable_spam_detection_for_outbound


def push_emails_to_queue() -> None:
	"""Pushes emails to the queue for sending."""

	import time

	from frappe.query_builder.functions import GroupConcat
	from pypika import Order

	from mail_server.rabbitmq import OUTGOING_MAIL_QUEUE, rabbitmq_context
	from mail_server.utils.cache import get_root_domain_name

	batch_size = 1000
	max_failures = 3
	total_failures = 0
	root_domain_name = get_root_domain_name()

	while total_failures < max_failures:
		OML = frappe.qb.DocType("Outgoing Mail Log")
		MLR = frappe.qb.DocType("Mail Log Recipient")
		mails = (
			frappe.qb.from_(OML)
			.join(MLR)
			.on(OML.name == MLR.parent)
			.select(
				OML.name,
				OML.message,
				OML.priority,
				OML.domain_name,
				GroupConcat(MLR.email).as_("recipients"),
			)
			.where(OML.status == "Accepted")
			.groupby(OML.name)
			.orderby(OML.priority, order=Order.desc)
			.orderby(OML.received_at)
			.limit(batch_size)
		).run(as_dict=True, as_iterator=False)

		if not mails:
			break

		try:
			mail_list = [mail["name"] for mail in mails]
			(frappe.qb.update(OML).set(OML.status, "Queuing (RMQ)").where(OML.name.isin(mail_list))).run()
			frappe.db.commit()

			with rabbitmq_context() as rmq:
				rmq.declare_queue(OUTGOING_MAIL_QUEUE, max_priority=3)

				for mail in mails:
					if mail["domain_name"] == root_domain_name:
						mail["priority"] = max(mail["priority"], 2)

					data = {
						"outgoing_mail_log": mail["name"],
						"recipients": mail["recipients"].split(","),
						"message": mail["message"],
					}
					rmq.publish(OUTGOING_MAIL_QUEUE, json.dumps(data), priority=mail["priority"])

			frappe.db.sql(
				"""
				UPDATE `tabOutgoing Mail Log`
				SET
					status = %s,
					queued_at = %s,
					queued_after = TIMESTAMPDIFF(SECOND, `processed_at`, `queued_at`)
				WHERE
					status = %s AND
					name IN %s
				""",
				("Queued (RMQ)", now(), "Queuing (RMQ)", tuple(mail_list)),
			)

		except Exception:
			total_failures += 1
			error_log = frappe.get_traceback(with_context=False)
			frappe.log_error(title="Push Emails to Queue", message=error_log)

			(
				frappe.qb.update(OML)
				.set(OML.status, "Failed")
				.set(OML.error_log, error_log)
				.where((OML.name.isin(mail_list)) & (OML.status == "Queuing (RMQ)"))
			).run()

			if total_failures < max_failures:
				time.sleep(2**total_failures)
