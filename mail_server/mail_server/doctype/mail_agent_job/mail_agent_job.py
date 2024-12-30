# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now, time_diff_in_seconds

from mail_server.agent import AgentAPI


class MailAgentJob(Document):
	def validate(self) -> None:
		self.validate_agent()

	def after_insert(self) -> None:
		self.execute()

	def validate_agent(self) -> None:
		"""Validate if the agent is enabled."""
		if not frappe.get_cached_value("Mail Agent", self.agent, "enabled"):
			frappe.throw(_("Mail Agent {0} is disabled.").format(self.agent))

	def execute(self) -> None:
		"""Executes the job."""

		self.started_at = now()

		try:
			agent = frappe.get_cached_doc("Mail Agent", self.agent)

			if not agent.enabled:
				frappe.throw(_("Mail Agent {0} is disabled.").format(self.agent))

			agent_api = AgentAPI(
				agent.base_url,
				api_key=agent.get_password("api_key"),
				username=agent.username,
				password=agent.get_password("password"),
			)
			response = agent_api.request(
				method=self.method,
				endpoint=self.endpoint,
				json=self.request_data,
			)

			self.status = "Completed"
			if response.get("error"):
				self.status = "Failed"

			self.response_data = response
		except Exception:
			self.status = "Failed"
			self.error_log = frappe.get_traceback()
		finally:
			self.ended_at = now()
			self.duration = time_diff_in_seconds(self.ended_at, self.started_at)
			self.db_update()
