# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from mail_server.mail_server.doctype.dns_record.dns_record import create_or_update_dns_record
from mail_server.mail_server.doctype.mail_server_settings.mail_server_settings import (
	validate_mail_server_settings,
)
from mail_server.utils import get_dns_record


class MailAgent(Document):
	def autoname(self) -> None:
		self.agent = self.agent.lower()
		self.name = self.agent

	def validate(self) -> None:
		if self.is_new():
			validate_mail_server_settings()

		self.validate_api_key()
		self.validate_agent()

	def on_update(self) -> None:
		if self.enable_outbound:
			create_or_update_spf_dns_record()

	def on_trash(self) -> None:
		if frappe.session.user != "Administrator":
			frappe.throw(_("Only Administrator can delete Mail Agent."))

		if self.enable_outbound:
			self.db_set("enabled", 0)
			create_or_update_spf_dns_record()

	def validate_api_key(self) -> None:
		"""Validates the API Key or Username and Password."""

		if not self.api_key:
			if not self.username or not self.password:
				frappe.throw(_("API Key or Username and Password is required."))

	def validate_agent(self) -> None:
		"""Validates the agent and fetches the IP addresses."""

		if self.is_new() and frappe.db.exists("Mail Agent", self.agent):
			frappe.throw(_("Mail Agent {0} already exists.").format(frappe.bold(self.agent)))

		ipv4 = get_dns_record(self.agent, "A")
		ipv6 = get_dns_record(self.agent, "AAAA")

		self.ipv4 = ipv4[0].address if ipv4 else None
		self.ipv6 = ipv6[0].address if ipv6 else None


def create_or_update_spf_dns_record(spf_host: str | None = None) -> None:
	"""Refreshes the SPF DNS Record."""

	ms_settings = frappe.get_single("Mail Server Settings")
	spf_host = spf_host or ms_settings.spf_host
	outbound_agents = frappe.db.get_all(
		"Mail Agent",
		filters={"enabled": 1, "enable_outbound": 1},
		pluck="agent",
		order_by="agent asc",
	)

	if not outbound_agents:
		if spf_dns_record := frappe.db.exists("DNS Record", {"host": spf_host, "type": "TXT"}):
			frappe.delete_doc("DNS Record", spf_dns_record, ignore_permissions=True)
			return

	outbound_agents = [f"a:{outbound_agent}" for outbound_agent in outbound_agents]
	create_or_update_dns_record(
		host=spf_host,
		type="TXT",
		value=f"v=spf1 {' '.join(outbound_agents)} ~all",
		ttl=ms_settings.default_ttl,
		category="Server Record",
	)
