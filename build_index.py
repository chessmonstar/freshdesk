#!/usr/bin/env python3
"""Build the compact Q&A retrieval index shipped inside the container.

Reads the two exported CSVs and writes data/qa_index.json.gz — a list of
{tid, q, a, model} pairs (customer question -> first agent public reply).
Run this again whenever you re-export fresher ticket data.

Usage:
  python build_index.py \
    --tickets "freshdesk_tickets.csv" \
    --conversations "freshdesk_conversations.csv" \
    --out data/qa_index.json.gz
"""
import argparse, csv, gzip, json, os, re
csv.field_size_limit(10**8)

Q_CAP, A_CAP = 320, 720


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickets", required=True)
    ap.add_argument("--conversations", required=True)
    ap.add_argument("--out", default="data/qa_index.json.gz")
    a = ap.parse_args()

    first_reply, first_inbound = {}, {}
    with open(a.conversations, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            tid = r["ticket_id"].strip(); created = r["created_at"]
            body = " ".join((r["body"] or "").split())
            if len(body) < 15:
                continue
            if r["incoming"].strip().lower() == "true":
                if tid not in first_inbound or created < first_inbound[tid][0]:
                    first_inbound[tid] = (created, body)
            elif r["private"].strip().lower() != "true":
                if tid not in first_reply or created < first_reply[tid][0]:
                    first_reply[tid] = (created, body)

    docs = []
    with open(a.tickets, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            tid = r["ticket_id"].strip()
            subj = (r["subject"] or "").strip(); desc = (r["description"] or "").strip()
            q = (subj + ". " + desc).strip(". ").strip()
            if len(q) < 12 and tid in first_inbound:
                q = first_inbound[tid][1]
            ans = first_reply.get(tid, (None, ""))[1]
            if len(q) < 12 or len(ans) < 25:
                continue
            docs.append({"tid": tid, "q": q[:Q_CAP], "a": ans[:A_CAP],
                         "model": model_of(subj + " " + desc)})

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with gzip.open(a.out, "wt", encoding="utf-8") as g:
        json.dump(docs, g)
    size = os.path.getsize(a.out) / 1e6
    print(f"wrote {a.out}: {len(docs)} Q&A pairs, {size:.1f} MB")


if __name__ == "__main__":
    main()
