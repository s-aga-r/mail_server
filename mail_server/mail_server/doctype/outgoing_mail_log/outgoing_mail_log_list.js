// Copyright (c) 2023, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.listview_settings["Outgoing Mail Log"] = {
	get_indicator: (doc) => {
		const status_colors = {
			"In Progress": "grey",
			Blocked: "red",
			Accepted: "blue",
			"Queuing (RMQ)": "orange",
			Failed: "red",
			"Queued (RMQ)": "yellow",
			"Queued (Haraka)": "blue",
			Deferred: "orange",
			Bounced: "pink",
			"Partially Sent": "purple",
			Sent: "green",
		};
		return [__(doc.status), status_colors[doc.status], "status,=," + doc.status];
	},
};
