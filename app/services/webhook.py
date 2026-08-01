import httpx
from app.core.logging import logger


async def fire_webhook(webhook_url: str, payload: dict) -> None:
    """Send an HTTP POST notification to the given webhook URL with the job result payload.

    This is a best-effort fire-and-forget call. Failures are logged but never raised,
    so they never affect the main ingestion pipeline result.
    """
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.post(webhook_url, json=payload)
            logger.info(
                "Webhook notification sent",
                webhook_url=webhook_url,
                status_code=resp.status_code,
            )
    except Exception as exc:
        logger.warning(
            "Webhook notification failed (best-effort, ignoring error)",
            webhook_url=webhook_url,
            error=str(exc),
        )
