# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.query_builder import Order
from frappe.query_builder.functions import Date, IfNull
from frappe.utils import flt


def execute(filters: dict | None = None) -> tuple[list, list]:
	columns = get_columns()
	data = get_data(filters)
	summary = get_summary(data)

	return columns, data, None, None, summary


def get_columns() -> list[dict]:
	return [
		{
			"label": _("Name"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Outgoing Mail Log",
			"width": 100,
		},
		{
			"label": _("Received At"),
			"fieldname": "received_at",
			"fieldtype": "Datetime",
			"width": 180,
		},
		{
			"label": _("Status"),
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"label": _("Retries"),
			"fieldname": "retries",
			"fieldtype": "Int",
			"width": 80,
		},
		{
			"label": _("Message Size"),
			"fieldname": "message_size",
			"fieldtype": "Int",
			"width": 120,
		},
		{
			"label": _("Priority"),
			"fieldname": "priority",
			"fieldtype": "Int",
			"width": 80,
		},
		{
			"label": _("Newsletter"),
			"fieldname": "is_newsletter",
			"fieldtype": "Check",
			"width": 100,
		},
		{
			"label": _("Receiving Delay"),
			"fieldname": "receiving_delay",
			"fieldtype": "Float",
			"width": 140,
		},
		{
			"label": _("Transfer Delay"),
			"fieldname": "transfer_delay",
			"fieldtype": "Float",
			"width": 120,
		},
		{
			"label": _("Action Delay"),
			"fieldname": "action_delay",
			"fieldtype": "Float",
			"width": 120,
		},
		{
			"label": _("Total Delay"),
			"fieldname": "total_delay",
			"fieldtype": "Float",
			"width": 120,
		},
		{
			"label": _("Domain Name"),
			"fieldname": "domain_name",
			"fieldtype": "Link",
			"options": "Mail Domain Registry",
			"width": 150,
		},
		{
			"label": _("Agent"),
			"fieldname": "agent",
			"fieldtype": "Link",
			"options": "Mail Agent",
			"width": 150,
		},
		{
			"label": _("IP Address"),
			"fieldname": "ip_address",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("Recipient"),
			"fieldname": "recipient",
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"label": _("Outgoing Mail"),
			"fieldname": "outgoing_mail",
			"fieldtype": "Data",
			"options": "Outgoing Mail",
			"width": 120,
		},
		{
			"label": _("Message ID"),
			"fieldname": "message_id",
			"fieldtype": "Data",
			"width": 200,
		},
	]


def get_data(filters: dict | None = None) -> list[list]:
	filters = filters or {}

	OML = frappe.qb.DocType("Outgoing Mail Log")
	MLR = frappe.qb.DocType("Mail Log Recipient")

	query = (
		frappe.qb.from_(OML)
		.left_join(MLR)
		.on(OML.name == MLR.parent)
		.select(
			OML.name,
			OML.received_at,
			MLR.status,
			MLR.retries,
			OML.message_size,
			OML.priority,
			OML.is_newsletter,
			OML.received_after.as_("receiving_delay"),
			(OML.transfer_started_after + OML.transfer_completed_after).as_("transfer_delay"),
			MLR.action_after.as_("action_delay"),
			(
				OML.received_after
				+ OML.transfer_started_after
				+ OML.transfer_completed_after
				+ MLR.action_after
			).as_("total_delay"),
			OML.domain_name,
			OML.agent,
			OML.ip_address,
			MLR.email.as_("recipient"),
			OML.outgoing_mail,
			OML.message_id,
		)
		.where(IfNull(MLR.status, "") != "")
		.orderby(OML.received_at, order=Order.desc)
		.orderby(MLR.idx, order=Order.asc)
	)

	if not filters.get("name") and not filters.get("outgoing_mail") and not filters.get("message_id"):
		query = query.where(
			(Date(OML.received_at) >= Date(filters.get("from_date")))
			& (Date(OML.received_at) <= Date(filters.get("to_date")))
		)

	if not filters.get("include_newsletter"):
		query = query.where(OML.is_newsletter == 0)

	for field in [
		"name",
		"outgoing_mail",
		"domain_name",
		"agent",
		"priority",
		"ip_address",
		"message_id",
	]:
		if filters.get(field):
			query = query.where(OML[field] == filters.get(field))

	for field in ["status", "email"]:
		if filters.get(field):
			query = query.where(MLR[field] == filters.get(field))

	return query.run(as_dict=True)


def get_summary(data: list) -> list[dict]:
	if not data:
		return []

	summary_data = {}
	average_data = {}

	for row in data:
		for field in ["message_size", "receiving_delay", "transfer_delay", "action_delay"]:
			key = f"total_{field}"
			summary_data.setdefault(key, 0)
			summary_data[key] += row[field]

	for key, value in summary_data.items():
		key = key.replace("total_", "")
		average_data[key] = flt(value / len(data) if data else 0, 1)

	return [
		{
			"label": _("Average Message Size"),
			"datatype": "Int",
			"value": average_data["message_size"],
			"indicator": "green",
		},
		{
			"label": _("Average Receiving Delay"),
			"datatype": "Data",
			"value": f"{average_data['receiving_delay']}s",
			"indicator": "yellow",
		},
		{
			"label": _("Average Transfer Delay"),
			"datatype": "Data",
			"value": f"{average_data['transfer_delay']}s",
			"indicator": "blue",
		},
		{
			"label": _("Average Action Delay"),
			"datatype": "Data",
			"value": f"{average_data['action_delay']}s",
			"indicator": "orange",
		},
	]
