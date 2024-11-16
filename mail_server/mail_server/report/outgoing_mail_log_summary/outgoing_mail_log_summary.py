# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import json
from datetime import datetime

import frappe
from frappe import _
from frappe.query_builder import Order
from frappe.query_builder.functions import Date, IfNull


def execute(filters: dict | None = None) -> tuple:
	columns = get_columns()
	data = get_data(filters)
	chart = get_chart(data)
	summary = get_summary(data)

	return columns, data, None, chart, summary


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
			"label": _("Response Message"),
			"fieldname": "response",
			"fieldtype": "Code",
			"width": 500,
		},
		{
			"label": _("Domain Name"),
			"fieldname": "domain_name",
			"fieldtype": "Link",
			"options": "Mail Domain Registry",
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
			MLR.response,
			OML.domain_name,
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
		"priority",
		"ip_address",
		"message_id",
	]:
		if filters.get(field):
			query = query.where(OML[field] == filters.get(field))

	for field in ["status", "email"]:
		if filters.get(field):
			query = query.where(MLR[field] == filters.get(field))

	data = query.run(as_dict=True)

	for row in data:
		response = json.loads(row["response"])
		row["response"] = (
			response.get("dsn_msg")
			or response.get("reason")
			or response.get("dsn_smtp_response")
			or response.get("response")
		)

	return data


def get_chart(data: list) -> list[dict]:
	labels, sent, deffered, bounced = [], [], [], []

	for row in reversed(data):
		if not isinstance(row["received_at"], datetime):
			frappe.throw(_("Invalid date format"))

		date = row["received_at"].date().strftime("%d-%m-%Y")

		if date not in labels:
			labels.append(date)

			if row["status"] == "Sent":
				sent.append(1)
				deffered.append(0)
				bounced.append(0)
			elif row["status"] == "Deferred":
				sent.append(0)
				deffered.append(1)
				bounced.append(0)
			elif row["status"] == "Bounced":
				sent.append(0)
				deffered.append(0)
				bounced.append(1)
			else:
				sent.append(0)
				deffered.append(0)
				bounced.append(0)
		else:
			idx = labels.index(date)
			if row["status"] == "Sent":
				sent[idx] += 1
			elif row["status"] == "Deferred":
				deffered[idx] += 1
			elif row["status"] == "Bounced":
				bounced[idx] += 1

	return {
		"data": {
			"labels": labels,
			"datasets": [
				{"name": "bounced", "values": bounced},
				{"name": "deffered", "values": deffered},
				{"name": "sent", "values": sent},
			],
		},
		"fieldtype": "Int",
		"type": "bar",
		"axisOptions": {"xIsSeries": -1},
	}


def get_summary(data: list) -> list[dict]:
	if not data:
		return []

	status_count = {}

	for row in data:
		status = row["status"]
		if status in ["Sent", "Deferred", "Bounced"]:
			status_count.setdefault(status, 0)
			status_count[status] += 1

	return [
		{
			"label": _("Sent"),
			"datatype": "Int",
			"value": status_count.get("Sent", 0),
			"indicator": "green",
		},
		{
			"label": _("Deferred"),
			"datatype": "Int",
			"value": status_count.get("Deferred", 0),
			"indicator": "blue",
		},
		{
			"label": _("Bounced"),
			"datatype": "Int",
			"value": status_count.get("Bounced", 0),
			"indicator": "red",
		},
	]
