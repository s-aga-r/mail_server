import frappe
from frappe import _

from mail_server.utils.cache import get_user_owned_domains
from mail_server.utils.user import has_role, is_system_manager


@frappe.whitelist(methods=["POST"])
def add_or_update_domain(domain_name: str) -> dict:
	"""Add or update domain in Mail Domain Registry."""

	user = frappe.session.user
	validate_user_has_domain_owner_role(user)

	if frappe.db.exists("Mail Domain Registry", domain_name):
		validate_user_is_domain_owner(user, domain_name)
		doc = frappe.get_doc("Mail Domain Registry", domain_name)
	else:
		doc = frappe.new_doc("Mail Domain Registry")
		doc.domain_name = domain_name
		doc.domain_owner = user
		doc.insert(ignore_permissions=True)

	response = {"domain_name": doc.domain_name, "dns_records": doc.get_dns_records()}
	response["dkim_selector"], response["dkim_private_key"] = doc.get_dkim_selector_and_private_key()

	return response


@frappe.whitelist(methods=["GET"])
def get_dns_records(domain_name: str) -> list[dict] | None:
	"""Returns DNS records for the given domain."""

	user = frappe.session.user
	validate_user_has_domain_owner_role(user)

	if frappe.db.exists("Mail Domain Registry", domain_name):
		validate_user_is_domain_owner(user, domain_name)
		doc = frappe.get_doc("Mail Domain Registry", domain_name)
		doc.db_set("is_verified", 0, notify=True, commit=True)
		return doc.get_dns_records()

	frappe.throw(
		_("Domain {0} not found in Mail Domain Registry").format(domain_name), frappe.DoesNotExistError
	)


@frappe.whitelist(methods=["POST"])
def verify_dns_records(domain_name: str) -> list[str] | None:
	"""Verify DNS records for the given domain."""

	user = frappe.session.user
	validate_user_has_domain_owner_role(user)

	if frappe.db.exists("Mail Domain Registry", domain_name):
		validate_user_is_domain_owner(user, domain_name)
		doc = frappe.get_doc("Mail Domain Registry", domain_name)
		doc.verify_dns_records()
		return doc.verification_errors.split("\n") if doc.verification_errors else None

	frappe.throw(
		_("Domain {0} not found in Mail Domain Registry").format(domain_name), frappe.DoesNotExistError
	)


def validate_user_has_domain_owner_role(user: str):
	"""Validate if the user has Domain Owner role or System Manager role."""

	if not has_role(user, "Domain Owner") and not is_system_manager(user):
		frappe.throw("You are not authorized to perform this action.", frappe.PermissionError)


def validate_user_is_domain_owner(user: str, domain_name: str):
	"""Validate if the user is the owner of the given domain."""

	if domain_name not in get_user_owned_domains(user) and not is_system_manager(user):
		frappe.throw("You are not authorized to perform this action.", frappe.PermissionError)
