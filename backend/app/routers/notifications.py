"""
Notification API.

Notifications belong to the authenticated IntelliTwin user.

The first version exposes:
    GET  /api/notifications
    POST /api/notifications/{notification_id}/read
"""

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import require_auth
from app.notifications import (
    get_user_notifications,
    mark_notification_read,
)


router = APIRouter()


@router.get("")
async def list_notifications(
    include_read: bool = Query(default=False),
    user: dict = Depends(require_auth),
):
    notifications = await get_user_notifications(
        user["_id"],
        include_read=include_read,
    )

    return {
        "notifications": notifications,
    }


@router.post("/{notification_id}/read")
async def read_notification(
    notification_id: str,
    user: dict = Depends(require_auth),
):
    try:
        oid = ObjectId(notification_id)
    except Exception:
        raise HTTPException(
            status_code=404,
            detail="Notification not found.",
        )

    notification = await mark_notification_read(
        user["_id"],
        oid,
    )

    if not notification:
        raise HTTPException(
            status_code=404,
            detail="Notification not found.",
        )

    return {
        "notification": notification,
    }