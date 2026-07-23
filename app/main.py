"""Luna Cycle suggested-reply service.

Freshdesk fires a webhook on ticket creation -> this service fetches the ticket,
retrieves similar past cases, drafts a reply with Claude, and posts it back as a
PRIVATE note for the agent to review. Deploy on Google Cloud Run.
"""
import html
import logging
import re

from fastapi import FastAPI, Request, Response
from starlette.concurrency import run_in_threadpool

from . import config, freshdesk, drafting
from .retrieval import get_index

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("luna-agent")

app = FastAPI(title="Luna Cycle Suggested-Reply Service")

AUTO_REPLY_RE = re.compile(
    r"out of office|automatic reply|auto-?reply|delivery status notification|"
    r"undeliverable|mail delivery|read receipt|do not reply", re.I)


def model_of(text):
    t = (text or "").lower()
    if re.search(r"\bxxx\s*pro\b", t): return "XXX Pro"
    if re.search(r"\bxxx\b", t): return "Talaria XXX"
    if re.search(r"\bmx\s*5\b", t): return "MX5"
    if re.search(r"\bmx\s*4\b", t): return "MX4"
    if re.search(r"\bmx\s*3\b", t): return "MX3"
    if re.search(r"\bx2\.5\b", t): return "Luna X2.5"
    if re.search(r"\bx2\b", t): return "Luna X2"
    if re.search(r"\beclipse\b", t): return "Luna Eclipse"
    if re.search(r"luna\s+fixed", t): return "Luna Fixed"
    return "General/Other"


def extract_ticket_id(payload):
    """Freshdesk automation webhooks can be shaped a few ways; be tolerant."""
    if not isinstance(payload, dict):
        return None
    for key in ("ticket_id", "id", "display_id"):
        if payload.get(key):
            return str(payload[key])
    for wrap in ("freshdesk_webhook", "ticket", "data"):
        inner = payload.get(wrap)
        if isinstance(inner, dict):
            got = extract_ticket_id(inner)
            if got:
                return got
    return None


def note_html(draft, cases):
    safe = html.escape(draft).replace("\n", "<br>")
    refs = ", ".join(f"#{c['tid']}" for c in cases[:5]) or "policy KB only"
    return (
        "<div style='font-family:Arial,sans-serif'>"
        "<b>🤖 Suggested reply (AI draft — review &amp; edit before sending)</b>"
        "<hr>"
        f"<div>{safe}</div>"
        "<hr>"
        f"<span style='color:#888;font-size:12px'>Grounded in past tickets: {refs}. "
        "This is a draft, not sent to the customer.</span>"
        f"<span style='display:none'>{config.NOTE_MARKER}</span>"
        "</div>"
    )


@app.get("/")
@app.get("/healthz")
def health():
    miss = config.missing_required()
    idx = get_index(config.INDEX_PATH)
    return {"status": "ok" if not miss else "missing_config",
            "missing_env": miss, "index_pairs": idx.N,
            "model": config.CLAUDE_MODEL, "dry_run": config.DRY_RUN,
            "pilot_group": config.PILOT_GROUP_ID or None}


@app.post("/webhook")
async def webhook(request: Request):
    # 1) shared-secret check
    if config.WEBHOOK_SECRET:
        token = (request.query_params.get("token")
                 or request.headers.get("x-webhook-token", ""))
        if token != config.WEBHOOK_SECRET:
            return Response("forbidden", status_code=403)
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    # Blocking network work (Freshdesk + Claude) runs off the event loop.
    return await run_in_threadpool(process_ticket, payload)


def process_ticket(payload):
    miss = config.missing_required()
    if miss:
        log.error("missing config: %s", miss)
        return {"ok": False, "reason": "server_misconfigured", "missing": miss}

    tid = extract_ticket_id(payload)
    if not tid:
        return {"ok": False, "reason": "no_ticket_id_in_payload"}

    try:
        t = freshdesk.get_ticket(tid)
    except Exception as e:
        log.exception("get_ticket failed")
        return {"ok": False, "reason": f"get_ticket_error: {e}"}

    subject = t.get("subject") or ""
    desc = t.get("description_text") or t.get("description") or ""
    requester = (t.get("requester") or {})
    name = (requester.get("name") or "").strip()
    first_name = name.split()[0] if name else "there"

    # 2) filters
    if t.get("spam"):
        return {"ok": True, "skipped": "spam", "ticket": tid}
    if config.PILOT_GROUP_ID and str(t.get("group_id") or "") != config.PILOT_GROUP_ID:
        return {"ok": True, "skipped": "not_pilot_group", "ticket": tid}
    if AUTO_REPLY_RE.search(subject) or AUTO_REPLY_RE.search(desc[:200]):
        return {"ok": True, "skipped": "auto_reply", "ticket": tid}
    if len((subject + " " + desc).strip()) < 15:
        return {"ok": True, "skipped": "too_short", "ticket": tid}
    if freshdesk.already_drafted(tid):
        return {"ok": True, "skipped": "already_drafted", "ticket": tid}

    # 3) retrieve + draft
    query = f"{subject}. {desc}".strip()
    cases = get_index(config.INDEX_PATH).search(query, k=config.MAX_CONTEXT_CASES)
    ticket_ctx = {"subject": subject, "question": desc or subject,
                  "first_name": first_name, "model": model_of(subject + " " + desc)}
    try:
        draft = drafting.draft_reply(ticket_ctx, cases)
    except Exception as e:
        log.exception("draft failed")
        return {"ok": False, "reason": f"draft_error: {e}", "ticket": tid}

    if not draft:
        return {"ok": False, "reason": "empty_draft", "ticket": tid}

    # 4) post (or dry-run)
    if config.DRY_RUN:
        log.info("[DRY_RUN] ticket %s draft:\n%s", tid, draft)
        return {"ok": True, "dry_run": True, "ticket": tid,
                "cases": [c["tid"] for c in cases], "draft": draft}
    try:
        freshdesk.post_private_note(tid, note_html(draft, cases))
    except Exception as e:
        log.exception("post_note failed")
        return {"ok": False, "reason": f"post_note_error: {e}", "ticket": tid}

    log.info("posted AI draft note on ticket %s", tid)
    return {"ok": True, "ticket": tid, "cases": [c["tid"] for c in cases]}
