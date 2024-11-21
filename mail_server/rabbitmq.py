import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

import frappe
import pika

if TYPE_CHECKING:
	from pika import BlockingConnection
	from pika.adapters.blocking_connection import BlockingChannel


OUTGOING_MAIL_QUEUE: str = "mail::outgoing_mails"
INCOMING_MAIL_QUEUE: str = "mail_agent::incoming_mails"
OUTGOING_MAIL_STATUS_QUEUE: str = "mail_agent::outgoing_mails_status"


class RabbitMQ:
	def __init__(
		self,
		host: str = "localhost",
		port: int = 5672,
		virtual_host: str = "/",
		username: str | None = None,
		password: str | None = None,
	) -> None:
		"""Initializes the RabbitMQ connection with the given parameters."""

		self.__host = host
		self.__port = port
		self.__virtual_host = virtual_host
		self.__username = username
		self.__password = password

		self._connection = None
		self._channel = None
		self._connect()

	def _connect(self) -> None:
		"""Connects to the RabbitMQ server."""

		max_retries = 3

		for attempt in range(max_retries):
			try:
				credentials = (
					pika.PlainCredentials(self.__username, self.__password)
					if self.__username and self.__password
					else None
				)
				parameters = pika.ConnectionParameters(
					host=self.__host,
					port=self.__port,
					virtual_host=self.__virtual_host,
					credentials=credentials,
					heartbeat=30,
					blocked_connection_timeout=60,
				)
				self._connection = pika.BlockingConnection(parameters)
				self._channel = self._connection.channel()
			except pika.exceptions.AMQPConnectionError:
				if attempt < (max_retries - 1):
					time.sleep(2**attempt)
				else:
					raise

	@property
	def connection(self) -> "BlockingConnection":
		"""Returns the connection to the RabbitMQ server."""

		if not self._connection or self._connection.is_closed:
			self._connect()

		return self._connection

	@property
	def channel(self) -> "BlockingChannel":
		"""Returns the channel to the RabbitMQ server."""

		if not self._connection or self._connection.is_closed:
			self._connect()
		elif not self._channel or self._channel.is_closed:
			self._channel = self._connection.channel()

		return self._channel

	def declare_queue(self, queue: str, max_priority: int = 0, durable: bool = True) -> None:
		"""Declares a queue with the given name and arguments."""

		arguments = {"x-max-priority": max_priority} if max_priority > 0 else None
		self.channel.queue_declare(queue=queue, arguments=arguments, durable=durable)

	def publish(
		self,
		routing_key: str,
		body: str,
		exchange: str = "",
		priority: int = 0,
		persistent: bool = True,
	) -> None:
		"""Publishes a message to the exchange with the given routing key."""

		properties = pika.BasicProperties(
			delivery_mode=pika.DeliveryMode.Persistent if persistent else None,
			priority=priority if priority > 0 else None,
		)
		self.channel.basic_publish(
			exchange=exchange,
			routing_key=routing_key,
			body=body,
			properties=properties,
		)

	def consume(
		self,
		queue: str,
		callback: callable,
		auto_ack: bool = False,
		prefetch_count: int = 0,
	) -> None:
		"""Consumes messages from the queue with the given callback."""

		if prefetch_count > 0:
			self.channel.basic_qos(prefetch_count=prefetch_count)

		self.channel.basic_consume(queue=queue, on_message_callback=callback, auto_ack=auto_ack)
		self.channel.start_consuming()

	def basic_get(
		self,
		queue: str,
		auto_ack: bool = False,
	) -> tuple[Any, int, bytes] | None:
		"""Gets a message from the queue and returns it."""

		method, properties, body = self.channel.basic_get(queue=queue, auto_ack=auto_ack)

		if method:
			return method, properties, body

		return None

	def _disconnect(self) -> None:
		"""Disconnects from the RabbitMQ server."""

		if self._connection and self._connection.is_open:
			self._connection.close()


class RabbitMQThreadLocal:
	def __init__(self, **kwargs) -> None:
		self._local = threading.local()
		self._kwargs = kwargs

	def get_connection(self) -> RabbitMQ:
		"""Returns a thread-local RabbitMQ connection."""

		if not hasattr(self._local, "connection"):
			self._local.connection = RabbitMQ(**self._kwargs)
		elif not self._local.connection.connection.is_open:
			self._local.connection._connect()

		return self._local.connection

	def close_connection(self) -> None:
		"""Closes the thread-local RabbitMQ connection."""

		if hasattr(self._local, "connection"):
			self._local.connection._disconnect()
			del self._local.connection


@contextmanager
def rabbitmq_context() -> Generator[RabbitMQ, None, None]:
	"""Context manager for RabbitMQ thread-local connections."""

	ms_settings = frappe.get_cached_doc("Mail Server Settings")
	rmq_local = RabbitMQThreadLocal(
		host=ms_settings.rmq_host,
		port=ms_settings.rmq_port,
		virtual_host=ms_settings.rmq_virtual_host,
		username=ms_settings.rmq_username,
		password=ms_settings.get_password("rmq_password") if ms_settings.rmq_password else None,
	)
	try:
		yield rmq_local.get_connection()
	finally:
		rmq_local.close_connection()
