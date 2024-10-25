// Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Outgoing Mail Log", {
	refresh(frm) {
		frm.trigger("add_actions");
	},

	add_actions(frm) {
		if (frm.doc.status === "Accepted") {
			frm.add_custom_button(
				__("Push to Queue"),
				() => {
					frm.trigger("push_to_queue");
				},
				__("Actions")
			);
		} else if (frm.doc.status === "Failed") {
			frm.add_custom_button(
				__("Retry"),
				() => {
					frm.trigger("retry_failed");
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
