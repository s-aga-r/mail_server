import frappe
from frappe import _

from mail_server.mail_server.doctype.ip_blacklist.ip_blacklist import get_blacklist_for_ip_address


@frappe.whitelist(methods=["GET"], allow_guest=True)
def get(ip_address: str) -> dict:
	"""Returns the blacklist for the given IP address."""

	if not ip_address:
		frappe.throw(_("IP address is required."), frappe.MandatoryError)

	return get_blacklist_for_ip_address(ip_address, create_if_not_exists=True, commit=True) or {}
