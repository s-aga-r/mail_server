# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class MailServerSyncHistory(Document):
	def before_insert(self) -> None:
		self.validate_duplicate()

	def validate_duplicate(self) -> None:
		"""Validate if the Mail Server Sync History already exists."""

		if frappe.db.exists(
			"Mail Server Sync History",
			{"source": self.source, "user": self.user, "domain_name": self.domain_name},
		):
			frappe.throw(_("Mail Server Sync History already exists for this source, user and domain."))

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


def create_mail_server_sync_history(
	source: str,
	user: str,
	domain_name: str,
	last_synced_at: str | None = None,
	commit: bool = False,
) -> "MailServerSyncHistory":
	"""Create a Mail Server Sync History."""

	doc = frappe.new_doc("Mail Server Sync History")
	doc.source = source
	doc.user = user
	doc.domain_name = domain_name
	doc.last_synced_at = last_synced_at
	doc.insert(ignore_permissions=True)

	if commit:
		frappe.db.commit()

	return doc


def get_mail_server_sync_history(source: str, user: str, domain_name: str) -> "MailServerSyncHistory":
	"""Returns the Mail Server Sync History for the given source, user and domain."""

	if name := frappe.db.exists(
		"Mail Server Sync History", {"source": source, "user": user, "domain_name": domain_name}
	):
		return frappe.get_doc("Mail Server Sync History", name)

	return create_mail_server_sync_history(source, user, domain_name, commit=True)


def on_doctype_update():
	frappe.db.add_unique(
		"Mail Server Sync History",
		["source", "user", "domain_name"],
		constraint_name="unique_source_user_domain",
	)
