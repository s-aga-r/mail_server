# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from mail_server.mail_server.doctype.dkim_key.dkim_key import (
	create_dkim_key,
	get_dkim_selector_and_private_key,
)
from mail_server.mail_server.doctype.mail_server_settings.mail_server_settings import (
	validate_mail_server_settings,
)


class MailDomainRegistry(Document):
	def validate(self) -> None:
		self.validate_domain_name()
		self.validate_is_verified()
		self.validate_is_subdomain()
		self.validate_domain_owner()
		self.validate_dkim_key_size()

		if self.is_new() or self.has_value_changed("dkim_key_size"):
			validate_mail_server_settings()
			create_dkim_key(self.domain_name, cint(self.dkim_key_size))

	def validate_domain_name(self) -> None:
		"""Validates Domain Name"""

		if not self.domain_name:
			frappe.throw(_("Domain Name is mandatory."))

		if self.domain_name.strip().lower() != self.domain_name:
			frappe.throw(_("Domain Name should be in lowercase."))

	def validate_is_verified(self) -> None:
		"""Validates Is Verified"""

		if not self.enabled:
			self.is_verified = 0

	def validate_is_subdomain(self) -> None:
		"""Validates Is Subdomain"""

		if len(self.domain_name.split(".")) > 2:
			self.is_subdomain = 1

	def validate_domain_owner(self) -> None:
		"""Validates Domain Owner"""

		if not self.domain_owner:
			self.domain_owner = frappe.session.user

	def validate_dkim_key_size(self) -> None:
		"""Validates DKIM Key Size"""

		if self.dkim_key_size:
			if cint(self.dkim_key_size) < 1024:
				frappe.throw(_("DKIM Key Size must be greater than 1024."))
		else:
			self.dkim_key_size = frappe.db.get_single_value(
				"Mail Server Settings", "default_dkim_key_size", cache=True
			)

	def get_dns_records(self) -> list[dict]:
		"""Returns DNS Records"""

		records = []
		ms_settings = frappe.get_cached_doc("Mail Server Settings")

		# SPF Record
		records.append(
			{
				"category": "Sending Record",
				"type": "TXT",
				"host": self.domain_name,
				"value": f"v=spf1 include:{ms_settings.spf_host}.{ms_settings.root_domain_name} ~all",
				"ttl": ms_settings.default_ttl,
			},
		)

		# DMARC Record
		dmarc_mailbox = f"dmarc@{ms_settings.root_domain_name}"
		dmarc_value = (
			f"v=DMARC1; p=reject; rua=mailto:{dmarc_mailbox}; ruf=mailto:{dmarc_mailbox}; fo=1; adkim=s; aspf=s; pct=100;"
			if self.domain_name == ms_settings.root_domain_name
			else f"v=DMARC1; p=reject; rua=mailto:{dmarc_mailbox}; ruf=mailto:{dmarc_mailbox}; fo=1; adkim=r; aspf=r; pct=100;"
		)
		records.append(
			{
				"category": "Sending Record",
				"type": "TXT",
				"host": f"_dmarc.{self.domain_name}",
				"value": dmarc_value,
				"ttl": ms_settings.default_ttl,
			}
		)

		# MX Record(s)
		if inbound_agents := frappe.db.get_all(
			"Mail Agent",
			filters={"enabled": 1, "type": "Inbound"},
			fields=["agent", "priority"],
			order_by="priority asc",
		):
			for inbound_agent in inbound_agents:
				records.append(
					{
						"category": "Receiving Record",
						"type": "MX",
						"host": self.domain_name,
						"value": f"{inbound_agent.agent.split(':')[0]}.",
						"priority": inbound_agent.priority,
						"ttl": ms_settings.default_ttl,
					}
				)

		return records

	def get_dkim_selector_and_private_key(self) -> tuple[str, str]:
		"""Returns DKIM Selector and Private Key"""

		return get_dkim_selector_and_private_key(self.domain_name, raise_exception=True)
