"""Minimal Freshdesk API client: fetch a ticket, list notes, post a private note."""
import base64
import requests

from . import config

TIMEOUT = 20


def _auth_header():
    # Freshdesk uses HTTP Basic auth: API key as username, any string as password.
    raw = f"{config.FRESHDESK_API_KEY}:X".encode()
    return {"Authorization": "Basic " + base64.b64encode(raw).decode(),
            "Content-Type": "application/json"}


def get_ticket(ticket_id):
    url = f"{config.freshdesk_base()}/api/v2/tickets/{ticket_id}?include=requester"
    r = requests.get(url, headers=_auth_header(), timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def get_conversations(ticket_id):
    url = f"{config.freshdesk_base()}/api/v2/tickets/{ticket_id}/conversations"
    r = requests.get(url, headers=_auth_header(), timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def already_drafted(ticket_id):
    """True if we've already posted an AI note (idempotency guard)."""
    try:
        for c in get_conversations(ticket_id):
            body = (c.get("body_text") or c.get("body") or "")
            if config.NOTE_MARKER in body:
                return True
    except Exception:
        pass
    return False


def post_private_note(ticket_id, body_html):
    url = f"{config.freshdesk_base()}/api/v2/tickets/{ticket_id}/notes"
    payload = {"body": body_html, "private": True}
    r = requests.post(url, headers=_auth_header(), json=payload, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()
