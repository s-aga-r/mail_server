import ipaddress
import re
import socket

import frappe
from frappe import _
from frappe.utils.caching import redis_cache
from validate_email_address import validate_email

from mail_server.utils.cache import get_user_owned_domains
from mail_server.utils.user import has_role


def is_valid_host(host: str) -> bool:
	"""Returns True if the host is a valid hostname else False."""

	return bool(re.compile(r"^[a-zA-Z0-9_-]+$").match(host))


def is_valid_ip(ip: str, category: str | None = None) -> bool:
	"""Returns True if the IP is valid else False."""

	try:
		ip_obj = ipaddress.ip_address(ip)

		if category:
			if category == "private":
				return ip_obj.is_private
			elif category == "public":
				return not ip_obj.is_private

		return True
	except ValueError:
		return False


def is_port_open(fqdn: str, port: int) -> bool:
	"""Returns True if the port is open else False."""

	try:
		with socket.create_connection((fqdn, port), timeout=10):
			return True
	except (TimeoutError, OSError):
		return False


def is_domain_registry_exists(
	domain_name: str, exclude_disabled: bool = True, raise_exception: bool = False
) -> bool:
	"""Validate if the domain exists in the Mail Domain Registry."""

	filters = {"domain_name": domain_name}
	if exclude_disabled:
		filters["enabled"] = 1

	if frappe.db.exists("Mail Domain Registry", filters):
		return True

	if raise_exception:
		if exclude_disabled:
			frappe.throw(
				_("Domain {0} does not exist or may be disabled in the Mail Domain Registry").format(
					frappe.bold(domain_name)
				),
				frappe.DoesNotExistError,
			)

		frappe.throw(
			_("Domain {0} not found in Mail Domain Registry").format(frappe.bold(domain_name)),
			frappe.DoesNotExistError,
		)

	return False


def validate_user_has_domain_owner_role(user: str) -> None:
	"""Validate if the user has Domain Owner role or System Manager role."""

	if not has_role(user, "Domain Owner"):
		frappe.throw(_("You are not authorized to perform this action."), frappe.PermissionError)


def validate_user_is_domain_owner(user: str, domain_name: str) -> None:
	"""Validate if the user is the owner of the given domain."""

	if domain_name not in get_user_owned_domains(user):
		frappe.throw(
			_("The domain {0} does not belong to user {1}.").format(
				frappe.bold(domain_name), frappe.bold(user)
			),
			frappe.PermissionError,
		)


def validate_email_address(
	email: str, check_mx: bool = True, verify: bool = True, smtp_timeout: int = 10
) -> bool:
	"""Validates the email address by checking MX records and RCPT TO."""

	return bool(validate_email(email=email, check_mx=check_mx, verify=verify, smtp_timeout=smtp_timeout))


@frappe.whitelist()
@redis_cache(ttl=3600)
def validate_email_address_cache(email: str) -> bool:
	"""Wrapper function of `utils.validation.validate_email_address` for caching."""

	return validate_email_address(email)
