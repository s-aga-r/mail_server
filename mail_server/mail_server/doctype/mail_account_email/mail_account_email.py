# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class MailAccountEmail(Document):
	def validate(self) -> None:
		self.validate_type()

	def validate_type(self) -> None:
		"""Ensure only one primary email account exists for an mail account"""

		if self.type == "primary":
			frappe.db.set_value(
				"Mail Account Email",
				{"account": self.account, "type": "primary", "name": ["!=", self.name]},
				"type",
				"alias",
			)
