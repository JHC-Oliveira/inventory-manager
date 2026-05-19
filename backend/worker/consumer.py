import asyncio
import json
import structlog
import aio_pika
from aio_pika.abc import AbstractIncomingMessage
from app.config import get_settings

settings = get_settings()
logger = structlog.get_logger()

LOW_STOCK_EXCHANGE = "inventory"
LOW_STOCK_QUEUE    = "low_stock_alerts"


async def process_low_stock_alert(message: AbstractIncomingMessage) -> None:
    """
    Called once per message.
    Decodes the JSON body, logs the alert, acknowledges the message.
    """
    async with message.process(requeue=True):
        # requeue=True means: if an exception is raised inside this block,
        # nack the message and put it back in the queue instead of losing it.
        try:
            body = json.loads(message.body.decode())

            logger.warning(
                "low_stock_alert_received",
                product_id=body.get("product_id"),
                sku=body.get("sku"),
                current_quantity=body.get("current_quantity"),
                threshold=body.get("threshold"),
            )

            # Future phases: send email, call webhook, create DB record, etc.

        except Exception as e:
            logger.error(
                "low_stock_alert_processing_failed",
                error=str(e),
                raw_body=message.body.decode(errors="replace"),
            )
            raise   # re-raise so aio_pika nacks and requeues the message


async def main() -> None:
    """
    Entry point — connects to RabbitMQ, starts consuming.
    Runs forever until the process is stopped.
    """
    logger.info("worker_starting", queue=LOW_STOCK_QUEUE)

    # connect_robust automatically reconnects if RabbitMQ restarts
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)

    async with connection:
        channel = await connection.channel()

        # Declare exchange + queue — idempotent, safe to run even if they exist
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

        # prefetch_count=1 means: only give me one message at a time.
        # Don't send the next one until I ack the current one.
        await channel.set_qos(prefetch_count=1)

        logger.info("worker_ready", queue=LOW_STOCK_QUEUE)

        # Start consuming — this blocks here forever
        await queue.consume(process_low_stock_alert)

        # Keep the process alive
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())