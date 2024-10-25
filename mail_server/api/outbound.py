import json

import frappe
from frappe import _

from mail_server.mail_server.doctype.outgoing_mail_log.outgoing_mail_log import create_outgoing_mail_log


@frappe.whitelist(methods=["POST"])
def send() -> str:
	data = json.loads(frappe.request.data.decode())
	log = create_outgoing_mail_log(data["outgoing_mail"], data["recipients"], data["message"])
	return log.name


@frappe.whitelist(methods=["GET"])
def fetch_delivery_status(outgoing_mail: str, token: str) -> dict:
	"""Returns the delivery status of the outgoing mail."""

	if not outgoing_mail or not token:
		frappe.throw(_("Both outgoing mail and token are required."), frappe.MandatoryError)

	if frappe.db.exists("Outgoing Mail Log", token):
		doc = frappe.get_doc("Outgoing Mail Log", token)

		if doc.outgoing_mail != outgoing_mail:
			frappe.throw(
				_(
					"The provided outgoing mail ({0}) does not match the specified token ({1}). Please verify your outgoing mail ID and token."
				).format(outgoing_mail, token)
			)

		return doc.get_delivery_status()

	return {
		"token": token,
		"status": "Failed",
		"error_message": _("No record found for the provided token ({0}) in the Outgoing Mail Log.").format(
			token
		),
		"outgoing_mail": outgoing_mail,
		"recipients": [],
	}


@frappe.whitelist(methods=["GET"])
def fetch_delivery_statuses() -> list[dict]:
	"""Returns the delivery statuses of the outgoing mails."""

	data = json.loads(frappe.request.data.decode()).get("data")

	if not data or not isinstance(data, list):
		frappe.throw(_("Invalid input. A list of dictionaries with 'outgoing_mail' and 'token' is required."))

	if len(data) > 500:
		frappe.throw(_("The maximum number of delivery statuses that can be fetched at a time is 500."))

	response = []

	for item in data:
		outgoing_mail = item["outgoing_mail"]
		token = item["token"]
		delivery_status = fetch_delivery_status(outgoing_mail, token)
		response.append(delivery_status)

	return response
