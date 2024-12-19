from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import requests


class AgentAPI:
	"""Class to interact with the Agent."""

	def __init__(self, base_url: str, api_key: str) -> None:
		self.base_url = base_url
		self.__api_key = api_key
		self.__headers = {"Authorization": f"Bearer {self.__api_key}"}
		self.__session = requests.Session()

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
			json=json,
			files=files,
			headers=headers,
			timeout=timeout,
		)
		response.raise_for_status()

		return response.json()
