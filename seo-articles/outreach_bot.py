#!/usr/bin/env python3
"""
FixCraft VP — SEO Guest Post Outreach Bot (Gmail SMTP)
Отправка outreach-писем через fixcraftvp@gmail.com
"""

import os
import sys
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from datetime import datetime

# ─── КОНФИГ ───
GMAIL_USER = "fixcraftvp@gmail.com"
GMAIL_PASS = "iulc yaue phss fnam"
REPLY_TO = "vladimir92905@gmail.com"

# Куда отправляем
OUTREACH_TARGETS = [
    {
        "site": "Wham Bam You're A Handyman",
        "url": "https://whambamyoureahandyman.com",
        "email": "info@whambamyoureahandyman.com",
        "method": "email",
        "article_file": "article-1-wham-bam.md",
        "subject": "Guest Post Pitch: 5 Signs You Need a Professional Handyman in Charlotte",
    },
    {
        "site": "House Whirl",
        "url": "https://housewhirl.com",
        "email": "editor@housewhirl.com",
        "method": "email",
        "article_file": "article-2-house-whirl.md",
        "subject": "Guest Post Contribution: TV Mounting 101 — Pro vs DIY",
    },
    {
        "site": "Opple House",
        "url": "https://opplehouse.com",
        "email": "hello@opplehouse.com",
        "method": "form",
        "article_file": "article-3-opple-house.md",
        "subject": "Write for Us Submission: Charlotte Home Maintenance Checklist",
    },
]

# ─── УТИЛИТЫ ───

def read_article(filename: str) -> str:
    path = Path(__file__).parent / filename
    if not path.exists():
        print(f"❌ Не найден файл: {path}")
        return ""
    return path.read_text(encoding="utf-8")

def build_pitch(site_name: str, article_title: str) -> str:
    return f"""Hi there,

I'm Vlad, owner of FixCraft VP — a handyman and home improvement service based in Charlotte, NC (28277). We specialize in furniture assembly, TV mounting, plumbing, and electrical work for homeowners in the Charlotte metro area.

I've been following {site_name} and really appreciate the practical, homeowner-focused content you publish. I'd love to contribute a guest post that your readers would find genuinely useful.

Here's the article I've prepared:

**"{article_title}"**

It's original, 100% unique content (about 1,400–1,800 words), written from the perspective of someone who does this work every day. No promotional fluff — just practical advice homeowners can actually use.

In exchange, I'd just ask for a brief author bio with a link back to fixcraftvp.com so readers can find us if they're in the Charlotte area.

The article is attached below. Happy to adjust the tone, length, or focus to match your editorial guidelines.

Would this work for you?

Best,
Vladimir Prihodko
FixCraft VP | Charlotte, NC
fixcraftvp.com | (980) 485-5899
"""

def send_via_gmail(to_email: str, subject: str, html_body: str, text_body: str) -> dict:
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

        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

def save_draft(target: dict, text_body: str, html_body: str):
    out_dir = Path(__file__).parent / "outbox"
    out_dir.mkdir(exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_site = target["site"].replace(" ", "_").replace("'", "")

    text_path = out_dir / f"{safe_site}_{ts}.txt"
    text_path.write_text(
        f"TO: {target['email']}\nSUBJECT: {target['subject']}\n\n{text_body}",
        encoding="utf-8"
    )

    html_path = out_dir / f"{safe_site}_{ts}.html"
    html_path.write_text(html_body, encoding="utf-8")

    print(f"   📄 Draft saved: {text_path.name}")
    return text_path, html_path

# ─── ОСНОВНАЯ ЛОГИКА ───

def run_outreach():
    print("🤖 FixCraft VP Outreach Bot (Gmail)")
    print("─" * 50)

    results = []

    for idx, target in enumerate(OUTREACH_TARGETS, 1):
        print(f"\n{idx}. 📋 {target['site']}")
        print(f"   📧 {target['email']} | Method: {target['method']}")

        article = read_article(target["article_file"])
        if not article:
            results.append({"site": target["site"], "status": "skipped", "reason": "article not found"})
            continue

        title = article.split("\n")[0].replace("# ", "").strip()

        pitch_text = build_pitch(target["site"], title)
        full_text = f"{pitch_text}\n\n{'='*60}\nARTICLE:\n{'='*60}\n\n{article}"

        pitch_html = pitch_text.replace("\n", "<br>").replace("**", "<b>").replace("*", "<i>")
        article_html = article.replace("\n", "<br>")
        full_html = f"<html><body>{pitch_html}<hr>{article_html}</body></html>"

        save_draft(target, full_text, full_html)

        if target["method"] == "email":
            result = send_via_gmail(target["email"], target["subject"], full_html, full_text)
            if result["success"]:
                print(f"   ✅ SENT to {target['email']}")
                results.append({"site": target["site"], "status": "sent"})
            else:
                print(f"   ❌ Failed: {result.get('error')}")
                results.append({"site": target["site"], "status": "failed", "error": result.get("error")})
        else:
            print(f"   ⏳ Form submission — draft saved, manual submit needed")
            results.append({"site": target["site"], "status": "draft", "reason": "form submission"})

    report_path = Path(__file__).parent / "outbox" / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    print("\n" + "─" * 50)
    print(f"📊 Report saved: {report_path.name}")
    print(f"📁 Drafts: {Path(__file__).parent / 'outbox'}")

    return results

if __name__ == "__main__":
    run_outreach()
