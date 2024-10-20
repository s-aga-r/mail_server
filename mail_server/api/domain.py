import frappe


@frappe.whitelist(methods=["POST"])
def add_or_update_domain(domain_name: str) -> dict:
	"""Add or update domain in Mail Domain Registry."""

	response = {}

	if frappe.db.exists("Mail Domain Registry", domain_name):
		doc = frappe.get_doc("Mail Domain Registry", domain_name)
	else:
		doc = frappe.new_doc("Mail Domain Registry")
		doc.domain_name = domain_name
		doc.insert()

	response["domain_name"] = doc.domain_name
	response["dns_records"] = doc.get_dns_records()
	response["dkim_selector"], response["dkim_private_key"] = doc.get_dkim_selector_and_private_key()

	return response


@frappe.whitelist(methods=["GET"])
def get_dns_records(domain_name: str) -> list[dict] | None:
	"""Returns DNS records for the given domain."""

	if frappe.db.exists("Mail Domain Registry", domain_name):
		doc = frappe.get_doc("Mail Domain Registry", domain_name)
		doc.db_set("is_verified", 0, notify=True, commit=True)
		return doc.get_dns_records()


@frappe.whitelist(methods=["POST"])
def verify_dns_records(domain_name: str) -> list[str] | None:
	"""Verify DNS records for the given domain."""

	if frappe.db.exists("Mail Domain Registry", domain_name):
		doc = frappe.get_doc("Mail Domain Registry", domain_name)
		doc.verify_dns_records()
		return doc.verification_errors.split("\n") if doc.verification_errors else None
