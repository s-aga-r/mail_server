# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json
from typing import Literal

import frappe
from frappe.model.document import Document


class MailAccountEmail(Document):
	def validate(self) -> None:
		self.validate_type()
		self.validate_domain_name()

	def on_update(self) -> None:
		if self.has_value_changed("email"):
			self.update_account_email_on_agents(action="create")
			return

		if self.has_value_changed("account"):
			self.update_account_email_on_agents(action="patch")

	def on_trash(self) -> None:
		self.update_account_email_on_agents(action="delete")

	def validate_type(self) -> None:
		"""Ensure only one primary email account exists for an mail account"""

		if self.type == "primary":
			frappe.db.set_value(
				"Mail Account Email",
				{"account": self.account, "type": "primary", "name": ["!=", self.name]},
				"type",
				"alias",
			)

	def validate_domain_name(self) -> None:
		"""Set domain name if not set"""

		if not self.domain_name:
			self.domain_name = self.email.split("@")[1]

	def update_account_email_on_agents(self, action: Literal["create", "patch", "delete"]) -> None:
		"""Updates account email on agents"""

		primary_agents = frappe.db.get_all(
			"Mail Agent", filters={"enabled": 1, "is_primary": 1}, pluck="name"
		)

		if not primary_agents:
			return

		for agent in primary_agents:
			agent_job = frappe.new_doc("Mail Agent Job")
			agent_job.agent = agent
			agent_job.method = "PATCH"
			agent_job.endpoint = f"/api/principal/{self.account}"

			request_data = []
			if action in ["create", "patch"]:
				# Remove email from previous account
				if action == "patch":
					frappe.get_doc(
						{
							"doctype": "Mail Agent Job",
							"agent": agent,
							"method": "PATCH",
							"endpoint": f"/api/principal/{self.get_doc_before_save().account}",
							"request_data": json.dumps(
								[{"action": "removeItem", "field": "emails", "value": self.email}]
							),
						}
					).insert()

				request_data.append({"action": "addItem", "field": "emails", "value": self.email})
			elif action == "delete":
				request_data.append({"action": "removeItem", "field": "emails", "value": self.email})

			agent_job.request_data = json.dumps(request_data)
			agent_job.insert()
