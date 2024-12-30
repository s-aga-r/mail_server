# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import crypt
import json
from typing import Literal

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import random_string, validate_email_address

from mail_server.agent import Principal


class MailAccount(Document):
	def validate(self) -> None:
		self.validate_password()

	def on_update(self) -> None:
		if self.has_value_changed("email"):
			self.update_account_on_agents(action="create")
			return

		has_value_changed = (
			self.has_value_changed("password")
			or self.has_value_changed("display_name")
			or self.has_value_changed("secret")
		)
		if has_value_changed:
			self.update_account_on_agents(action="patch")

	def after_insert(self) -> None:
		self.create_primary_email()

	def on_trash(self) -> None:
		self.update_account_on_agents(action="delete")

	def validate_password(self) -> None:
		"""Generates secret if password is changed"""

		if self.type == "individual":
			if not self.password:
				self.password = random_string(length=20)
		elif self.type == "group":
			self.password = None
			return

		if not self.is_new():
			if previous_doc := self.get_doc_before_save():
				if previous_doc.get_password("password") == self.get_password("password"):
					return

		self.generate_secret()

	def update_account_on_agents(self, action: Literal["create", "patch", "delete"]) -> None:
		"""Updates account on agents"""

		primary_agents = frappe.db.get_all(
			"Mail Agent", filters={"enabled": 1, "is_primary": 1}, pluck="name"
		)

		if not primary_agents:
			return

		principal = Principal(
			name=self.email,
			type="individual",
			description=self.display_name,
			secrets=[self.secret],
			roles=["user", "admin"],
		).__dict__
		for agent in primary_agents:
			agent_job = frappe.new_doc("Mail Agent Job")
			agent_job.agent = agent

			if action == "create":
				agent_job.method = "POST"
				agent_job.endpoint = "/api/principal"
				agent_job.request_json = principal
			elif action == "patch":
				agent_job.method = "PATCH"
				agent_job.endpoint = f"/api/principal/{self.email}"

				request_data = []
				if self.has_value_changed("display_name"):
					request_data.append(
						{
							"action": "set",
							"field": "description",
							"value": self.display_name,
						}
					)
				if self.has_value_changed("secret"):
					request_data.append(
						{
							"action": "addItem",
							"field": "secrets",
							"value": self.secret,
						}
					)
					request_data.append(
						{
							"action": "removeItem",
							"field": "secrets",
							"value": self.get_doc_before_save().secret,
						}
					)
				agent_job.request_data = json.dumps(request_data)
			elif action == "delete":
				agent_job.method = "DELETE"
				agent_job.endpoint = f"/api/principal/{self.email}"

			agent_job.insert()

	def create_primary_email(self) -> None:
		"""Creates primary email for individual accounts"""

		if (self.type != "individual") or (validate_email_address(self.email) != self.email):
			return

		doc = frappe.new_doc("Mail Account Email")
		doc.account = self.name
		doc.email = self.email
		doc.type = "primary"
		doc.save()

	def generate_secret(self) -> None:
		"""Generates secret from password"""

		password = self.get_password("password")
		salt = crypt.mksalt(crypt.METHOD_SHA512)
		self.secret = crypt.crypt(password, salt)
