import asyncio
import json
import signal
import structlog
import aio_pika
from pydantic_settings import BaseSettings, SettingsConfigDict


log = structlog.get_logger()


class Settings(BaseSettings):
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()

LOW_STOCK_EXCHANGE = "inventory"
LOW_STOCK_QUEUE = "low_stock_alerts"


async def handle_message(message: aio_pika.abc.AbstractIncomingMessage) -> None:
    """
    Processes a single low-stock alert message from RabbitMQ.
    Acknowledges the message only after successful processing.
    """
    async with message.process():
        try:
            body = json.loads(message.body.decode())

            log.info(
                "low_stock_alert_received",
                product_id=body.get("product_id"),
                sku=body.get("sku"),
                current_quantity=body.get("current_quantity"),
                threshold=body.get("threshold"),
            )

            # This is where you would send an email, Slack message,
            # trigger a reorder system, etc.
            # For now: structured logging is the action.

        except Exception as e:
            log.error("message_processing_failed", error=str(e))


async def main() -> None:
    """
    Entry point. Connects to RabbitMQ, declares the exchange and queue,
    and starts consuming messages indefinitely.
    """
    log.info("worker_starting", rabbitmq_url=settings.rabbitmq_url)

    connection = await aio_pika.connect_robust(settings.rabbitmq_url)

    async with connection:
        channel = await connection.channel()

        await channel.set_qos(prefetch_count=1)

        exchange = await channel.declare_exchange(
            LOW_STOCK_EXCHANGE,
            aio_pika.ExchangeType.DIRECT,
            durable=True,
        )

        queue = await channel.declare_queue(
            LOW_STOCK_QUEUE,
            durable=True,
        )

        await queue.bind(exchange, routing_key=LOW_STOCK_QUEUE)

        await queue.consume(handle_message)

        log.info("worker_ready", queue=LOW_STOCK_QUEUE)

        # Keep the worker alive until a shutdown signal is received
        stop_event = asyncio.Event()

        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop_event.set)

        await stop_event.wait()

    log.info("worker_stopped")


if __name__ == "__main__":
    asyncio.run(main())