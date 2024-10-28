# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import socket

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from mail_server.rabbitmq import rabbitmq_context
from mail_server.utils.cache import delete_cache
from mail_server.utils.validation import is_valid_host


class MailServerSettings(Document):
	def validate(self) -> None:
		self.validate_root_domain_name()
		self.validate_dns_provider()
		self.validate_spf_host()
		self.validate_default_dkim_key_size()
		self.validate_rmq_host()

	def on_update(self) -> None:
		delete_cache("root_domain_name")

	def validate_root_domain_name(self) -> None:
		"""Validates the Root Domain Name."""

		self.root_domain_name = self.root_domain_name.lower()

		if self.has_value_changed("root_domain_name"):
			frappe.db.set_value("DNS Record", {"is_verified": 1}, "is_verified", 0)

			if self.get_doc_before_save().get("root_domain_name"):
				dns_record_list_link = f'<a href="/app/dns-record">{_("DNS Records")}</a>'
				frappe.msgprint(
					_("Please verify the {0} for the new {1} to ensure proper email authentication.").format(
						dns_record_list_link, frappe.bold("Root Domain Name")
					)
				)

	def validate_dns_provider(self) -> None:
		"""Validates the DNS Provider."""

		if self.dns_provider and not self.dns_provider_token:
			frappe.throw(_("Please set the DNS Provider Token."))

	def validate_spf_host(self) -> None:
		"""Validates the SPF Host."""

		if not self.has_value_changed("spf_host"):
			return

		from mail_server.mail_server.doctype.mail_agent.mail_agent import create_or_update_spf_dns_record

		self.spf_host = self.spf_host.lower()
		if not is_valid_host(self.spf_host):
			msg = _(
				"SPF Host {0} is invalid. It can be alphanumeric but should not contain spaces or special characters, excluding underscores."
			).format(frappe.bold(self.spf_host))
			frappe.throw(msg)

		previous_doc = self.get_doc_before_save()
		if previous_doc and previous_doc.spf_host:
			if spf_dns_record := frappe.db.exists(
				"DNS Record", {"host": previous_doc.spf_host, "type": "TXT"}
			):
				frappe.delete_doc("DNS Record", spf_dns_record, ignore_permissions=True)

		create_or_update_spf_dns_record(self.spf_host)

	def validate_default_dkim_key_size(self) -> None:
		"""Validates the DKIM Key Size."""

		if cint(self.default_dkim_key_size) < 1024:
			frappe.throw(_("DKIM Key Size must be greater than 1024."))

	def validate_rmq_host(self) -> None:
		"""Validates the rmq_host and converts it to lowercase."""

		if self.rmq_host:
			self.rmq_host = self.rmq_host.lower()

	@frappe.whitelist()
	def test_rabbitmq_connection(self) -> None:
		"""Tests the connection to the RabbitMQ server."""

		try:
			with rabbitmq_context():
				frappe.msgprint(_("Connection Successful"), alert=True, indicator="green")
		except socket.gaierror as e:
			frappe.msgprint(e.args[1], _("Connection Failed"), indicator="red")
		except Exception as e:
			messages = []
			for error in e.args:
				if not isinstance(error, str):
					error = error.exception

				messages.append(f"{frappe.bold(e.__class__.__name__)}: {error}")

			as_list = True
			if len(messages) == 1:
				messages = messages[0]
				as_list = False

			frappe.msgprint(messages, _("Connection Failed"), as_list=as_list, indicator="red")


def validate_mail_server_settings() -> None:
	"""Validates the mandatory fields in the Mail Server Settings."""

	ms_settings = frappe.get_doc("Mail Server Settings")
	mandatory_fields = [
		"root_domain_name",
		"spf_host",
		"default_dkim_key_size",
		"default_ttl",
	]

	for field in mandatory_fields:
		if not ms_settings.get(field):
			field_label = frappe.get_meta("Mail Server Settings").get_label(field)
			frappe.throw(
				_("Please set the {0} in the Mail Server Settings.").format(frappe.bold(field_label))
			)
