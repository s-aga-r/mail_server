import re

import frappe
from frappe import _


def is_valid_host(host: str) -> bool:
	"""Returns True if the host is a valid hostname else False."""

	return bool(re.compile(r"^[a-zA-Z0-9_-]+$").match(host))


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
