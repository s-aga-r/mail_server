from typing import Any

import frappe


def _get_or_set(name: str, getter: callable, expires_in_sec: int | None = 60 * 60) -> Any | None:
	"""Get or set a value in the cache."""

	value = frappe.cache.get_value(name)

	if not value:
		value = getter()
		frappe.cache.set_value(name, value, expires_in_sec=expires_in_sec)

	if isinstance(value, bytes):
		value = value.decode()

	return value


def get_root_domain_name() -> str | None:
	"""Returns the root domain name."""

	def getter() -> str | None:
		return frappe.db.get_single_value("Mail Server Settings", "root_domain_name")

	return _get_or_set("root_domain_name", getter, expires_in_sec=None)
