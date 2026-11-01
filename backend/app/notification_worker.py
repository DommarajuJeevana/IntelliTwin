"""
Background worker for IntelliTwin notifications.

Continuously checks scheduled notifications and changes notifications
whose scheduled time has arrived to "due".
"""

import asyncio

from app.notifications import mark_due_notifications


CHECK_INTERVAL_SECONDS = 5


async def notification_worker():
    """
    Continuously promote scheduled notifications to due notifications.
    """

    while True:
        try:
            await mark_due_notifications()
        except Exception as exc:
            print(f"[NotificationWorker] Error: {exc}")

        await asyncio.sleep(CHECK_INTERVAL_SECONDS)