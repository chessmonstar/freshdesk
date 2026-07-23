"""Build the grounded prompt and call the Claude API to draft a suggested reply."""
import os
import anthropic

from . import config

with open(config.POLICIES_PATH, encoding="utf-8") as f:
    POLICIES = f.read()

SYSTEM = f"""You are a support-reply drafting assistant for Luna Cycle, an electric
dirt-bike and e-bike company. You write a DRAFT reply that a human agent will review
before sending to the customer. Match Luna's warm, concise, friendly agent voice.

Follow these rules strictly:
- Ground every factual claim in the POLICY KNOWLEDGE BASE or the RETRIEVED PAST CASES
  provided below. Do NOT invent prices, fees, dollar amounts, dates, links, or part
  numbers that are not present in that material.
- If a specific number/link/policy is needed but not provided, do NOT guess — write a
  short line telling the agent to confirm it (e.g. "[agent: confirm current fee]") and
  phrase the customer-facing text so it still reads naturally.
- Never explain how to derestrict/unlock a bike's speed. It is acceptable to say Luna
  can't provide those instructions for liability reasons and that third-party guides exist.
- For refunds, fee quotes, fraud/chargeback decisions, warranty approvals, battery-safety
  incidents, or legal/injury matters: do NOT resolve them. Draft an empathetic holding
  reply and add a clear "[ESCALATE: ...]" note for the agent.
- Keep it to a few sentences. Start with "Hi {{first_name}}," and end with a friendly
  sign-off line. Do not fabricate order status or tracking — if needed, say you'll check.
- Output ONLY the draft reply text. No preamble, no explanation of your reasoning.

POLICY KNOWLEDGE BASE:
{POLICIES}
"""


def build_user_prompt(ticket, cases):
    lines = []
    lines.append("INCOMING TICKET")
    lines.append(f"Model detected: {ticket.get('model','?')}")
    lines.append(f"Customer first name: {ticket.get('first_name') or 'there'}")
    lines.append(f"Subject: {ticket.get('subject','')}")
    lines.append(f"Message:\n{ticket.get('question','')}\n")
    lines.append("RETRIEVED PAST CASES (how Luna agents handled similar questions — use "
                 "for grounding, adapt; do not copy verbatim):")
    if not cases:
        lines.append("  (no close matches found — rely on the policy knowledge base and "
                     "hedge/escalate where unsure)")
    for i, c in enumerate(cases, 1):
        lines.append(f"[{i}] ({c.get('model','?')}) Q: {c['q']}")
        lines.append(f"    A: {c['a']}")
    lines.append("\nWrite the draft reply now.")
    return "\n".join(lines)


_client = None


def _client_lazy():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


def draft_reply(ticket, cases):
    msg = _client_lazy().messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=config.MAX_DRAFT_TOKENS,
        system=SYSTEM,
        messages=[{"role": "user", "content": build_user_prompt(ticket, cases)}],
    )
    parts = [b.text for b in msg.content if getattr(b, "type", "") == "text"]
    return "".join(parts).strip()
