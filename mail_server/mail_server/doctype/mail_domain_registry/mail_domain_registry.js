// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Mail Domain Registry", {
	refresh(frm) {
		frm.trigger("set_queries");
	},

	set_queries(frm) {
		frm.set_query("domain_owner", () => ({
			query: "mail_server.utils.query.get_users_with_domain_owner_role",
			filters: {
				enabled: 1,
				role: "Domain Owner",
			},
		}));
	},
});
