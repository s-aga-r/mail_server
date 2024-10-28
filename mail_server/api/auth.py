import frappe
from frappe import _


@frappe.whitelist(methods=["POST"])
def validate() -> None:
	"""Validate the user is a domain owner or system manager."""

	frappe.only_for(["Domain Owner", "System Manager", "Administrator"])
