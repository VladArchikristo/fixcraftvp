#!/usr/bin/env python3
"""
FixCraft VP — Weekly Outreach Cron
Каждый понедельник: ищет новые статьи и отправляет outreach
"""

import os
import sys
import json
import smtplib
import random
from datetime import datetime
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ─── КОНФИГ ───
GMAIL_USER = "fixcraftvp@gmail.com"
GMAIL_PASS = "iulc yaue phss fnam"
REPLY_TO = "fixcraftvp@gmail.com"
BASE_DIR = Path(__file__).parent
ARTICLES_DIR = BASE_DIR / "pending"  # сюда кладем новые статьи
OUTBOX_DIR = BASE_DIR / "outbox"
SENT_LOG = BASE_DIR / "sent_log.json"

TARGET_SITES = [
    # Home improvement / DIY
    {"site": "Home Inside", "email": "info@homeinside.net", "form": False},
    {"site": "The DIY Home Decor", "email": "editor@thediyhomedecor.com", "form": False},
    {"site": "Hometalk", "email": "community@hometalk.com", "form": True, "url": "https://www.hometalk.com"},
    {"site": "Today's Homeowner", "email": "editor@todayshomeowner.com", "form": False},
    {"site": "Family Handyman", "email": "editor@familyhandyman.com", "form": False},
    # Local Charlotte
    {"site": "Charlotte Magazine", "email": "editor@charlottemagazine.com", "form": False},
    {"site": "Build Charlotte", "email": "info@buildcharlotte.com", "form": False},
    # General home
    {"site": "Bob Vila", "email": "editor@bobvila.com", "form": False},
    {"site": "Angi Blog", "email": "content@angi.com", "form": False},
    {"site": "HomeServe", "email": "editor@homeserve.com", "form": False},
]

# ─── УТИЛИТЫ ───

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
    intro = random.choice(angles)

    return f"""Hi there,

I'm Vlad, owner of FixCraft VP — a handyman and home improvement service based in Charlotte, NC (28277). We specialize in furniture assembly, TV mounting, plumbing, and electrical work for homeowners in the Charlotte metro area.

{intro} I'd love to contribute a guest post that your readers would find genuinely useful.

Here's the article I've prepared:

**"{article_title}"**

It's original, 100% unique content (about {word_count} words), written from the perspective of someone who does this work every day. No promotional fluff — just practical advice homeowners can actually use.

In exchange, I'd just ask for a brief author bio with a link back to fixcraftvp.com so readers can find us if they're in the Charlotte area.

The article is attached below. Happy to adjust the tone, length, or focus to match your editorial guidelines.

Would any of these topics work for you? I'm also open to writing something specific for your audience if you have a preferred angle.

Best,
Vladimir Prihodko
FixCraft VP | Charlotte, NC
fixcraftvp.com | (980) 485-5899
"""

def send_email(to_email, subject, text_body, html_body):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"FixCraft VP <{GMAIL_USER}>"
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

# ─── ОСНОВНАЯ ЛОГИКА ───

def main():
    print(f"🤖 FixCraft Outreach Cron — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("─" * 50)

    # Создаем папки
    ARTICLES_DIR.mkdir(exist_ok=True)
    OUTBOX_DIR.mkdir(exist_ok=True)

    log = read_sent_log()

    # Ищем новые статьи
    pending = list(ARTICLES_DIR.glob("*.md"))
    if not pending:
        print("📂 Нет новых статей в pending/. Скип.")
        print("💡 Напиши статью, сохрани как pending/article-4-something.md — и я разошлю в следующий понедельник.")
        return {"status": "no_new_articles", "sent": []}

    sent_this_run = []

    for article_path in pending:
        if str(article_path) in log["articles"]:
            continue  # уже отправляли

        title, article_text = read_article(article_path)
        word_count = count_words(article_text)
        print(f"\n📄 {title} ({word_count} words)")

        # ВЫБИРАЕМ ТОЛЬКО 1 сайт на статью (не насколько всем сразу)
        available = [t for t in TARGET_SITES if t["email"] not in log["emails"]]
        if not available:
            print("   ⚠️ Закончились target sites. Обнови список.")
            break

        target = random.choice(available)  # ТОЛЬКО 1 сайт на статью
        site = target["site"]
        email = target["email"]

        pitch = build_pitch(site, title, word_count)
        full_text = f"{pitch}\n\n{'='*60}\nARTICLE:\n{'='*60}\n\n{article_text}"
        html_body = f"<html><body>{pitch.replace(chr(10), '<br>')}<hr>{article_text.replace(chr(10), '<br>')}</body></html>"

        success, err = send_email(email, f"Guest Post Pitch: {title}", full_text, html_body)

        if success:
            print(f"   ✅ {site} ({email})")
            log["emails"].append(email)
            sent_this_run.append({"site": site, "email": email, "article": title})
        else:
            print(f"   ❌ {site}: {err}")

        # Переносим статью в outbox после отправки
        out_path = OUTBOX_DIR / article_path.name
        out_path.write_text(article_path.read_text(), encoding="utf-8")
        article_path.unlink()
        log["articles"].append(str(article_path))

    save_sent_log(log)

    # Отправляем уведомление в Telegram
    if sent_this_run:
        notify_text = f"📬 Outreach Sent ({len(sent_this_run)} emails)\n" + "\n".join([f"• {s['site']}: {s['article']}" for s in sent_this_run])
        print(f"\n📤 Telegram: {notify_text}")

    print(f"\n{'─'*50}")
    print(f"📊 Sent today: {len(sent_this_run)}")
    print(f"📁 Next: save articles to {ARTICLES_DIR}")

    return {"status": "ok", "sent": sent_this_run}

if __name__ == "__main__":
    main()
