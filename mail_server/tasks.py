import frappe

from mail_server.utils import enqueue_job


def enqueue_push_emails_to_queue() -> None:
	"Called by the scheduler to enqueue the `push_emails_to_queue` job."

	from mail_server.mail_server.doctype.outgoing_mail_log.outgoing_mail_log import push_emails_to_queue

	frappe.session.user = "Administrator"
	enqueue_job(push_emails_to_queue, queue="long")


@frappe.whitelist()
def enqueue_fetch_and_update_delivery_statuses() -> None:
	"Called by the scheduler to enqueue the `fetch_and_update_delivery_statuses` job."

	from mail_server.mail_server.doctype.outgoing_mail_log.outgoing_mail_log import (
		fetch_and_update_delivery_statuses,
	)

	frappe.session.user = "Administrator"
	enqueue_job(fetch_and_update_delivery_statuses, queue="long")


@frappe.whitelist()
def enqueue_fetch_emails_from_queue() -> None:
	"Called by the scheduler to enqueue the `fetch_emails_from_queue` job."

	from mail_server.mail_server.doctype.incoming_mail_log.incoming_mail_log import fetch_emails_from_queue

	frappe.session.user = "Administrator"
	enqueue_job(fetch_emails_from_queue, queue="long")
