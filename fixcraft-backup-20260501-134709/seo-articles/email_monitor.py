#!/usr/bin/env python3
"""
FixCraft VP — Email Monitor
Проверяет почту fixcraftvp@gmail.com каждые 30 мин
Отправляет отчёт о важных письмах в Telegram
Чистит спам и неважное
"""

import imaplib
import json
from email.parser import BytesParser
from email.policy import default
from pathlib import Path

IMAP_SERVER = "imap.gmail.com"
EMAIL = "fixcraftvp@gmail.com"
APP_PASSWORD = "iulc yaue phss fnam"
BASE_DIR = Path.home() / "Папка тест/fixcraftvp/seo-articles"
SEEN_FILE = BASE_DIR / ".seen_emails.json"

# --- Whitelist: чья почта нам интересна ---
WHITELIST_DOMAINS = [
    "hometalk.com", "todayshomeowner.com", "familyhandyman.com",
    "charlottemagazine.com", "bobvila.com", "angi.com",
    "remodelaholic.com", "theglobalhues.com", "finderify.com",
    "kitchenandbathresources.com", "hometechscoop.com", "securityforward.com",
    "homeautomationtalks.com", "onlinetoolreviews.com", "shineyourlightblog.com",
    "housewhirl.com", "beautifulhousetips.com", "axios.com", "charlotte.axios.com",
]

# --- Blacklist: спам / неважное ---
BLACKLIST_SENDERS = [
    "no-reply@accounts.google.com", "noreply@", "do-not-reply@", "noreply-",
    "@taskrabbit.com", "@nextdoor.com", "@thumbtack.com", "@c-mail.taskrabbit.com",
    "businessprofile-noreply@google.com", "mybusiness-noreply@google.com",
]

KNOWLEDGE_SENDERS = [
    "businessprofile-noreply@google.com",
    "do-not-reply@pro.thumbtack.com",
    "@taskrabbit.com",
    "@nextdoor.com",
]

def load_seen():
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text(encoding="utf-8")))
    return set()

def save_seen(seen):
    SEEN_FILE.write_text(json.dumps(list(seen), indent=2), encoding="utf-8")

def is_important(from_addr, subject):
    """Определяет важность письма"""
    from_lower = from_addr.lower()
    
    # Черный список — спам или известные рассылки
    for b in BLACKLIST_SENDERS:
        if b in from_lower:
            return False, "spam_blacklist"
    
    # Белый список — ответы от редакторов
    for domain in WHITELIST_DOMAINS:
        if domain in from_lower:
            return True, "editor_response"
    
    # Bounce / delivery failure
    if "mailer-daemon" in from_lower or "delivery status" in subject.lower():
        return True, "delivery_failure"
    
    # Google Business — отзывы и лиды
    if "businessprofile" in from_lower and ("review" in subject.lower() or "lead" in subject.lower()):
        return True, "google_business"
    
    # Generic — если не определили, нейтрально
    return None, "unknown"

def main():
    print(f"📧 FixCraft Email Monitor — checking {EMAIL}\n")
    
    seen = load_seen()
    important_emails = []
    spam_emails = []
    
    mail = imaplib.IMAP4_SSL(IMAP_SERVER, 993)
    mail.login(EMAIL, APP_PASSWORD)
    mail.select("inbox")
    
    status, messages = mail.search(None, "UNSEEN")
    unread_ids = messages[0].split()
    
    if not unread_ids:
        print("✅ Нет новых писем.")
        mail.logout()
        return
    
    print(f"📨 Новых писем: {len(unread_ids)}\n")
    
    for msg_id in unread_ids:
        status, msg_data = mail.fetch(msg_id, "(RFC822)")
        raw_email = msg_data[0][1]
        email_msg = BytesParser(policy=default).parsebytes(raw_email)
        
        from_addr = email_msg["From"] or "unknown"
        subject = email_msg["Subject"] or "(no subject)"
        date = email_msg["Date"] or "(no date)"
        msg_id_str = email_msg["Message-ID"] or str(msg_id)
        
        if msg_id_str in seen:
            continue
        seen.add(msg_id_str)
        
        important, reason = is_important(from_addr, subject)
        
        info = {
            "from": from_addr,
            "subject": subject,
            "date": date,
            "reason": reason,
        }
        
        if important is True:
            print(f"  🔴 ВАЖНО [{reason}]: {subject[:55]}")
            print(f"     От: {from_addr[:50]}")
            important_emails.append(info)
        elif important is False:
            print(f"  🗑️ СПАМ [{reason}]: {subject[:40]} (удаляем)")
            spam_emails.append(info)
            # Удаляем спам сразу — неважные письма в корзину
            mail.store(msg_id, "+FLAGS", "\\Deleted")
        else:
            print(f"  ⚪ НЕЙТРАЛЬНО: {subject[:45]} — {from_addr[:40]}")
    
    # Финализируем удаление спама
    if spam_emails:
        mail.expunge()
    
    mail.logout()
    save_seen(seen)
    
    # Отчёт
    print(f"\n{'─'*50}")
    print(f"📊 ИТОГО: {len(important_emails)} важных, {len(spam_emails)} спама удалено, {len(unread_ids) - len(important_emails) - len(spam_emails)} нейтральных")
    
    if important_emails:
        print("\n🔴 ВАЖНЫЕ ПИСЬМА:")
        for e in important_emails:
            emoji = "📬" if e["reason"] == "editor_response" else "⚠️" if e["reason"] == "delivery_failure" else "⭐"
            print(f"  {emoji} {e['subject']}")
            print(f"     От: {e['from']}")
    
    return important_emails

if __name__ == "__main__":
    main()
