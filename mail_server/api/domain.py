import frappe
from frappe import _

from mail_server.utils.validation import (
	is_domain_registry_exists,
	validate_user_has_domain_owner_role,
	validate_user_is_domain_owner,
)


@frappe.whitelist(methods=["POST"])
def add_or_update_domain(
	domain_name: str, access_token: str, dkim_public_key: str, mail_host: str | None = None
) -> None:
	"""Add or update domain in Mail Domain Registry."""

	if not domain_name:
		frappe.throw(_("Domain Name is required."), frappe.MandatoryError)

	user = frappe.session.user
	validate_user_has_domain_owner_role(user)

	if is_domain_registry_exists(domain_name):
		validate_user_is_domain_owner(user, domain_name)
		doc = frappe.get_doc("Mail Domain Registry", domain_name)
	else:
		doc = frappe.new_doc("Mail Domain Registry")
		doc.domain_owner = user
		doc.domain_name = domain_name

	doc.access_token = access_token
	doc.dkim_public_key = dkim_public_key
	doc.mail_host = mail_host
	doc.save(ignore_permissions=True)


@frappe.whitelist(methods=["GET"])
def get_dns_records(domain_name: str) -> list[dict] | None:
	"""Returns DNS records for the given domain."""

	if not domain_name:
		frappe.throw(_("Domain Name is required."), frappe.MandatoryError)

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

	if not domain_name:
		frappe.throw(_("Domain Name is required."), frappe.MandatoryError)

	user = frappe.session.user
	validate_user_has_domain_owner_role(user)

	if is_domain_registry_exists(domain_name, raise_exception=True):
		validate_user_is_domain_owner(user, domain_name)
		doc = frappe.get_doc("Mail Domain Registry", domain_name)
		doc.verify_dns_records()

		if doc.dns_verification_errors:
			return doc.dns_verification_errors.split("\n")
