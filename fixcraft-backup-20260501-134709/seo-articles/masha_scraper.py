#!/usr/bin/env python3
"""
Masha Article Scraper — авто-парсер статей из логов Маши
Следит за разговорами, находит статьи и сохраняет в pending/
"""

import os
import re
import json
import gzip
import hashlib
from pathlib import Path
from datetime import datetime

# Пути
MASHA_DIR = Path("/Users/vladimirprihodko/Папка тест/fixcraftvp/masha-bot")
PENDING_DIR = Path("/Users/vladimirprihodko/Папка тест/fixcraftvp/seo-articles/pending")
PROCESSED_LOG = Path(__file__).parent / ".masha_processed"

# Минимальный размер статьи (500 слов минимум)
MIN_WORDS = 500


def get_last_processed():
    if PROCESSED_LOG.exists():
        return PROCESSED_LOG.read_text().strip()
    return ""


def save_last_processed(timestamp):
    PROCESSED_LOG.write_text(timestamp)


def find_log_files():
    files = []
    for f in MASHA_DIR.glob("conversation_log*"):
        if f.suffix in ['.jsonl', '.gz']:
            files.append(f)
    files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return files


def read_log_file(path):
    if path.suffix == '.gz':
        with gzip.open(path, 'rt', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]
    else:
        return path.read_text(encoding='utf-8').strip().split('\n')


def extract_articles(lines):
    articles = []
    current_text = []
    current_ts = ""

    for line in lines:
        try:
            entry = json.loads(line)
            text = entry.get("text", "")
            role = entry.get("role", "")
            ts = entry.get("ts", "")

            if role != "assistant":
                continue

            # Ищем признаки статьи
            if text.startswith("#") or "##" in text[:500]:
                current_text.append(text)
                if ts > current_ts:
                    current_ts = ts
            elif current_text and len(text) > 200:
                # Продолжение статьи
                current_text.append(text)
            elif current_text:
                # Конец статьи — обрабатываем
                full_text = "\n\n".join(current_text)
                if len(full_text.split()) >= MIN_WORDS:
                    articles.append({"text": full_text, "ts": current_ts})
                current_text = []
                current_ts = ""
        except json.JSONDecodeError:
            continue

    # Если осталась статья в конце
    if current_text:
        full_text = "\n\n".join(current_text)
        if len(full_text.split()) >= MIN_WORDS:
            articles.append({"text": full_text, "ts": current_ts})

    return articles


def clean_article(text):
    # Убираем мета-информацию пользователя, оставляем только статью
    lines = text.split('\n')
    cleaned = []
    in_article = False

    for line in lines:
        if line.startswith('#'):
            in_article = True
        if in_article:
            cleaned.append(line)

    return '\n'.join(cleaned) if cleaned else text


def generate_filename(text):
    # Берём первую строку как заголовок
    title = text.split('\n')[0].replace('#', '').strip()[:50]
    safe_title = re.sub(r'[^a-zA-Z0-9\s-]', '', title).replace(' ', '-').lower()
    if not safe_title:
        safe_title = "article"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"masha-{safe_title}-{ts}.md"


def main():
    print(f"🔍 Masha Article Scraper — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("─" * 50)

    PENDING_DIR.mkdir(exist_ok=True)

    log_files = find_log_files()
    if not log_files:
        print("⚠️ Не найдено логов Маши")
        return

    last_processed = get_last_processed()
    new_articles = []
    latest_ts = last_processed

    for log_file in log_files:
        lines = read_log_file(log_file)
        articles = extract_articles(lines)

        for art in articles:
            if art["ts"] > last_processed:
                cleaned = clean_article(art["text"])
                if cleaned:
                    new_articles.append(cleaned)
                    if art["ts"] > latest_ts:
                        latest_ts = art["ts"]

    if not new_articles:
        print("📤 Новых статей не найдено")
        return

    print(f"📝 Найдено новых статей: {len(new_articles)}")

    for article in new_articles:
        filename = generate_filename(article)
        filepath = PENDING_DIR / filename
        filepath.write_text(article, encoding="utf-8")
        words = len(article.split())
        print(f"   ✅ Saved: {filename} ({words} words)")

    save_last_processed(latest_ts)
    print(f"\n📁 Всего в pending/: {len(list(PENDING_DIR.glob('*.md')))} статей")


if __name__ == "__main__":
    main()
