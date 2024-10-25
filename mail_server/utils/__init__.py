from collections.abc import Callable
from datetime import datetime

import dns.resolver
import frappe
import pytz
from frappe import _
from frappe.utils import get_datetime, get_system_timezone


def get_dns_record(fqdn: str, type: str = "A", raise_exception: bool = False) -> dns.resolver.Answer | None:
	"""Returns DNS record for the given FQDN and type."""

	err_msg = None

	try:
		resolver = dns.resolver.Resolver(configure=False)
		resolver.nameservers = [
			"1.1.1.1",
			"8.8.4.4",
			"8.8.8.8",
			"9.9.9.9",
		]

		r = resolver.resolve(fqdn, type)
		return r
	except dns.resolver.NXDOMAIN:
		err_msg = _("{0} does not exist.").format(frappe.bold(fqdn))
	except dns.resolver.NoAnswer:
		err_msg = _("No answer for {0}.").format(frappe.bold(fqdn))
	except dns.exception.DNSException as e:
		err_msg = _(str(e))

	if raise_exception and err_msg:
		frappe.throw(err_msg)


def verify_dns_record(fqdn: str, type: str, expected_value: str, debug: bool = False) -> bool:
	"""Verifies the DNS Record."""

	if result := get_dns_record(fqdn, type):
		for data in result:
			if data:
				if type == "MX":
					data = data.exchange
				data = data.to_text().replace('"', "")
				if type == "TXT" and "._domainkey." in fqdn:
					data = data.replace(" ", "")
					expected_value = expected_value.replace(" ", "")
				if data == expected_value:
					return True
			if debug:
				frappe.msgprint(f"Expected: {expected_value} Got: {data}")
	return False


def get_host_by_ip(ip_address: str, raise_exception: bool = False) -> str | None:
	"""Returns host for the given IP address."""

	import socket

	err_msg = None

	try:
		return socket.gethostbyaddr(ip_address)[0]
	except Exception as e:
		err_msg = _(str(e))

	if raise_exception and err_msg:
		frappe.throw(err_msg)


def enqueue_job(method: str | Callable, **kwargs) -> None:
	"""Enqueues a background job."""

	from frappe.utils.background_jobs import get_jobs

	site = frappe.local.site
	jobs = get_jobs(site=site)
	if not jobs or method not in jobs[site]:
		frappe.enqueue(method, **kwargs)


def convert_to_utc(date_time: datetime | str, from_timezone: str | None = None) -> "datetime":
	"""Converts the given datetime to UTC timezone."""

	dt = get_datetime(date_time)
	if dt.tzinfo is None:
		tz = pytz.timezone(from_timezone or get_system_timezone())
		dt = tz.localize(dt)

	return dt.astimezone(pytz.utc)


def parsedate_to_datetime(date_header: str, to_timezone: str | None = None) -> "datetime":
	"""Returns datetime object from parsed date header."""

	from email.utils import parsedate_to_datetime as parsedate

	dt = parsedate(date_header)
	if not dt:
		frappe.throw(_("Invalid date format: {0}").format(date_header))

	return dt.astimezone(pytz.timezone(to_timezone or get_system_timezone()))
