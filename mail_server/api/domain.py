import frappe
from frappe import _

from mail_server.utils.cache import get_root_domain_name
from mail_server.utils.validation import (
	is_domain_registry_exists,
	validate_user_has_domain_owner_role,
	validate_user_is_domain_owner,
)


@frappe.whitelist(methods=["POST"])
def add_or_update_domain(domain_name: str, mail_client_host: str = None) -> dict:
	"""Add or update domain in Mail Domain Registry."""

	user = frappe.session.user
	validate_user_has_domain_owner_role(user)

	if is_domain_registry_exists(domain_name):
		validate_user_is_domain_owner(user, domain_name)
		doc = frappe.get_doc("Mail Domain Registry", domain_name)

		if mail_client_host and doc.mail_client_host != mail_client_host:
			doc.db_set("mail_client_host", mail_client_host)
	else:
		doc = frappe.new_doc("Mail Domain Registry")
		doc.domain_owner = user
		doc.domain_name = domain_name
		doc.mail_client_host = mail_client_host
		doc.insert(ignore_permissions=True)

	response = {
		"domain_name": doc.domain_name,
		"dns_records": doc.get_dns_records(),
		"dkim_domain": get_root_domain_name(),
		"inbound_token": doc.get_password("inbound_token"),
	}
	response["dkim_selector"], response["dkim_private_key"] = doc.get_dkim_selector_and_private_key()

	return response


@frappe.whitelist(methods=["GET"])
def get_dns_records(domain_name: str) -> list[dict] | None:
	"""Returns DNS records for the given domain."""

	user = frappe.session.user
	validate_user_has_domain_owner_role(user)

	if is_domain_registry_exists(domain_name, raise_exception=True):
		validate_user_is_domain_owner(user, domain_name)
		doc = frappe.get_doc("Mail Domain Registry", domain_name)
		doc.db_set("is_verified", 0, notify=True, commit=True)
		return doc.get_dns_records()


@frappe.whitelist(methods=["POST"])
def verify_dns_records(domain_name: str) -> list[str] | None:
	"""Verify DNS records for the given domain."""

	user = frappe.session.user
	validate_user_has_domain_owner_role(user)

	if is_domain_registry_exists(domain_name, raise_exception=True):
		validate_user_is_domain_owner(user, domain_name)
		doc = frappe.get_doc("Mail Domain Registry", domain_name)
		doc.verify_dns_records()
		return doc.verification_errors.split("\n") if doc.verification_errors else None
