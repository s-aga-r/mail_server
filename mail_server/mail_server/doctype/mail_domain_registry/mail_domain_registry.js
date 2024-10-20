// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Mail Domain Registry", {
	refresh(frm) {
		frm.trigger("set_queries");
	},

	set_queries(frm) {
		frm.set_query("domain_owner", () => ({
			query: "mail_server.mail_server.doctype.mail_domain_registry.mail_domain_registry.get_domain_owner",
			filters: {
				enabled: 1,
				role: "Domain Owner",
			},
		}));
	},
});
