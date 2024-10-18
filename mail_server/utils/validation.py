import re


def is_valid_host(host: str) -> bool:
	"""Returns True if the host is a valid hostname else False."""

	return bool(re.compile(r"^[a-zA-Z0-9_-]+$").match(host))
