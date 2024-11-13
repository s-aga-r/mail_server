from html import unescape
from typing import Literal

import frappe
from frappe import _

from mail_server.mail_server.doctype.spam_check_log.spam_check_log import create_spam_check_log


@frappe.whitelist(methods=["POST"], allow_guest=True)
def scan(message: str) -> dict:
	"""Returns the spam score, spamd response and scanning mode of the message"""

	try:
		message = get_unescaped_message(message)
		spam_log = create_spam_check_log(message)
		return {
			"spam_score": spam_log.spam_score,
			"spamd_response": spam_log.spamd_response,
			"scanning_mode": spam_log.scanning_mode,
		}
	except Exception:
		frappe.log_error(title=_("Spam Check Failed"), message=frappe.get_traceback())
		raise


@frappe.whitelist(methods=["POST"], allow_guest=True)
def is_spam(message: str, message_type: Literal["Inbound", "Outbound"] = "Outbound") -> bool:
	"""Returns True if the message is spam else False"""

	try:
		message = get_unescaped_message(message)
		spam_log = create_spam_check_log(message)
		return spam_log.is_spam(message_type)
	except Exception:
		frappe.log_error(title=_("Spam Check Failed"), message=frappe.get_traceback())
		raise


@frappe.whitelist(methods=["POST"], allow_guest=True)
def get_spam_score(message: str) -> float:
	"""Returns the spam score of the message"""

	try:
		message = get_unescaped_message(message)
		spam_log = create_spam_check_log(message)
		return spam_log.spam_score
	except Exception:
		frappe.log_error(title=_("Spam Check Failed"), message=frappe.get_traceback())
		raise


def get_unescaped_message(message: str) -> str:
	"""Returns the unescaped message"""

	return unescape(message)
