# PRIME Scoreboard & Nudge

Internal tool for the **PRIME — Careers in the Age of AI** program (Foundation for a Path Forward × Coding in Colour). Renders a behavioral‑nudge email from live CRM data to keep the team's progress board accurate.

## What it is
- **Daily scoreboard email** — pulls live from the CRM and shows the team's numbers.
- **Progress nudge email** — drives staff to log outreach + update statuses in the CRM, surfacing the live numbers, a goal thermometer, a per‑person "party" view, and a one‑click "log" button. Anime/game‑HUD styling to make it motivating.

The board is only as accurate as what we log — this makes the goal, the gap, and the action visible in one place.

## 👋 Feedback welcome
We're improving this. **Open an Issue** here, or **reply to the email**. Specifically:
- Is the goal framing right?
- What would make **logging faster** (fewer fields, mobile, one‑tap)?
- What's missing or confusing?

## How it works
- `src/nudge_email.py` — render‑only. Pulls live CRM data (read‑only) and renders the nudge HTML.
- **No credentials, funder name, staff names, CRM ids, or local paths live in this repo** — they're read from a local, git‑ignored `.env`.

## Configure
Copy `.env.example` → `.env` (git‑ignored) and fill in the CRM org/module ids, the goal, and the staff list. Zoho credentials live in their own file referenced by `ZOHO_ENV`.

```bash
cp .env.example .env   # then edit .env
python3 src/nudge_email.py --name "First" --out /tmp/nudge.html
```

## Roadmap
See [ROADMAP.md](ROADMAP.md).

## Status
The nudge email is in active iteration (test sends only). Built with the lucy‑loop method.
