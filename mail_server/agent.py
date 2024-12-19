from dataclasses import dataclass, field
from typing import Any, Literal
from urllib.parse import urljoin

import frappe
import requests
from frappe import _


@dataclass
class Principal:
	"""Dataclass to represent a principal."""

	name: str
	type: Literal["domain", "apiKey"]
	id: int = 0
	quota: int = 0
	secrets: list[str] = field(default_factory=list)
	emails: list[str] = field(default_factory=list)
	urls: list[str] = field(default_factory=list)
	memberOf: list[str] = field(default_factory=list)
	roles: list[str] = field(default_factory=list)
	lists: list[str] = field(default_factory=list)
	members: list[str] = field(default_factory=list)
	enabledPermissions: list[str] = field(default_factory=list)
	disabledPermissions: list[str] = field(default_factory=list)
	externalMembers: list[str] = field(default_factory=list)


class AgentAPI:
	"""Class to interact with the Agent."""

	def __init__(
		self,
		base_url: str,
		api_key: str | None = None,
		username: str | None = None,
		password: str | None = None,
	) -> None:
		self.base_url = base_url
		self.__api_key = api_key
		self.__username = username
		self.__password = password
		self.__session = requests.Session()

		self.__auth = None
		self.__headers = {}
		if self.__api_key:
			self.__headers.update({"Authorization": f"Bearer {self.__api_key}"})
		else:
			if not self.__username or not self.__password:
				frappe.throw(_("API Key or Username and Password is required."))

			self.__auth = (self.__username, self.__password)

	def request(
		self,
		method: str,
		endpoint: str,
		params: dict | None = None,
		data: dict | None = None,
		json: dict | None = None,
		files: dict | None = None,
		headers: dict[str, str] | None = None,
		timeout: int | tuple[int, int] = (60, 120),
	) -> Any | None:
		"""Makes an HTTP request to the Agent."""

		url = urljoin(self.base_url, endpoint)

		headers = headers or {}
		headers.update(self.__headers)

		if files:
			headers.pop("content-type", None)

		response = self.__session.request(
			method=method,
			url=url,
			params=params,
			data=data,
			headers=headers,
			files=files,
			auth=self.__auth,
			timeout=timeout,
			json=json,
		)
		response.raise_for_status()
		response = response.json()

		if response.get("error"):
			frappe.throw(response)

		return response


class AgentPrincipalAPI(AgentAPI):
	"""Class to interact with the Principal API of the Agent."""

	def create(self, principal: Principal) -> int:
		"""Create a principal in the Agent."""

		endpoint = "/api/principal"
		return self.request(method="POST", endpoint=endpoint, json=principal.__dict__)["data"]

	def read(self, type: str, limit: int = 10, page: int = 1) -> list[Principal]:
		"""Read all the principals from the Agent."""

		endpoint = "/api/principal"
		params = {"type": type, "limit": limit, "page": page}
		result = self.request(method="GET", params=params, endpoint=endpoint)["data"]
		return [Principal(**data) for data in result["items"]]
