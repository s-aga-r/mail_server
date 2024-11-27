// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Outgoing Mail Log", {
	refresh(frm) {
		frm.trigger("add_actions");
	},

	add_actions(frm) {
		if (["In Progress", "Blocked"].includes(frm.doc.status)) {
			frm.add_custom_button(
				__("Force Accept"),
				() => {
					frm.trigger("force_accept");
				},
				__("Actions")
			);
		} else if (frm.doc.status === "Accepted") {
			frm.add_custom_button(
				__("Push to Queue"),
				() => {
					frm.trigger("push_to_queue");
				},
				__("Actions")
			);
		} else if (frm.doc.status === "Failed" && frm.doc.failed_count < 3) {
			frm.add_custom_button(
				__("Retry"),
				() => {
					frm.trigger("retry_failed");
				},
				__("Actions")
			);
		} else if (["Queued (RMQ)", "Queued (Haraka)", "Deferred"].includes(frm.doc.status)) {
			frm.add_custom_button(
				__("Fetch Delivery Status"),
				() => {
					frm.trigger("fetch_and_update_delivery_statuses");
				},
				__("Actions")
			);
		} else if (
			frm.doc.status === "Bounced" &&
			has_common(frappe.user_roles, ["Administrator", "System Manager"])
		) {
			frm.add_custom_button(
				__("Retry"),
				() => {
					frm.trigger("retry_bounced");
				},
				__("Actions")
			);
		}
	},

	force_accept(frm) {
		frappe.call({
			doc: frm.doc,
			method: "force_accept",
			freeze: true,
			freeze_message: __("Force Accepting..."),
			callback: (r) => {
				if (!r.exc) {
					frm.refresh();
				}
			},
		});
	},

	push_to_queue(frm) {
		frappe.call({
			doc: frm.doc,
			method: "push_to_queue",
			freeze: true,
			freeze_message: __("Pushing to Queue..."),
			callback: (r) => {
				if (!r.exc) {
					frm.refresh();
				}
			},
		});
	},

	retry_failed(frm) {
		frappe.call({
			doc: frm.doc,
			method: "retry_failed",
			freeze: true,
			freeze_message: __("Retrying..."),
			callback: (r) => {
				if (!r.exc) {
					frm.refresh();
				}
			},
		});
	},

	fetch_and_update_delivery_statuses(frm) {
		frappe.call({
			method: "mail_server.tasks.enqueue_fetch_and_update_delivery_statuses",
			freeze: true,
			freeze_message: __("Creating Job..."),
			callback: () => {
				frappe.show_alert({
					message: __("{0} job has been created.", [
						__("Fetch Delivery Statuses").bold(),
					]),
					indicator: "green",
				});
			},
		});
	},

	retry_bounced(frm) {
		frappe.call({
			doc: frm.doc,
			method: "retry_bounced",
			freeze: true,
			freeze_message: __("Retrying..."),
			callback: (r) => {
				if (!r.exc) {
					frm.refresh();
				}
			},
		});
	},
});

frappe.ui.form.on("Mail Log Recipient", {
	validate_email_address(frm, cdt, cdn) {
		let recipient = locals[cdt][cdn];
		let email = recipient.email;

		if (!email) return;

		frappe.call({
			method: "mail_server.mail_server.doctype.outgoing_mail_log.outgoing_mail_log.validate_email_address",
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
