import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from main import handle_message, LOW_STOCK_EXCHANGE, LOW_STOCK_QUEUE, main


@pytest.mark.asyncio
async def test_handle_message_logs_low_stock_alert() -> None:
    body = {
        "product_id": "prd_123",
        "sku": "TSHIRT-001",
        "current_quantity": 8,
        "threshold": 10,
    }

    message = MagicMock()
    message.body = json.dumps(body).encode()

    process_cm = AsyncMock()
    process_cm.__aenter__.return_value = None
    process_cm.__aexit__.return_value = None
    message.process.return_value = process_cm

    with patch("main.log.info") as mock_info:
        await handle_message(message)

    mock_info.assert_any_call(
        "low_stock_alert_received",
        product_id="prd_123",
        sku="TSHIRT-001",
        current_quantity=8,
        threshold=10,
    )


@pytest.mark.asyncio
async def test_handle_message_logs_error_on_invalid_json() -> None:
    message = MagicMock()
    message.body = b"not-json"

    process_cm = AsyncMock()
    process_cm.__aenter__.return_value = None
    process_cm.__aexit__.return_value = None
    message.process.return_value = process_cm

    with patch("main.log.error") as mock_error:
        await handle_message(message)

    mock_error.assert_called_once()
    assert mock_error.call_args[0][0] == "message_processing_failed"


@pytest.mark.asyncio
async def test_main_declares_exchange_queue_and_consumer() -> None:
    mock_connection = AsyncMock()
    mock_connection.__aenter__.return_value = mock_connection
    mock_connection.__aexit__.return_value = None

    mock_channel = AsyncMock()
    mock_exchange = AsyncMock()
    mock_queue = AsyncMock()

    mock_connection.channel.return_value = mock_channel
    mock_channel.declare_exchange.return_value = mock_exchange
    mock_channel.declare_queue.return_value = mock_queue

    with patch("main.aio_pika.connect_robust", new=AsyncMock(return_value=mock_connection)), \
         patch("main.asyncio.Event") as mock_event_class, \
         patch("main.asyncio.get_event_loop") as mock_get_loop:

        mock_event = MagicMock()
        mock_event.wait = AsyncMock(return_value=None)
        mock_event.set = MagicMock()
        mock_event_class.return_value = mock_event

        mock_loop = MagicMock()
        mock_get_loop.return_value = mock_loop

        await main()

    mock_channel.set_qos.assert_awaited_once_with(prefetch_count=1)
    mock_channel.declare_exchange.assert_awaited_once_with(
        LOW_STOCK_EXCHANGE,
        pytest.importorskip("aio_pika").ExchangeType.DIRECT,
        durable=True,
    )
    mock_channel.declare_queue.assert_awaited_once_with(
        LOW_STOCK_QUEUE,
        durable=True,
    )
    mock_queue.bind.assert_awaited_once_with(
        mock_exchange,
        routing_key=LOW_STOCK_QUEUE,
    )
    mock_queue.consume.assert_awaited_once()