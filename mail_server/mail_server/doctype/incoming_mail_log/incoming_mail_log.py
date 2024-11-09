# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import time

import frappe
import requests
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, now, time_diff_in_seconds, validate_email_address
from uuid_utils import uuid7

from mail_server.mail_server.doctype.spam_check_log.spam_check_log import create_spam_check_log
from mail_server.rabbitmq import INCOMING_MAIL_QUEUE, rabbitmq_context
from mail_server.utils import convert_to_utc, parse_iso_datetime
from mail_server.utils.email_parser import EmailParser, extract_ip_and_host
from mail_server.utils.validation import is_domain_registry_exists


class IncomingMailLog(Document):
	def autoname(self) -> None:
		self.name = str(uuid7())

	def validate(self) -> None:
		self.validate_status()
		self.validate_fetched_at()

	def after_insert(self) -> None:
		self.enqueue_process_message()

	def validate_status(self) -> None:
		"""Set status to `In Progress` if not set."""

		if not self.status:
			self.status = "In Progress"

	def validate_fetched_at(self) -> None:
		"""Set `fetched_at` to current datetime if not set."""

		if not self.fetched_at:
			self.fetched_at = now()

	def enqueue_process_message(self) -> None:
		"""Enqueue `process_message` method to process the email message."""

		frappe.enqueue_doc(
			self.doctype, self.name, "process_message", queue="short", enqueue_after_commit=True
		)

	def process_message(self) -> None:
		"""Process the email message and update the log."""

		parser = EmailParser(self.message)
		self.display_name, self.sender = parser.get_sender()
		self.receiver = parser.get_header("Delivered-To")
		self.message_id = parser.get_message_id()
		self.created_at = parser.get_date()
		self.message_size = parser.get_size()
		self.from_ip, self.from_host = extract_ip_and_host(parser.get_header("Received"))
		self.received_at = parse_iso_datetime(parser.get_header("Received-At"))

		if self.created_at:
			self.received_after = time_diff_in_seconds(self.received_at, self.created_at)

		self.fetched_after = time_diff_in_seconds(self.fetched_at, self.received_at)

		for key, value in parser.get_authentication_results().items():
			setattr(self, key, value)

		if (validate_email_address(self.sender) == self.sender) and (
			validate_email_address(self.receiver) == self.receiver
		):
			self.domain_name = self.receiver.split("@")[1]
			if is_domain_registry_exists(self.domain_name, exclude_disabled=False):
				if is_spam_detection_enabled_for_inbound():
					log = create_spam_check_log(self.message)
					ms_settings = frappe.get_cached_doc("Mail Server Settings")
					self.spam_score = log.spam_score
					self.spam_check_response = log.spamd_response
					self.is_spam = cint(log.spam_score > ms_settings.inbound_spam_threshold)

					if self.is_spam and ms_settings.reject_inbound_spam:
						self.is_rejected = 1
						self.rejection_message = _("Email is marked as spam.")

			else:
				self.is_rejected = 1
				self.rejection_message = _("Domain is not registered.")

		else:
			self.is_rejected = 1
			self.rejection_message = _("Invalid sender or receiver email address.")

		self.status = "Rejected" if self.is_rejected else "Accepted"
		self.processed_at = now()
		self.processed_after = time_diff_in_seconds(self.processed_at, self.fetched_at)
		self.db_update()

		if self.status == "Accepted":
			self.deliver_email_to_mail_client()

	def deliver_email_to_mail_client(self):
		"""Deliver email to mail client."""

		domain_registry = frappe.get_cached_doc("Mail Domain Registry", self.domain_name)
		if domain_registry.mail_client_host:
			if not domain_registry.inbound_token:
				return

			host = domain_registry.mail_client_host
			data = {
				"incoming_mail_log": self.name,
				"is_spam": self.is_spam,
				"message": self.message,
				"domain_name": self.domain_name,
				"processed_at": str(convert_to_utc(self.processed_at)),
				"inbound_token": domain_registry.get_password("inbound_token"),
			}

			try:
				requests.post(f"{host}/api/method/mail_client.api.webhook.receive_email", json=data)
			except Exception:
				frappe.log_error(title="Mail Client Email Delivery Failed", message=frappe.get_traceback())

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


def create_incoming_mail_log(agent: str, message: str) -> "IncomingMailLog":
	"""Create Incoming Mail Log."""

	log = frappe.new_doc("Incoming Mail Log")
	log.agent = agent
	log.message = message
	log.insert(ignore_permissions=True)
	return log


def fetch_emails_from_queue() -> None:
	"""Fetch emails from queue and create Incoming Mail Log."""

	max_failures = 3
	total_failures = 0

	try:
		with rabbitmq_context() as rmq:
			rmq.declare_queue(INCOMING_MAIL_QUEUE)

			while True:
				result = rmq.basic_get(INCOMING_MAIL_QUEUE)

				if not result:
					break

				method, properties, body = result
				if body:
					message = body.decode("utf-8")
					create_incoming_mail_log(properties.app_id, message)

				rmq.channel.basic_ack(delivery_tag=method.delivery_tag)

	except Exception:
		total_failures += 1
		error_log = frappe.get_traceback(with_context=False)
		frappe.log_error(title="Fetch Emails from Queue", message=error_log)

		if total_failures < max_failures:
			time.sleep(2**total_failures)


def is_spam_detection_enabled_for_inbound() -> bool:
	"""Returns True if spam detection is enabled for inbound emails else False."""

	ms_settings = frappe.get_cached_doc("Mail Server Settings")
	return ms_settings.enable_spam_detection and ms_settings.enable_spam_detection_for_inbound
