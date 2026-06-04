#!/usr/bin/env python3
"""PRIME progress-nudge email v2 — render-only, sandbox (does NOT touch the live board/state).
Pulls live Zoho CRM (read-only) and renders a behavioral-nudge email that drives officers to log
outreach + update student status. Improvements over v1: embedded live numbers, 30-jobs goal
thermometer, the 7-day gap (loss framing), per-officer leaderboard (accountability/social proof),
single primary CTA, mobile-first + dark-mode-aware, hidden preheader. Personalizes by --name.

Usage: python3 nudge_email.py --name Yusuf --out /tmp/prime-nudge-v2.html
Reads creds from the live primecareers .env (read-only). Writes ONLY to --out. No live STATE/LOG writes.
"""
import json, subprocess, re, sys, argparse, os
from collections import Counter
from datetime import date
from pathlib import Path

# Org-specific config — read from a local, git-ignored config (prime-nudge-lab/.env) or env vars, so the
# PUBLIC repo ships only generic placeholders (no funder name / staff names / CRM ids / local paths).
_CFG = {}
_CFG_PATH = Path(__file__).resolve().parent.parent / ".env"
if _CFG_PATH.exists():
    for _l in _CFG_PATH.read_text().splitlines():
        _mm = re.match(r'^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*?)\s*$', _l)
        if _mm:
            _CFG[_mm.group(1)] = re.sub(r'^["\']|["\']$', '', _mm.group(2))

def _cv(key, default):
    return os.getenv(key) or _CFG.get(key) or default

ENV = Path(_cv("ZOHO_ENV", "./.zoho.env"))   # file holding ZOHO_CLIENT_ID/SECRET/REFRESH_TOKEN (read-only)
ORG = _cv("ZOHO_ORG", "YOUR_ORG_ID")
OUTREACH_MODULE = _cv("OUTREACH_MODULE", "CustomModuleXX")
STUDENTS_MODULE = _cv("STUDENTS_MODULE", "CustomModuleXX")
STUDENTS_VIEW = _cv("STUDENTS_VIEW", "VIEW_ID")
GOAL_REFUGEES = int(_cv("GOAL_TARGET", "40"))
GOAL_LABEL = _cv("GOAL_LABEL", "Refugee-employment goal")
OFFICERS = [o.strip() for o in _cv("OFFICERS", "Officer 1,Officer 2,Officer 3,Officer 4").split(",") if o.strip()]
REPO_URL = _cv("REPO_URL", "https://github.com/Foundation4ward/prime-scoreboard")
CREATE_OUTREACH = f"https://crm.zoho.com/crm/org{ORG}/tab/{OUTREACH_MODULE}/create"
STUDENTS_LIST = f"https://crm.zoho.com/crm/org{ORG}/tab/{STUDENTS_MODULE}/custom-view/{STUDENTS_VIEW}/list"

# Tomo's daily nugget — one rotates in per day (date-based, stable within a day). AI tips + did-you-knows
# + motivational lines, kept fabrication-free (no invented stats; quotes are well-attributed or proverbs).
NUGGETS = [
    "&#128161; AI tip: paste a job posting into an AI and ask for the top 5 skills to put on the candidate&rsquo;s CV.",
    "&#128161; AI tip: ask an AI to rewrite a CV bullet to open with a strong action verb and a real result.",
    "&#128161; AI tip: have an AI draft three outreach messages, then send the one that sounds most human.",
    "&#128161; AI tip: before an interview, ask an AI for the likely questions for that exact role and company.",
    "&#128161; AI tip: ask an AI to pull the keywords from a posting so the CV gets past automated screening.",
    "&#128161; AI tip: turn a long job description into a one-line &lsquo;what they really want&rsquo; summary to brief a candidate fast.",
    "&#128161; AI tip: ask an AI to polish a CV into clear, confident English while keeping the candidate&rsquo;s own voice.",
    "&#128161; AI tip: have an AI build a 30-second &lsquo;tell me about yourself&rsquo; for the role, then practice it out loud.",
    "&#10024; Did you know: many jobs are never advertised &mdash; they&rsquo;re filled through referrals and outreach. The contacts you log are how people get found.",
    "&#10024; Did you know: a warm follow-up often reopens a stalled conversation &mdash; logging the first contact is what reminds us to send it.",
    "&#10024; Did you know: a personal referral can jump a candidate past the r&eacute;sum&eacute; pile &mdash; that&rsquo;s the door your outreach opens.",
    "&#10024; Did you know: multilingual, cross-border experience is a real strength &mdash; worth surfacing on every CV you help build.",
    "&#10024; Did you know: clear notes on each contact make the next officer&rsquo;s call easier &mdash; your log is a gift to the whole team.",
    "&#10024; Did you know: practising answers out loud beats re-reading them &mdash; a quick mock interview before the real one helps.",
    "&#128172; &ldquo;Alone we can do so little; together we can do so much.&rdquo; &mdash; Helen Keller",
    "&#128172; &ldquo;It always seems impossible until it&rsquo;s done.&rdquo; &mdash; Nelson Mandela",
    "&#128172; &ldquo;A journey of a thousand miles begins with a single step.&rdquo; &mdash; Lao Tzu",
    "&#128172; &ldquo;The best way to predict the future is to invent it.&rdquo; &mdash; Alan Kay",
    "&#128172; &ldquo;If you want to go fast, go alone. If you want to go far, go together.&rdquo; &mdash; proverb",
    "&#128172; Small steps, repeated daily, cover big distances.",
    "&#128172; Progress over perfection &mdash; one logged call still moves the board.",
    "&#128172; Every conversation you log is someone one step closer to a job.",
    "&#128172; Consistency beats intensity &mdash; a little every day wins.",
    "&#128172; Not perfect today &mdash; just one step better than yesterday.",
]


def load_env():
    env = {}
    for line in ENV.read_text().splitlines():
        m = re.match(r'^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*?)\s*$', line)
        if m:
            env[m.group(1)] = re.sub(r'^["\']|["\']$', '', m.group(2))
    return env


E = load_env()
ACC = E["ZOHO_ACCOUNTS_DOMAIN"].rstrip("/")
API = E["ZOHO_API_DOMAIN"].rstrip("/")


def curl(args):
    r = subprocess.run(["curl", "-s", *args], capture_output=True, text=True, timeout=60)
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"_raw": r.stdout[:200]}


def token():
    d = curl([f"{ACC}/oauth/v2/token", "-d", "grant_type=refresh_token",
              "-d", f"client_id={E['ZOHO_CLIENT_ID']}", "-d", f"client_secret={E['ZOHO_CLIENT_SECRET']}",
              "-d", f"refresh_token={E['ZOHO_REFRESH_TOKEN']}"])
    t = d.get("access_token")
    if not t:
        sys.exit("TOKEN FAIL: %s" % d)
    return t


def fetch_all(tok, module, fields):
    recs, page = [], 1
    while page <= 25:
        d = curl([f"{API}/crm/v6/{module}?fields={fields}&per_page=200&page={page}",
                  "-H", f"Authorization: Zoho-oauthtoken {tok}"])
        recs += (d.get("data") or [])
        if not (d.get("info") or {}).get("more_records"):
            break
        page += 1
    return recs


def gather():
    tok = token()
    ts = fetch_all(tok, "Test_Student", "Status,Refugee,Forcibly_Displaced")
    pc = fetch_all(tok, "PRIME_Clients", "Status,Job_Placed")
    oa = fetch_all(tok, "Outreach_Activities", "Owner1,Type,Date,Success")
    c = Counter((r.get("Status") or "None") for r in ts)
    emp = [r for r in ts if r.get("Status") == "Employed"]
    emp_rfd = sum(1 for r in emp if r.get("Refugee") or r.get("Forcibly_Displaced"))
    enrolled = Counter((r.get("Status") or "None") for r in pc).get("Enrolled", 0)
    active = c.get("Job Seeking", 0) + c.get("Studying", 0) + enrolled
    off_n = Counter((r.get("Owner1") or "Unassigned") for r in oa)
    off_s = Counter((r.get("Owner1") or "Unassigned") for r in oa if r.get("Success"))

    def pdate(s):
        try:
            return date.fromisoformat((s or "")[:10])
        except Exception:
            return None
    today = date.today()
    dates = [d for d in (pdate(r.get("Date")) for r in oa) if d]
    last7 = sum(1 for d in dates if (today - d).days <= 7)
    recent = max(dates).isoformat() if dates else "none"
    return {"emp_rfd": emp_rfd, "emp_total": len(emp), "active": active,
            "prospective": c.get("Prospective", 0), "enrolled": enrolled,
            "oa_total": len(oa), "last7": last7, "recent": recent,
            "off_n": dict(off_n), "off_s": dict(off_s)}


def render(name, m):
    pct = min(100, round(100 * m["emp_rfd"] / GOAL_REFUGEES)) if GOAL_REFUGEES else 0
    gap = GOAL_REFUGEES - m["emp_rfd"]
    # per-officer leaderboard rows (sorted desc), bold the recipient if they're an officer
    rows = ""
    omax = max(list(m["off_n"].get(o, 0) for o in OFFICERS) + [1])
    medals = ["\U0001F947", "\U0001F948", "\U0001F949"]  # gold / silver / bronze
    for i, o in enumerate(sorted(OFFICERS, key=lambda x: -m["off_n"].get(x, 0))):
        n = m["off_n"].get(o, 0)
        s = m["off_s"].get(o, 0)
        w = max(3, int(n / omax * 100)) if n else 2
        mine = (o.lower() == (name or "").strip().lower())
        badge = (medals[i] + " ") if (i < 3 and n > 0) else ""
        lab = f'<b>{badge}{o}</b>' if mine else f'{badge}{o}'
        rows += (f'<tr><td style="padding:5px 10px 5px 0;font-size:13px;color:#374151;white-space:nowrap;">{lab}</td>'
                 f'<td style="width:100%;padding:5px 0;"><div style="background:#ece9fb;border-radius:999px;"><div style="width:{w}%;background:linear-gradient(90deg,#8b5cf6,#22d3ee);height:14px;border-radius:999px;"></div></div></td>'
                 f'<td style="padding:5px 0 5px 10px;font-size:13px;font-weight:700;color:#0f172a;text-align:right;white-space:nowrap;">{n} <span style="color:#059669;font-weight:600;">&middot; {s}&#10003;</span></td></tr>')

    pre = f"Weekly streak at {m['last7']} &mdash; {GOAL_REFUGEES - m['emp_rfd']} to go, together. Drop a +1. &#10024;"
    nugget = NUGGETS[date.today().toordinal() % len(NUGGETS)]   # rotates daily, stable within the day

    head = ('<tr><td style="background:#6d28d9;background:linear-gradient(135deg,#6d28d9 0%,#7c3aed 45%,#22d3ee 100%);padding:26px 24px 24px;">'
            '<div style="font-size:11px;font-weight:800;letter-spacing:.14em;color:rgba(255,255,255,.82);text-transform:uppercase;">&#9656; PRIME &middot; daily quest &#10024;</div>'
            '<div style="color:#ffffff;font-size:27px;font-weight:800;font-style:italic;line-height:1.05;margin-top:8px;text-shadow:0 2px 14px rgba(34,211,238,.5);">LEVEL UP THE BOARD</div>'
            '<div style="color:rgba(255,255,255,.92);font-size:13px;margin-top:7px;">A note from Yusuf &middot; we clear this one as a team &#10024;</div></td></tr>')

    intro = (f'<tr><td style="padding:22px 24px 6px;color:#374151;font-size:15px;line-height:1.6;">'
             '<p style="margin:0 0 12px;">Hi Team!</p>'
             f'<p style="margin:0;">Our daily scoreboard pulls <b>live</b> from Zoho, so it only reflects what <b>we</b> log &mdash; as a team. '
             f'Here&rsquo;s where we all stand right now, and how we close the gap together.</p></td></tr>')

    # the gap framed as a streak/combo (loss framing, game language)
    gapcard = ('<tr><td style="padding:18px 24px 4px;">'
               '<div style="background:#fff7ed;background:linear-gradient(135deg,#fff7ed,#ffedd5);border:1px solid #fdba74;border-radius:16px;padding:15px 18px;box-shadow:0 6px 18px rgba(234,88,12,.12);">'
               '<table cellpadding="0" cellspacing="0" style="width:100%;border-collapse:collapse;"><tr>'
               f'<td style="vertical-align:middle;width:62px;"><div style="font-size:42px;font-weight:800;color:#ea580c;line-height:1;">{m["last7"]}</div></td>'
               '<td style="vertical-align:middle;padding-left:8px;">'
               '<div style="font-size:11px;font-weight:800;letter-spacing:.1em;color:#c2410c;text-transform:uppercase;">&#9889; weekly streak</div>'
               '<div style="font-size:13px;color:#9a3412;font-weight:600;margin-top:3px;">logged in the last 7 days</div>'
               f'<div style="font-size:12px;color:#b45309;margin-top:2px;">last log {m["recent"]} &middot; every call restarts the combo</div>'
               '</td></tr></table></div></td></tr>')

    # main quest — XP / progress bar
    goal = ('<tr><td style="padding:16px 24px 4px;">'
            f'<div style="font-size:11px;font-weight:800;color:#6d28d9;text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px;">&#127919; main quest &middot; {GOAL_LABEL}</div>'
            '<div style="background:#ede9fe;border-radius:999px;height:26px;">'
            f'<div style="width:{max(8, pct)}%;background:linear-gradient(90deg,#059669,#10b981);height:26px;border-radius:999px;box-shadow:0 0 14px rgba(16,185,129,.55);"></div></div>'
            f'<div style="font-size:14px;color:#374151;margin-top:8px;"><b style="color:#059669;">{m["emp_rfd"]}</b> / {GOAL_REFUGEES} refugees employed &nbsp;&#9656;&nbsp; <b>{gap}</b> to go &nbsp;&#9656;&nbsp; {pct}%</div></td></tr>')

    # party stats — KPI tiles
    def kpi(v, lab, col, bg):
        return (f'<td style="width:33.3%;padding:5px;vertical-align:top;">'
                f'<div style="background:{bg};border:1px solid {col}26;border-radius:14px;padding:13px 6px;text-align:center;">'
                f'<div style="font-size:27px;font-weight:800;color:{col};line-height:1;">{v}</div>'
                f'<div style="font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:.06em;margin-top:5px;font-weight:700;">{lab}</div></div></td>')
    snap = ('<tr><td style="padding:14px 20px 4px;">'
            '<div style="font-size:11px;font-weight:800;color:#6d28d9;text-transform:uppercase;letter-spacing:.08em;margin:0 5px 8px;">&#127918; party stats</div>'
            '<table cellpadding="0" cellspacing="0" style="width:100%;border-collapse:collapse;"><tr>'
            + kpi(m["active"], "Active", "#2563eb", "#eff6ff") + kpi(m["prospective"], "Pipeline", "#d97706", "#fffbeb")
            + kpi(m["emp_total"], "Employed", "#059669", "#ecfdf5") + '</tr></table></td></tr>')

    # leaderboard
    board = ('<tr><td style="padding:16px 24px 4px;">'
             '<div style="font-size:11px;font-weight:800;color:#6d28d9;text-transform:uppercase;letter-spacing:.08em;margin-bottom:10px;">&#129309; our party &middot; every log = XP (&#10003; = wins)</div>'
             '<table cellpadding="0" cellspacing="0" style="width:100%;border-collapse:collapse;">' + rows + '</table>'
             f'<div style="font-size:12px;color:#64748b;margin-top:9px;">Party total: <b style="color:#6d28d9;">{m["oa_total"]}</b> XP logged &nbsp;&#9656;&nbsp; keep it climbing.</div>'
             '</td></tr>')

    # CTA
    cta = ('<tr><td align="center" style="padding:20px 24px 4px;">'
           f'<a href="{CREATE_OUTREACH}" style="display:inline-block;background:#7c3aed;background:linear-gradient(135deg,#7c3aed,#06b6d4);color:#ffffff;font-size:17px;font-weight:800;text-decoration:none;padding:16px 36px;border-radius:14px;box-shadow:0 10px 24px rgba(124,58,237,.4);">&#9889; Log outreach in Zoho</a>'
           '<div style="font-size:12px;color:#64748b;margin-top:9px;">every log = <b style="color:#6d28d9;">+1</b> on the board</div>'
           '</td></tr>'
           f'<tr><td align="center" style="padding:2px 24px 16px;"><a href="{STUDENTS_LIST}" style="color:#6d28d9;font-size:13px;text-decoration:none;font-weight:700;">Update a student&rsquo;s status &rarr;</a></td></tr>')

    close = ('<tr><td style="padding:4px 24px 22px;color:#374151;font-size:15px;line-height:1.6;">'
             '<p style="margin:0 0 14px;">When we each log as we go, the board tells the real story of what this team is pulling off &mdash; and it&rsquo;s exactly what our partners and funders see.</p>'
             '<p style="margin:0;">Best,<br>Yusuf</p></td></tr>')

    feedback = ('<tr><td style="padding:2px 24px 20px;">'
                '<div style="background:#f1f5f9;border-radius:12px;padding:14px 16px;font-size:13px;color:#475569;line-height:1.55;">'
                '<b style="color:#334155;">This is new &mdash; help us shape it.</b> What would make it more useful, and what&rsquo;d make logging in Zoho faster? '
                'Just hit reply, or review the writeup &amp; roadmap here: '
                f'<a href="{REPO_URL}" style="color:#2563eb;font-weight:600;text-decoration:none;">github.com/Foundation4ward/prime-scoreboard</a>'
                '</div></td></tr>')

    mascot = ('<tr><td style="padding:16px 24px 4px;">'
              '<div style="background:#f5f3ff;background:linear-gradient(135deg,#f5f3ff,#ecfeff);border:1px solid #ddd6fe;border-radius:18px;padding:15px 16px;box-shadow:0 8px 22px rgba(109,40,217,.12);">'
              '<table cellpadding="0" cellspacing="0" style="width:100%;border-collapse:collapse;"><tr>'
              '<td style="width:78px;vertical-align:top;">'
              '<div style="width:64px;height:64px;border-radius:50%;background:linear-gradient(135deg,#7c3aed,#22d3ee);text-align:center;line-height:64px;font-size:34px;box-shadow:0 0 0 4px #ffffff,0 0 18px rgba(124,58,237,.6);">&#129418;</div></td>'
              '<td style="vertical-align:top;padding-left:12px;">'
              '<div style="font-size:14px;font-weight:800;color:#5b21b6;margin-bottom:5px;">TOMO <span style="font-size:11px;font-weight:700;color:#7c3aed;">&middot; PRIME hype-friend &#10024;</span></div>'
              '<div style="background:#ffffff;border:1px solid #ddd6fe;border-radius:14px;border-top-left-radius:3px;padding:11px 14px;font-size:14px;color:#1e293b;line-height:1.55;box-shadow:0 2px 8px rgba(109,40,217,.08);">'
              f'<div style="font-size:14px;color:#1e293b;">{nugget}</div>'
              f'<div style="margin-top:8px;color:#5b21b6;font-size:13px;">&hellip; and we&rsquo;re <b>{m["emp_rfd"]}/{GOAL_REFUGEES}</b>, <b>{GOAL_REFUGEES - m["emp_rfd"]}</b> to go. Every log gets us there &mdash; let&rsquo;s gooo! &#128293;</div></div>'
              '</td></tr></table></div></td></tr>')

    foot = ('<div style="max-width:600px;color:#9aa1ab;font-size:11px;margin:12px auto 0;text-align:center;line-height:1.5;">'
            'Live from Zoho CRM at send time &middot; green button &rarr; new Outreach Activity &middot; '
            'you&rsquo;re on the PRIME team list.</div>')

    preheader = (f'<div style="display:none;max-height:0;overflow:hidden;opacity:0;color:#eceef1;">{pre}'
                 + ('&nbsp;&zwnj;' * 60) + '</div>')

    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="color-scheme" content="light dark"><meta name="supported-color-schemes" content="light dark">'
        '</head>'
        '<body style="margin:0;background:#edeafc;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">'
        + preheader +
        '<table cellpadding="0" cellspacing="0" style="width:100%;background:#edeafc;background:linear-gradient(160deg,#edeafc,#e0f7fe);"><tr><td align="center" style="padding:20px 10px;">'
        '<table cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#ffffff;border-radius:22px;overflow:hidden;box-shadow:0 12px 34px rgba(76,29,149,.16);">'
        + head + intro + gapcard + goal + snap + board + mascot + cta + close + feedback +
        '</table>' + foot +
        '</td></tr></table></body></html>'
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="Yusuf")
    ap.add_argument("--out", default="/tmp/prime-nudge-v2.html")
    a = ap.parse_args()
    m = gather()
    Path(a.out).write_text(render(a.name, m), encoding="utf-8")
    print("WROTE", a.out)
    print("SUBJECT: PRIME — %d of %d refugees employed · %d logged in 7 days"
          % (m["emp_rfd"], GOAL_REFUGEES, m["last7"]))
    print("metrics:", json.dumps(m))


if __name__ == "__main__":
    main()
