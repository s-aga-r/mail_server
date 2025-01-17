# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from mail_server.utils import get_dns_record


class MailAgentGroup(Document):
	def autoname(self) -> None:
		self.agent_group = self.agent_group.lower()
		self.name = self.agent_group

	def validate(self) -> None:
		self.validate_agent_group()
		self.validate_priority()

	def validate_agent_group(self) -> None:
		"""Validates the agent group and fetches the IP addresses."""

		if self.is_new() and frappe.db.exists("Mail Agent Group", self.agent_group):
			frappe.throw(_("Mail Agent Group {0} already exists.").format(frappe.bold(self.agent_group)))

		ipv4 = get_dns_record(self.agent_group, "A")
		ipv6 = get_dns_record(self.agent_group, "AAAA")

		self.ipv4 = ipv4[0].address if ipv4 else None
		self.ipv6 = ipv6[0].address if ipv6 else None

	def validate_priority(self) -> None:
		"""Validates the priority of the agent group."""

		if frappe.db.exists(
			"Mail Agent Group", {"enabled": 1, "priority": self.priority, "name": ["!=", self.name]}
		):
			frappe.throw(
				_("Mail Agent Group with priority {0} already exists.").format(frappe.bold(self.priority))
			)
