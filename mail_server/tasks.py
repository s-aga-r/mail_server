import frappe


def enqueue_push_emails_to_queue() -> None:
	"Called by the scheduler to enqueue the `push_emails_to_queue` job."

	from mail_server.mail_server.doctype.outgoing_mail_log.outgoing_mail_log import push_emails_to_queue
	from mail_server.utils import enqueue_job

	frappe.session.user = "Administrator"
	enqueue_job(push_emails_to_queue, queue="long")
