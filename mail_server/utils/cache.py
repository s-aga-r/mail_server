from typing import Any

import frappe


def get_user_owned_domains(user: str) -> list:
	"""Returns the domains owned by the user."""

	def getter() -> list:
		MAIL_DOMAIN_REGISTRY = frappe.qb.DocType("Mail Domain Registry")
		return (
			frappe.qb.from_(MAIL_DOMAIN_REGISTRY)
			.select("name")
			.where((MAIL_DOMAIN_REGISTRY.enabled == 1) & (MAIL_DOMAIN_REGISTRY.domain_owner == user))
		).run(pluck="name")

	return _hget_or_hset(f"user|{user}", "owned_domains", getter)


def get_blacklist_for_ip_group(ip_group: str) -> list:
	"""Returns the blacklist for the IP group."""

	def getter() -> list:
		IP_BLACKLIST = frappe.qb.DocType("IP Blacklist")
		return (
			frappe.qb.from_(IP_BLACKLIST)
			.select(
				IP_BLACKLIST.name,
				IP_BLACKLIST.is_blacklisted,
				IP_BLACKLIST.ip_address,
				IP_BLACKLIST.ip_address_expanded,
				IP_BLACKLIST.blacklist_reason,
			)
			.where(IP_BLACKLIST.ip_group == ip_group)
		).run(as_dict=True)

	return _get_or_set(f"blacklist|{ip_group}", getter, expires_in_sec=24 * 60 * 60)
