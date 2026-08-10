"""
WhatsAppBusinessAI — Messaging Provider Abstraction (spec section 38)

    MessagingProvider (interface)
     |- WhatsAppCloudProvider   <- built
     |- TelegramProvider        <- future
     \- SMSProvider             <- future

Only WhatsApp is implemented; the interface exists so a future provider
doesn't require touching apps.messages or apps.conversations at all — they
only ever talk to `MessagingProvider.send_text_message`.
"""

import logging
from abc import ABC, abstractmethod
from typing import TypedDict

import requests
from django.conf import settings

logger = logging.getLogger("waba")


class SendResult(TypedDict):
    success: bool
    external_id: str | None
    error: str | None


class MessagingProvider(ABC):
    @abstractmethod
    def send_text_message(self, *, to: str, text: str) -> SendResult:
        """Send a plain text message to `to` (provider-specific address format)."""


class WhatsAppCloudProvider(MessagingProvider):
    """Thin client for the WhatsApp Cloud API (Meta Graph API)."""

    def __init__(
        self, *, phone_number_id: str, access_token: str, api_base_url: str | None = None
    ):
        self.phone_number_id = phone_number_id
        self.access_token = access_token
        self.api_base_url = api_base_url or settings.WHATSAPP_GRAPH_API_BASE_URL

    def send_text_message(self, *, to: str, text: str) -> SendResult:
        url = f"{self.api_base_url}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text},
        }
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=10)
        except requests.RequestException as exc:
            logger.warning("WhatsApp send failed (network): %s", exc)
            return SendResult(success=False, external_id=None, error=str(exc))

        try:
            data = response.json()
        except ValueError:
            data = {}

        if response.status_code >= 400:
            error_message = (data.get("error") or {}).get(
                "message", f"HTTP {response.status_code}"
            )
            logger.warning("WhatsApp send failed (API): %s", error_message)
            return SendResult(success=False, external_id=None, error=error_message)

        messages = data.get("messages") or []
        external_id = messages[0].get("id") if messages else None
        return SendResult(success=True, external_id=external_id, error=None)


def parse_webhook_payload(payload: dict) -> list[dict]:
    """
    Flattens a WhatsApp Cloud API webhook payload into a list of normalized
    inbound message events:
    {"phone_number_id", "wa_id", "contact_name", "message_id", "timestamp",
     "message_type", "text"}

    Only inbound *messages* are extracted (not delivery/read status
    updates — those arrive under the same `changes[].value` but without a
    `messages` key, and are silently skipped here; nothing currently
    consumes outbound delivery receipts).

    Deliberately tolerant of missing/unexpected fields — a malformed or
    partially-understood payload should degrade to "no events extracted",
    not raise, since this runs directly in the webhook request path.
    """
    events = []
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value", {}) or {}
            phone_number_id = (value.get("metadata") or {}).get("phone_number_id")
            contacts = value.get("contacts") or []
            contact_name = ""
            if contacts:
                contact_name = (contacts[0].get("profile") or {}).get("name", "")

            for message in value.get("messages", []) or []:
                message_type = message.get("type", "text")
                text = ""
                if message_type == "text":
                    text = (message.get("text") or {}).get("body", "")
                events.append(
                    {
                        "phone_number_id": phone_number_id,
                        "wa_id": message.get("from", ""),
                        "contact_name": contact_name,
                        "message_id": message.get("id", ""),
                        "timestamp": message.get("timestamp"),
                        "message_type": message_type,
                        "text": text,
                    }
                )
    return events
