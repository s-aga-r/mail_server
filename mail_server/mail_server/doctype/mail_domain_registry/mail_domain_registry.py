# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, now

from mail_server.mail_server.doctype.dkim_key.dkim_key import (
	create_dkim_key,
	get_dkim_selector_and_private_key,
)
from mail_server.mail_server.doctype.mail_server_settings.mail_server_settings import (
	validate_mail_server_settings,
)
from mail_server.utils.cache import delete_cache
from mail_server.utils.user import has_role, is_system_manager


class MailDomainRegistry(Document):
	def validate(self) -> None:
		self.validate_domain_name()
		self.validate_is_verified()
		self.validate_is_subdomain()
		self.validate_domain_owner()
		self.validate_dkim_key_size()

		if self.is_new() or self.has_value_changed("dkim_key_size"):
			self.last_verified_at = now()
			validate_mail_server_settings()
			create_dkim_key(self.domain_name, cint(self.dkim_key_size))

	def on_update(self) -> None:
		delete_cache(f"user|{self.domain_owner}")

		if not self.is_new() and self.has_value_changed("domain_owner"):
			previous_doc = self.get_doc_before_save()
			if previous_doc and previous_doc.get("domain_owner"):
				delete_cache(f"user|{previous_doc.get('domain_owner')}")

	def on_trash(self) -> None:
		if frappe.session.user != "Administrator":
			frappe.throw(_("Only Administrator can delete Mail Domain Registry."))

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

		if not has_role(self.domain_owner, "Domain Owner") and not is_system_manager(self.domain_owner):
			frappe.throw(
				_("User {0} does not have Domain Owner role.").format(frappe.bold(self.domain_owner))
			)

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
		if inbound_agent_groups := frappe.db.get_all(
			"Mail Agent Group",
			filters={"enabled": 1},
			fields=["agent_group", "priority"],
			order_by="priority asc",
		):
			for group in inbound_agent_groups:
				records.append(
					{
						"category": "Receiving Record",
						"type": "MX",
						"host": self.domain_name,
						"value": f"{group.agent_group.split(':')[0]}.",
						"priority": group.priority,
						"ttl": ms_settings.default_ttl,
					}
				)

		return records

	def verify_dns_records(self) -> None:
		"""Verifies DNS Records"""

		from mail_server.utils import verify_dns_record

		errors = []
		for record in self.get_dns_records():
			if not verify_dns_record(record["host"], record["type"], record["value"]):
				errors.append(
					_("Could not verify {0}:{1} record.").format(
						frappe.bold(record["type"]), frappe.bold(record["host"])
					)
				)

		frappe.db.set_value(
			self.doctype,
			self.name,
			{
				"verification_errors": "\n".join(errors) if errors else None,
				"is_verified": 0 if errors else 1,
				"last_verified_at": now(),
			},
		)
		self.reload()

	def get_dkim_selector_and_private_key(self) -> tuple[str, str]:
		"""Returns DKIM Selector and Private Key"""

		return get_dkim_selector_and_private_key(self.domain_name, raise_exception=True)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_users_with_domain_owner_role(
	doctype: str | None = None,
	txt: str | None = None,
	searchfield: str | None = None,
	start: int = 0,
	page_len: int = 20,
	filters: dict | None = None,
) -> list:
	"""Returns a list of User(s) who have Domain Owner role."""

	USER = frappe.qb.DocType("User")
	HAS_ROLE = frappe.qb.DocType("Has Role")
	return (
		frappe.qb.from_(USER)
		.left_join(HAS_ROLE)
		.on(USER.name == HAS_ROLE.parent)
		.select(USER.name)
		.where(
			(USER.enabled == 1)
			& (USER.name.like(f"%{txt}%"))
			& (HAS_ROLE.role == "Domain Owner")
			& (HAS_ROLE.parenttype == "User")
		)
	).run(as_dict=False)


def get_permission_query_condition(user: str | None = None) -> str:
	if not user:
		user = frappe.session.user

	if is_system_manager(user):
		return ""

	return f"(`tabMail Domain Registry`.`domain_owner` = {frappe.db.escape(user)})"


def has_permission(doc: "Document", ptype: str, user: str) -> bool:
	if doc.doctype != "Mail Domain Registry":
		return False

	return (user == doc.domain_owner) or is_system_manager(user)
