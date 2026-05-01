#!/usr/bin/env python3
"""
FixCraft VP — Weekly Outreach Cron v2
Leverages real email data from Claude Code research.
"""

import os, sys, json, random, smtplib
from datetime import datetime
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ─── CONFIG ───
GMAIL_USER = "fixcraftvp@gmail.com"
GMAIL_PASS = "iulc yaue phss fnam"
REPLY_TO = "fixcraftvp@gmail.com"
BASE_DIR = Path(__file__).parent
ARTICLES_DIR = BASE_DIR / "pending"
OUTBOX_DIR = BASE_DIR / "outbox"
SENT_LOG = BASE_DIR / "sent_log.json"
TARGET_SITES_FILE = BASE_DIR / "target_sites_research.json"

# ─── UTILS ───

def load_sites():
    with open(TARGET_SITES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [s for s in data if s.get("contact_email") and s["contact_email"] != "N/A"]

TARGET_SITES = load_sites()

def read_sent_log():
    if SENT_LOG.exists():
        return json.loads(SENT_LOG.read_text(encoding="utf-8"))
    return {"emails": [], "articles": []}

def save_sent_log(log):
    SENT_LOG.write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")

def read_article(path):
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    title = lines[0].replace("# ", "").strip() if lines else "Untitled"
    return title, text

def build_pitch(site_name, article_title, word_count):
    angles = [
        f"I really appreciate the practical, homeowner-focused content you publish at {site_name}.",
        f"I came across {site_name} while researching home improvement resources for Charlotte homeowners — great stuff.",
        f"The content on {site_name} is exactly the kind of practical advice homeowners need.",
    ]
    return f"""Hi there,

I'm Vlad, owner of FixCraft VP — a handyman and home improvement service based in Charlotte, NC (28277). We specialize in furniture assembly, TV mounting, plumbing, and electrical work.

{random.choice(angles)} I'd love to contribute a guest post that your readers would find genuinely useful.

Here's the article I've prepared:

**"{article_title}"**

It's original, 100% unique content (about {word_count} words), written from the perspective of someone who does this work every day. No promotional fluff — just practical advice homeowners can actually use.

In exchange, I'd just ask for a brief author bio with a link back to fixcraftvp.com so readers can find us if they're in the Charlotte area.

The article is attached below. Happy to adjust the tone, length, or focus to match your editorial guidelines.

Best,
Vladimir Prihodko
FixCraft VP | Charlotte, NC
fixcraftvp.com | (980) 485-5899
"""

def send_email(to_email, subject, text_body, html_body):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"FixCraft VP Guest Post Submissions via {GMAIL_USER}"
        msg["To"] = to_email
        msg["Reply-To"] = REPLY_TO
        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
            server.starttls()
            server.login(GMAIL_USER, GMAIL_PASS)
            server.sendmail(GMAIL_USER, [to_email], msg.as_string())
        return True, None
    except Exception as e:
        return False, str(e)

def count_words(text):
    return len(text.split())

# ─── MAIN ───

def main():
    print(f"🤖 FixCraft Outreach Cron v2 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"🎯 Live targets in database: {len(TARGET_SITES)}")
    print("─" * 50)

    ARTICLES_DIR.mkdir(exist_ok=True)
    OUTBOX_DIR.mkdir(exist_ok=True)
    log = read_sent_log()

    pending = list(ARTICLES_DIR.glob("*.md"))
    if not pending:
        print("📂 Нет новых статей в pending/. Скип.")
        return {"status": "no_new_articles", "sent": []}

    sent_this_run = []

    for article_path in pending:
        if str(article_path) in log.get("articles", []):
            continue

        title, article_text = read_article(article_path)
        word_count = count_words(article_text)
        print(f"\n📄 {title} ({word_count} words)")

        # available = not yet emailed this run
        already_sent = set(log.get("emails", []))
        available = [t for t in TARGET_SITES if t["contact_email"] not in already_sent]
        if not available:
            print("   ⚠️ Закончились target sites. Обнови список.")
            break

        target = random.choice(available)
        site = target["name"]
        email = target["contact_email"]

        pitch = build_pitch(site, title, word_count)
        full_text = f"{pitch}\n\n{'='*60}\nARTICLE:\n{'='*60}\n\n{article_text}"
        html_body = f"""\
        &lt;html&gt;&lt;body&gt;{pitch.replace(chr(10), '&lt;br&gt;')}&lt;hr&gt;{article_text.replace(chr(10), '&lt;br&gt;')}&lt;/body&gt;&lt;/html&gt;"""

        success, err = send_email(email, f"Guest Post Pitch: {title}", full_text, html_body)

        if success:
            print(f"   ✅ {site} ({email})")
            log.setdefault("emails", []).append(email)
            sent_this_run.append({"site": site, "email": email, "article": title})
        else:
            print(f"   ❌ {site}: {err}")

        # Move article to outbox regardless of success
        out_path = OUTBOX_DIR / article_path.name
        out_path.write_text(article_path.read_text(), encoding="utf-8")
        article_path.unlink()
        log.setdefault("articles", []).append(str(article_path))

    save_sent_log(log)

    if sent_this_run:
        notify_text = f"📬 Outreach Sent ({len(sent_this_run)} emails)\n" + "\n".join([f"• {s['site']}: {s['article']}" for s in sent_this_run])
        print(f"\n📤 Telegram: {notify_text}")

    print(f"\n{'─'*50}")
    print(f"📊 Sent today: {len(sent_this_run)}")
    print(f"📁 Database has {len(TARGET_SITES)} sites with email.")

    return {"status": "ok", "sent": sent_this_run}

if __name__ == "__main__":
    main()
