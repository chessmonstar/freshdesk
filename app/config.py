"""Configuration, all from environment variables (set these in Cloud Run)."""
import os


def _bool(name, default="false"):
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


# --- required ---
FRESHDESK_DOMAIN = os.getenv("FRESHDESK_DOMAIN", "").strip()      # e.g. "lunacycle"
FRESHDESK_API_KEY = os.getenv("FRESHDESK_API_KEY", "").strip()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()

# --- model / drafting ---
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5").strip()
MAX_CONTEXT_CASES = int(os.getenv("MAX_CONTEXT_CASES", "5"))
MAX_DRAFT_TOKENS = int(os.getenv("MAX_DRAFT_TOKENS", "700"))

# --- safety / behaviour switches ---
# Shared secret required on the webhook (sent as ?token=... or X-Webhook-Token header).
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "").strip()
# If "true", never posts to Freshdesk — logs the draft instead. Great for first tests.
DRY_RUN = _bool("DRY_RUN", "false")
# If set, only tickets in this Freshdesk group are processed (pilot mode). Empty = all.
PILOT_GROUP_ID = os.getenv("PILOT_GROUP_ID", "").strip()
# Marker put at the end of every AI note so we never double-post on the same ticket.
NOTE_MARKER = os.getenv("NOTE_MARKER", "⁣[luna-ai-draft]")

INDEX_PATH = os.getenv("INDEX_PATH", "data/qa_index.json.gz")
POLICIES_PATH = os.getenv("POLICIES_PATH", "app/policies.md")
RESOURCES_PATH = os.getenv("RESOURCES_PATH", "app/resources.md")


def freshdesk_base():
    return f"https://{FRESHDESK_DOMAIN}.freshdesk.com"


def missing_required():
    out = []
    if not FRESHDESK_DOMAIN:
        out.append("FRESHDESK_DOMAIN")
    if not FRESHDESK_API_KEY:
        out.append("FRESHDESK_API_KEY")
    if not ANTHROPIC_API_KEY:
        out.append("ANTHROPIC_API_KEY")
    return out
