import json
import structlog
import aio_pika
from aio_pika.abc import AbstractRobustConnection, AbstractChannel
from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

# Module-level state — one connection, one channel for the lifetime of the app
_connection: AbstractRobustConnection | None = None
_channel: AbstractChannel | None = None

LOW_STOCK_EXCHANGE = "inventory"
LOW_STOCK_QUEUE    = "low_stock_alerts"


async def connect_rabbitmq() -> None:
    """
    Called once on app startup (lifespan).
    Creates a robust connection — aio_pika automatically reconnects
    if RabbitMQ restarts, without the app crashing.
    """
    global _connection, _channel

    _connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    _channel = await _connection.channel()

    # Declare the exchange — type=direct means messages route by exact key
    exchange = await _channel.declare_exchange(
        LOW_STOCK_EXCHANGE,
        aio_pika.ExchangeType.DIRECT,
        durable=True,   # survives RabbitMQ restarts
    )

    # Declare the queue
    queue = await _channel.declare_queue(
        LOW_STOCK_QUEUE,
        durable=True,   # survives RabbitMQ restarts
    )

    # Bind queue to exchange with routing key matching the queue name
    await queue.bind(exchange, routing_key=LOW_STOCK_QUEUE)

    logger.info("rabbitmq_connected", url=settings.rabbitmq_url)


async def close_rabbitmq() -> None:
    """Called once on app shutdown (lifespan)."""
    global _connection

    if _connection and not _connection.is_closed:
        await _connection.close()
        logger.info("rabbitmq_disconnected")


async def publish_low_stock_alert(
    product_id: str,
    sku: str,
    current_quantity: int,
    threshold: int,
) -> None:
    """
    Publishes a low stock alert message to RabbitMQ.
    Called by the stock service whenever quantity <= threshold.
    Fire-and-forget: the API does not wait for a consumer.
    """
    if _channel is None:
        logger.error("rabbitmq_publish_failed", reason="channel not initialised")
        return

    message_body = {
        "product_id": product_id,
        "sku": sku,
        "current_quantity": current_quantity,
        "threshold": threshold,
    }

    exchange = await _channel.get_exchange(LOW_STOCK_EXCHANGE)

    await exchange.publish(
        aio_pika.Message(
            body=json.dumps(message_body).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,  # survives RabbitMQ restart
            content_type="application/json",
        ),
        routing_key=LOW_STOCK_QUEUE,
    )

    logger.info(
        "low_stock_alert_published",
        product_id=product_id,
        sku=sku,
        current_quantity=current_quantity,
        threshold=threshold,
    )