// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Bounce History", {
	validate_email_address(frm) {
		let email = frm.doc.email;

		if (!email) return;

		frappe.call({
			method: "mail_server.utils.validation.validate_email_address_cache",
			args: {
				email: email,
			},
			freeze: true,
			freeze_message: __("Validating Email Address..."),
			callback: (r) => {
				if (!r.exc) {
					if (r.message) {
						frappe.show_alert({
							message: __("Email address {0} is valid.", [email.bold()]),
							indicator: "green",
						});
					} else {
						frappe.show_alert({
							message: __("Email address {0} is invalid.", [email.bold()]),
							indicator: "red",
						});
					}
				}
			},
		});
	},
});
