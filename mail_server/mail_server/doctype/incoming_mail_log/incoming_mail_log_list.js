// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.listview_settings["Incoming Mail Log"] = {
	refresh: (listview) => {
		listview.page.add_inner_button("Refresh", () => {
			fetch_emails_from_queue(listview);
		});
	},

	get_indicator: (doc) => {
		const status_colors = {
			"In Progress": "grey",
			Rejected: "red",
			Accepted: "green",
		};
		return [__(doc.status), status_colors[doc.status], "status,=," + doc.status];
	},
};

function fetch_emails_from_queue(listview) {
	frappe.call({
		method: "mail_server.tasks.enqueue_fetch_emails_from_queue",
		freeze: true,
		freeze_message: __("Creating Job..."),
		callback: () => {
			frappe.show_alert({
				message: __("{0} job has been created.", [__("Fetch Mails").bold()]),
				indicator: "green",
			});
		},
	});
}
