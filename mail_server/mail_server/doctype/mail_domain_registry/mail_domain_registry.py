# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from typing import Literal

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now

from mail_server.agent import Principal
from mail_server.mail_server.doctype.dns_record.dns_record import create_or_update_dns_record
from mail_server.mail_server.doctype.mail_server_settings.mail_server_settings import (
	validate_mail_server_settings,
)
from mail_server.utils import get_dmarc_address, verify_dns_record
from mail_server.utils.cache import delete_cache
from mail_server.utils.user import has_role, is_system_manager


class MailDomainRegistry(Document):
	def validate(self) -> None:
		if self.is_new():
			validate_mail_server_settings()
			self.last_verified_at = now()

		self.validate_domain_name()
		self.validate_is_verified()
		self.validate_is_subdomain()
		self.validate_domain_owner()

	def after_insert(self) -> None:
		create_or_delete_domain_on_agents(action="create", domain_name=self.domain_name)

	def on_update(self) -> None:
		delete_cache(f"user|{self.domain_owner}")

		if not self.is_new() and self.has_value_changed("domain_owner"):
			previous_doc = self.get_doc_before_save()
			if previous_doc and previous_doc.get("domain_owner"):
				delete_cache(f"user|{previous_doc.get('domain_owner')}")

		self.create_or_update_dkim_dns_record()

	def on_trash(self) -> None:
		if frappe.session.user != "Administrator":
			frappe.throw(_("Only Administrator can delete Mail Domain Registry."))

		create_or_delete_domain_on_agents(action="delete", domain_name=self.domain_name)

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

		if self.domain_owner and not has_role(self.domain_owner, "Domain Owner"):
			frappe.throw(
				_("User {0} does not have Domain Owner role.").format(frappe.bold(self.domain_owner))
			)

	def create_or_update_dkim_dns_record(self) -> None:
		"""Creates or Updates DKIM DNS Record"""

		if self.dkim_public_key:
			frappe.flags.enqueue_dns_record_update = True
			create_or_update_dns_record(
				host=self.get_dkim_host(),
				type="TXT",
				value=f"v=DKIM1; k=rsa; p={self.dkim_public_key}",
				ttl=300,
				category="Sending Record",
				attached_to_doctype=self.doctype,
				attached_to_docname=self.name,
			)
		else:
			if dkim_dns_record := frappe.db.exists(
				"DNS Record", {"host": self.get_dkim_host(), "type": "TXT"}
			):
				frappe.delete_doc("DNS Record", dkim_dns_record, ignore_permissions=True)

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

		# DKIM Record
		records.append(
			{
				"category": "Sending Record",
				"type": "CNAME",
				"host": f"frappemail._domainkey.{self.domain_name}",
				"value": f"{self.get_dkim_host()}.{ms_settings.root_domain_name}.",
				"ttl": ms_settings.default_ttl,
			}
		)

		# DMARC Record
		dmarc_address = get_dmarc_address()
		records.append(
			{
				"category": "Sending Record",
				"type": "TXT",
				"host": f"_dmarc.{self.domain_name}",
				"value": f"v=DMARC1; p=reject; rua=mailto:{dmarc_address}; ruf=mailto:{dmarc_address}; fo=1; aspf=s; adkim=s; pct=100;",
				"ttl": ms_settings.default_ttl,
			}
		)

		# MX Record(s)
		if inbound_agent_groups := frappe.db.get_all(
			"Mail Agent Group",
			filters={"enabled": 1, "inbound": 1},
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

		errors = []
		for record in self.get_dns_records():
			if not verify_dns_record(record["host"], record["type"], record["value"]):
				errors.append(
					_("Could not verify {0}:{1} record.").format(
						frappe.bold(record["type"]), frappe.bold(record["host"])
					)
				)

		is_verified = 0 if errors else 1
		dns_verification_errors = "\n".join(errors) if errors else None
		self._db_set(
			is_verified=is_verified,
			last_verified_at=now(),
			dns_verification_errors=dns_verification_errors,
			notify_update=True,
		)

	def get_dkim_host(self) -> str:
		"""Returns DKIM Host"""

		return f"{self.domain_name.replace('.', '-')}._domainkey"

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


def create_or_delete_domain_on_agents(
	action: Literal["create", "delete"], domain_name: str, agents: list[str] | None = None
) -> None:
	"""Creates or Deletes Domain on Agents"""

	primary_agents = agents or frappe.db.get_all(
		"Mail Agent", filters={"enabled": 1, "is_primary": 1}, pluck="name"
	)

	if not primary_agents:
		return

	principal = Principal(name=domain_name, type="domain").__dict__
	for agent in primary_agents:
		agent_job = frappe.new_doc("Mail Agent Job")
		agent_job.agent = agent

		if action == "create":
			agent_job.method = "POST"
			agent_job.endpoint = "/api/principal"
			agent_job.request_json = principal
		elif action == "delete":
			agent_job.method = "DELETE"
			agent_job.endpoint = f"/api/principal/{domain_name}"

		agent_job.insert()
