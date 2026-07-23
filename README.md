# Luna Cycle — AI Suggested-Reply Service

When a new Freshdesk ticket comes in, this service reads it, finds how your agents
handled similar questions in the past (from your own 38,900-case history), drafts a
reply with Claude, and posts it back on the ticket as a **private note** for an agent to
review, edit, and send. Nothing is ever sent to a customer automatically.

It runs on **Google Cloud Run** (scales to zero — near-free at your volume).

---

## What you need before starting

1. **An Anthropic API key** — from https://console.anthropic.com → API Keys. (Billing is
   on this key; at your volume expect a few dollars a month. See "Cost" below.)
2. **A Freshdesk API key** — in Freshdesk, click your avatar → **Profile Settings**; the
   API key is on the right. Your "domain" is the part before `.freshdesk.com`
   (e.g. `lunacycle`).
3. **A Google account** (you already have one) with a Google Cloud project and billing
   enabled — https://console.cloud.google.com. The free tier covers this workload.

You do NOT need to install anything on your computer — every command below runs in
**Cloud Shell**, a terminal built into the Google Cloud console (top-right `>_` icon).

---

## Step 1 — Get the code into Cloud Shell

Upload this whole `luna-support-agent` folder to Cloud Shell (Cloud Shell has an
"Upload" button in its `⋮` menu), or push it to a GitHub repo and `git clone` it there.
Then in Cloud Shell:

```bash
cd luna-support-agent
```

## Step 2 — Deploy to Cloud Run (one command)

```bash
gcloud run deploy luna-support-agent \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 1Gi \
  --set-env-vars "DRY_RUN=true,FRESHDESK_DOMAIN=lunacycle,CLAUDE_MODEL=claude-sonnet-5"
```

Google builds the container for you (no Dockerfile knowledge needed) and, when it
finishes, prints a **Service URL** like `https://luna-support-agent-xxxx.run.app`.
Keep that URL — your webhook target is that URL + `/webhook`.

> First deploy may ask to enable the Cloud Run / Cloud Build APIs — say yes.

## Step 3 — Add your secret keys

Set the API keys as env vars (kept out of the code):

```bash
gcloud run services update luna-support-agent --region us-central1 \
  --update-env-vars "ANTHROPIC_API_KEY=sk-ant-...,FRESHDESK_API_KEY=your_fd_key,WEBHOOK_SECRET=some-long-random-string"
```

Check it's healthy — open your Service URL in a browser (or `/healthz`). You should see
`"status":"ok"` and `index_pairs: 38898`. If it says `missing_config`, a key isn't set.

## Step 4 — Point Freshdesk at it

In Freshdesk: **Admin → Workflows → Automations → Ticket Creation** → **New Rule**.

- **When:** a ticket is created (add a condition like *Source is Email/Portal* if you like).
- **Action:** *Trigger Webhook* →
  - Request type: **POST**
  - URL: `https://YOUR-SERVICE-URL/webhook?token=YOUR_WEBHOOK_SECRET`
  - Content: **JSON**, body:
    ```json
    { "ticket_id": "{{ticket.id}}" }
    ```
- Save and activate.

## Step 5 — Test safely (DRY_RUN is on)

Create a test ticket in Freshdesk. Because `DRY_RUN=true`, the service will **log** the
draft instead of posting it. View the log:

```bash
gcloud run services logs read luna-support-agent --region us-central1 --limit 50
```

You'll see the drafted reply and which past tickets it used. Try a few ticket types.

## Step 6 — Go live

When you're happy, turn off dry-run so it posts real private notes. To be cautious, pilot
on ONE group first (find the group id under Admin → Groups):

```bash
gcloud run services update luna-support-agent --region us-central1 \
  --update-env-vars "DRY_RUN=false,PILOT_GROUP_ID=123456789"
```

Remove `PILOT_GROUP_ID` (set it blank) when you want it on for all tickets.

---

## Updating the answers later

- **Policies / facts** (fees, lead times, links): edit `app/policies.md` and re-run the
  Step 2 deploy command. The agent uses the new values immediately.
- **Fresh ticket history**: re-export the two CSVs, run
  `python build_index.py --tickets freshdesk_tickets.csv --conversations freshdesk_conversations.csv --out data/qa_index.json.gz`,
  then re-deploy.

## Cost (rough)

- **Cloud Run:** scales to zero; effectively free at your volume (well within free tier).
- **Claude API:** ~1 call per ticket. With `claude-sonnet-5` that's a small fraction of a
  cent to a couple cents per ticket depending on length; switch `CLAUDE_MODEL` to
  `claude-haiku-4-5-20251001` to cut it further. Check current pricing at
  https://www.anthropic.com/pricing.

## Safety built in

- Posts **private** notes only — never messages customers directly.
- Skips spam and auto-reply/bounce emails, and won't double-post on the same ticket.
- The draft is instructed to **hedge or escalate** (never invent) on fees, refunds,
  fraud, warranty approvals, and battery-safety cases, and never gives derestrict steps.
- `WEBHOOK_SECRET` blocks anyone else from calling your endpoint.

## Files

```
app/main.py        webhook + orchestration (filters, idempotency)
app/retrieval.py   BM25 search over the bundled index
app/drafting.py    prompt + Claude call (guardrails live here)
app/freshdesk.py   Freshdesk API (get ticket, post private note)
app/policies.md    <-- edit this to change Luna's policies/facts
app/config.py      env-var settings
data/qa_index.json.gz   bundled Q&A history (38,898 pairs)
build_index.py     regenerate the index from fresh CSVs
Dockerfile         used automatically by `gcloud run deploy --source .`
```
