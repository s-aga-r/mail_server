import gzip
import socket
import zipfile
from collections.abc import Callable
from datetime import datetime
from email.utils import parsedate_to_datetime as parsedate
from io import BytesIO

import dns.resolver
import frappe
import pytz
from frappe import _
from frappe.utils import convert_utc_to_system_timezone, get_datetime, get_datetime_str, get_system_timezone
from frappe.utils.background_jobs import get_jobs


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

	err_msg = None

	try:
		return socket.gethostbyaddr(ip_address)[0]
	except Exception as e:
		err_msg = _(str(e))

	if raise_exception and err_msg:
		frappe.throw(err_msg)


def enqueue_job(method: str | Callable, **kwargs) -> None:
	"""Enqueues a background job."""

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


def parsedate_to_datetime(date_header: str) -> "datetime":
	"""Returns datetime object from parsed date header."""

	utc_dt = parsedate(date_header)
	if not utc_dt:
		frappe.throw(_("Invalid date format: {0}").format(date_header))

	return convert_utc_to_system_timezone(utc_dt)


def parse_iso_datetime(
	datetime_str: str, to_timezone: str | None = None, as_str: bool = True
) -> str | datetime:
	"""Converts ISO datetime string to datetime object in given timezone."""

	if not to_timezone:
		to_timezone = get_system_timezone()

	dt = datetime.fromisoformat(datetime_str.replace("Z", "+00:00")).astimezone(pytz.timezone(to_timezone))

	return get_datetime_str(dt) if as_str else dt


def add_or_update_tzinfo(date_time: datetime | str, timezone: str | None = None) -> str:
	"""Adds or updates timezone to the datetime."""

	date_time = get_datetime(date_time)
	target_tz = pytz.timezone(timezone or get_system_timezone())

	if date_time.tzinfo is None:
		date_time = target_tz.localize(date_time)
	else:
		date_time = date_time.astimezone(target_tz)

	return str(date_time)


def load_compressed_file(file_path: str | None = None, file_data: bytes | None = None) -> str | None:
	"""Load content from a compressed file or bytes object."""

	if not file_path and not file_data:
		frappe.throw(_("Either file path or file data is required."))

	if file_path:
		if zipfile.is_zipfile(file_path):
			with zipfile.ZipFile(file_path, "r") as zip_file:
				file_name = zip_file.namelist()[0]
				with zip_file.open(file_name) as file:
					content = file.read().decode()
					return content
		else:
			with gzip.open(file_path, "rt") as gz_file:
				return gz_file.read()

	elif file_data:
		try:
			with zipfile.ZipFile(BytesIO(file_data), "r") as zip_file:
				file_name = zip_file.namelist()[0]
				with zip_file.open(file_name) as file:
					return file.read().decode()
		except zipfile.BadZipFile:
			pass

		try:
			with gzip.open(BytesIO(file_data), "rt") as gz_file:
				return gz_file.read()
		except OSError:
			pass

		frappe.throw(_("Failed to load content from the compressed file."))
