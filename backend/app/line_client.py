import uuid

import asyncpg
import httpx
from fastapi import HTTPException

from .core import LINE_CHANNEL_ACCESS_TOKEN


def announcement_bubble(title: str, body: str) -> dict[str, object]:
    return {
        "type": "bubble",
        "header": {
            "type": "box",
            "layout": "vertical",
            "backgroundColor": "#0B8F50",
            "paddingAll": "18px",
            "contents": [{
                "type": "text",
                "text": "ประกาศบริษัท",
                "color": "#FFFFFF",
                "weight": "bold",
                "size": "sm",
            }],
        },
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "paddingAll": "20px",
            "contents": [
                {"type": "text", "text": title, "weight": "bold", "size": "xl", "wrap": True},
                {"type": "separator", "color": "#DDE8E1"},
                {"type": "text", "text": body, "size": "md", "color": "#46544C", "wrap": True},
            ],
        },
        "footer": {
            "type": "box",
            "layout": "vertical",
            "paddingAll": "14px",
            "backgroundColor": "#F3F7F4",
            "contents": [{
                "type": "text",
                "text": "ฝ่ายทรัพยากรบุคคล",
                "size": "xs",
                "color": "#708078",
                "align": "end",
            }],
        },
    }


def announcement_message(title: str, body: str) -> dict[str, object]:
    return {
        "type": "flex",
        "altText": f"ประกาศบริษัท: {title}"[:400],
        "contents": announcement_bubble(title, body),
    }


def announcement_carousel(rows: list[asyncpg.Record]) -> dict[str, object]:
    bubbles = [announcement_bubble(row["title"], row["body"]) for row in rows]
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
