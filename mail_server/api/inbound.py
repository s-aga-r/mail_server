from datetime import datetime, timezone

import frappe
from frappe import _
from frappe.utils import convert_utc_to_system_timezone, now

from mail_server.utils import convert_to_utc, get_dmarc_address
from mail_server.utils.cache import get_user_owned_domains
from mail_server.utils.validation import validate_user_has_domain_owner_role


@frappe.whitelist(methods=["GET"])
def fetch(limit: int = 100, last_synced_at: str | None = None) -> dict[str, str | list[dict]]:
	"""Returns the incoming mails for the user's domains."""

	limit = min(max(limit, 1), 100)
	user = frappe.session.user
	validate_user_has_domain_owner_role(user)
	mail_domains = get_user_owned_domains(user)

	if not mail_domains:
		frappe.throw(_("User {0} does not associated with any domain.").format(user))

	last_synced_at = convert_to_system_timezone(last_synced_at)
	result = get_incoming_mails(mail_domains, limit, last_synced_at)
	result["last_synced_at"] = convert_to_utc(result["last_synced_at"])

	return result


def convert_to_system_timezone(last_synced_at: str) -> datetime | None:
	"""Converts the last_synced_at to system timezone."""

	if last_synced_at:
		dt = datetime.fromisoformat(last_synced_at)
		dt_utc = dt.astimezone(timezone.utc)
		return convert_utc_to_system_timezone(dt_utc)


def get_incoming_mails(
	mail_domains: list[str],
	limit: int,
	last_synced_at: str | datetime | None = None,
) -> dict[str, str | list[dict]]:
	"""Returns the incoming mails for the given domains."""

	IML = frappe.qb.DocType("Incoming Mail Log")
	query = (
		frappe.qb.from_(IML)
		.select(
			IML.name.as_("incoming_mail_log"),
			IML.processed_at,
			IML.is_spam,
			IML.message,
		)
		.where(
			(IML.is_rejected == 0)
			& (IML.status == "Accepted")
			& (IML.receiver != get_dmarc_address())
			& (IML.domain_name.isin(mail_domains))
		)
		.orderby(IML.processed_at)
		.limit(limit)
	)

	if last_synced_at:
		query = query.where(IML.processed_at > last_synced_at)

	mails = query.run(as_dict=True)
	last_synced_at = mails[-1].processed_at if mails else now()

	return {
		"mails": mails,
		"last_synced_at": last_synced_at,
	}
