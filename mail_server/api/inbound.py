from datetime import datetime
from typing import TYPE_CHECKING

import frappe
import pytz
from frappe import _
from frappe.utils import convert_utc_to_system_timezone, now

from mail_server.mail_server.doctype.mail_server_sync_history.mail_server_sync_history import (
	get_mail_server_sync_history,
)
from mail_server.utils.validation import (
	is_domain_registry_exists,
	validate_user_has_domain_owner_role,
	validate_user_is_domain_owner,
)

if TYPE_CHECKING:
	from mail_server.mail_server.doctype.mail_server_sync_history.mail_server_sync_history import (
		MailServerSyncHistory,
	)


from mail_server.utils import convert_to_utc


@frappe.whitelist(methods=["GET"])
def fetch(
	domain_name: str, limit: int = 100, last_synced_at: str | None = None
) -> dict[str, list[dict] | str]:
	"""Returns the incoming mails for the given domain."""

	user = frappe.session.user
	validate_user_has_domain_owner_role(user)
	is_domain_registry_exists(domain_name, raise_exception=True)
	validate_user_is_domain_owner(user, domain_name)

	source = get_source()
	last_synced_at = convert_to_system_timezone(last_synced_at)
	sync_history = get_mail_server_sync_history(source, frappe.session.user, domain_name)
	result = get_incoming_mails(domain_name, limit, last_synced_at or sync_history.last_synced_at)
	update_mail_server_sync_history(sync_history, result["last_synced_at"], result["last_synced_mail"])
	result["last_synced_at"] = convert_to_utc(result["last_synced_at"])

	return result


def get_source() -> str:
	"""Returns the source of the request."""

	return frappe.request.headers.get("X-Frappe-Mail-Site") or frappe.local.request_ip


def convert_to_system_timezone(last_synced_at: str) -> datetime | None:
	"""Converts the last_synced_at to system timezone."""

	if last_synced_at:
		dt = datetime.fromisoformat(last_synced_at)
		dt_utc = dt.astimezone(pytz.utc)
		return convert_utc_to_system_timezone(dt_utc)


def get_incoming_mails(
	domain_name: str,
	limit: int,
	last_synced_at: str | None = None,
) -> dict[str, list[dict] | str]:
	"""Returns the incoming mails for the given domain."""

	IML = frappe.qb.DocType("Incoming Mail Log")
	query = (
		frappe.qb.from_(IML)
		.select(
			IML.name.as_("oml"),
			IML.processed_at,
			IML.is_spam,
			IML.message,
		)
		.where((IML.is_rejected == 0) & (IML.status == "Accepted") & (IML.domain_name == domain_name))
		.orderby(IML.processed_at)
		.limit(limit)
	)

	if last_synced_at:
		query = query.where(IML.processed_at > last_synced_at)

	mails = query.run(as_dict=True)
	last_synced_at = mails[-1].processed_at if mails else now()
	last_synced_mail = mails[-1].oml if mails else None

	return {
		"mails": mails,
		"last_synced_at": last_synced_at,
		"last_synced_mail": last_synced_mail,
	}


def update_mail_server_sync_history(
	sync_history: "MailServerSyncHistory",
	last_synced_at: str,
	last_synced_mail: str | None = None,
) -> None:
	"""Update the last_synced_at in the Mail Server Sync History."""

	kwargs = {
		"last_synced_at": last_synced_at or now(),
	}

	if last_synced_mail:
		kwargs["last_synced_mail"] = last_synced_mail

	sync_history._db_set(**kwargs, commit=True)
