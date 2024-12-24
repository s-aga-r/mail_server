# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class MailGroupMember(Document):
	def validate(self) -> None:
		self.validate_account()
		self.validate_email()

	def validate_account(self) -> None:
		"""Validate if the account is of type Group"""

		if frappe.db.get_value("Mail Account", self.account, "type") != "group":
			frappe.throw(_("Mail Account must be of type Group"))

	def validate_email(self) -> None:
		"""Validate if the email is not the same as the account"""

		if self.email == self.account:
			frappe.throw(_("Email and Account cannot be the same"))


def after_doctype_insert() -> None:
	frappe.db.add_unique("Mail Group Member", ["account", "email"])
