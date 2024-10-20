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
