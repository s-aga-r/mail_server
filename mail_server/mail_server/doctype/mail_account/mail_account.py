# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import crypt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import validate_email_address


class MailAccount(Document):
	def validate(self) -> None:
		self.validate_password()

	def after_insert(self) -> None:
		self.create_primary_email()

	def validate_password(self) -> None:
		"""Generates secret if password is changed"""

		if self.type == "individual":
			if not self.password:
				frappe.throw(_("Password is mandatory for individual accounts"))
		elif self.type == "group":
			self.password = None
			return

		if not self.is_new():
			if previous_doc := self.get_doc_before_save():
				if previous_doc.get_password("password") == self.get_password("password"):
					return

		self.generate_secret()

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
