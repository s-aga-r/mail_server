import frappe
from frappe import _

from mail_server.utils.user import has_role, is_system_manager


@frappe.whitelist(methods=["POST"])
def validate() -> None:
	"""Validate the user is a domain owner or system manager."""

	user = frappe.session.user
	if not has_role(user, "Domain Owner") and not is_system_manager(user):
		frappe.throw(_("Not permitted"), frappe.PermissionError)
