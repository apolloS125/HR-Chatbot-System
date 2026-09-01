import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import asyncpg
import httpx
from fastapi import HTTPException

from .core import LINE_CHANNEL_ACCESS_TOKEN


def announcement_date(value: datetime | None) -> str:
    value = value or datetime.now(ZoneInfo("Asia/Bangkok"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(ZoneInfo("Asia/Bangkok")).strftime("%d/%m/%Y · %H:%M น.")


def announcement_bubble(
    title: str,
    body: str,
    published_at: datetime | None = None,
) -> dict[str, object]:
    return {
        "type": "bubble",
        "size": "kilo",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#0F5132",
            "paddingAll": "20px",
            "contents": [
                {
                    "type": "box",
                    "layout": "horizontal",
                    "alignItems": "center",
                    "contents": [
                        {
                            "type": "box",
                            "layout": "vertical",
                            "backgroundColor": "#DDF5E7",
                            "cornerRadius": "12px",
                            "paddingAll": "6px",
                            "flex": 0,
                            "contents": [{
                                "type": "text",
                                "text": "HR UPDATE",
                                "color": "#0F5132",
                                "weight": "bold",
                                "size": "xxs",
                            }],
                        },
                        {
                            "type": "text",
                            "text": announcement_date(published_at),
                            "color": "#DDF5E7",
                            "size": "xxs",
                            "align": "end",
                            "gravity": "center",
                        },
                    ],
                },
                {
                    "type": "text",
                    "text": "ประกาศบริษัท",
                    "color": "#FFFFFF",
                    "weight": "bold",
                    "size": "xl",
                    "margin": "lg",
                },
            ],
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "22px",
            "contents": [
                {
                    "type": "text",
                    "text": title,
                    "weight": "bold",
                    "size": "xxl",
                    "color": "#17251E",
                    "wrap": True,
                },
                {"type": "separator", "color": "#DDE8E1", "margin": "xl"},
                {
                    "type": "text",
                    "text": body,
                    "size": "md",
                    "color": "#46544C",
                    "wrap": True,
                    "margin": "xl",
                },
            ],
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "paddingAll": "18px",
            "backgroundColor": "#F3F7F4",
            "contents": [
                {
                    "type": "button",
                    "style": "primary",
                    "height": "sm",
                    "color": "#0B8F50",
                    "action": {
                        "type": "message",
                        "label": "ดูประกาศล่าสุด",
                        "text": "ประกาศ",
                    },
                },
                {
                    "type": "text",
                    "text": "ฝ่ายทรัพยากรบุคคล",
                    "size": "xxs",
                    "color": "#708078",
                    "align": "center",
                    "margin": "md",
                },
            ],
        },
    }


def announcement_message(
    title: str,
    body: str,
    published_at: datetime | None = None,
) -> dict[str, object]:
    return {
        "type": "flex",
        "altText": f"ประกาศบริษัท: {title}"[:400],
        "contents": announcement_bubble(title, body, published_at),
    }


def announcement_carousel(rows: list[asyncpg.Record]) -> dict[str, object]:
    bubbles = [
        announcement_bubble(row["title"], row["body"], row["published_at"])
        for row in rows
    ]
    return {
        "type": "flex",
        "altText": "ประกาศล่าสุดจากบริษัท",
        "contents": bubbles[0] if len(bubbles) == 1 else {"type": "carousel", "contents": bubbles},
    }


async def reply_line(reply_token: str, message: str | dict[str, object]) -> None:
    if not LINE_CHANNEL_ACCESS_TOKEN:
        return
    line_message = {"type": "text", "text": message[:5000]} if isinstance(message, str) else message
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            "https://api.line.me/v2/bot/message/reply",
            headers={"Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"},
            json={"replyToken": reply_token, "messages": [line_message]},
        )
        response.raise_for_status()


async def multicast_line(user_ids: list[str], message: dict[str, object]) -> None:
    if not LINE_CHANNEL_ACCESS_TOKEN:
        raise HTTPException(status_code=503, detail="LINE Messaging API is not configured")
    async with httpx.AsyncClient(timeout=15) as client:
        for offset in range(0, len(user_ids), 500):
            response = await client.post(
                "https://api.line.me/v2/bot/message/multicast",
                headers={
                    "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}",
                    "X-Line-Retry-Key": str(uuid.uuid4()),
                },
                json={"to": user_ids[offset:offset + 500], "messages": [message]},
            )
            response.raise_for_status()
