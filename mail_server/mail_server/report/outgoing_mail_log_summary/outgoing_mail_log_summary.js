// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.query_reports["Outgoing Mail Log Summary"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "name",
			label: __("Outgoing Mail Log"),
			fieldtype: "Link",
			options: "Outgoing Mail Log",
		},
		{
			fieldname: "outgoing_mail",
			label: __("Outgoing Mail"),
			fieldtype: "Data",
			options: "Outgoing Mail",
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "MultiSelectList",
			get_data: (txt) => {
				return ["", "Blocked", "Deferred", "Bounced", "Sent"];
			},
		},
		{
			fieldname: "domain_name",
			label: __("Domain Name"),
			fieldtype: "MultiSelectList",
			get_data: (txt) => {
				return frappe.db.get_link_options("Mail Domain Registry", txt);
			},
		},
		{
			fieldname: "agent",
			label: __("Agent"),
			fieldtype: "MultiSelectList",
			get_data: (txt) => {
				return frappe.db.get_link_options("Mail Agent", txt, {
					enabled: 1,
					enable_outbound: 1,
				});
			},
		},
		{
			fieldname: "priority",
			label: __("Priority"),
			fieldtype: "Int",
		},
		{
			fieldname: "ip_address",
			label: __("IP Address"),
			fieldtype: "Data",
		},
		{
			fieldname: "email",
			label: __("Recipient"),
			fieldtype: "Data",
			options: "Email",
		},
		{
			fieldname: "message_id",
			label: __("Message ID"),
			fieldtype: "Data",
		},
		{
			fieldname: "include_newsletter",
			label: __("Include Newsletter"),
			fieldtype: "Check",
			default: 0,
		},
	],

	get_datatable_options(options) {
		return Object.assign(options, {
			checkboxColumn: true,
		});
	},

	onload(report) {
		if (!frappe.user_roles.includes("System Manager")) return;

		report.page.add_inner_button(__("Retry"), () => {
			let indexes = frappe.query_report.datatable.rowmanager.getCheckedRows();
			let selected_rows = indexes.map((i) => frappe.query_report.data[i]);

			if (!selected_rows.length) {
				frappe.throw(__("No rows selected. Please select at least one row to retry."));
			}

			frappe.call({
				method: "mail_server.mail_server.report.outgoing_mail_log_summary.outgoing_mail_log_summary.retry",
				args: {
					rows: selected_rows,
				},
			});
		});
	},
};
