#!/usr/bin/env python3
"""
FixCraftVP Google Business Profile Setup Script
Запускает браузер с твоим Chrome профилем (уже залогинен в Google)
и автоматически настраивает профиль бизнеса.
"""

from playwright.sync_api import sync_playwright
import time
import os

CHROME_USER_DATA = os.path.expanduser("~/Library/Application Support/Google/Chrome")

BUSINESS_DATA = {
    "description": (
        "FixCraftVP Handyman Services is your trusted local handyman in Charlotte, NC. "
        "I specialize in furniture assembly (IKEA, Wayfair, Amazon), TV mounting, "
        "shelf installation, minor drywall repairs, door and window fixes, caulking, "
        "and general home maintenance.\n\n"
        "As a solo professional, I bring personal attention to every job — no crews, "
        "no surprises. Quality work, fair pricing, and same-week availability across "
        "Charlotte, Ballantyne, Matthews, Mint Hill, and surrounding areas.\n\n"
        "Licensed, insured, and committed to 5-star service. "
        "Text or call for a free estimate — most jobs completed in a single visit."
    ),
    "service_areas": [
        "Charlotte, NC",
        "Ballantyne, NC",
        "Matthews, NC",
        "Mint Hill, NC",
        "Huntersville, NC",
        "Concord, NC"
    ],
    "hours": {
        "Monday": ("08:00", "18:00"),
        "Tuesday": ("08:00", "18:00"),
        "Wednesday": ("08:00", "18:00"),
        "Thursday": ("08:00", "18:00"),
        "Friday": ("08:00", "18:00"),
        "Saturday": ("09:00", "16:00"),
        "Sunday": "Closed"
    },
    "services": [
        {"name": "Furniture Assembly", "price": "$50 - $250"},
        {"name": "TV Mounting", "price": "$80 - $250"},
        {"name": "Shelf & Picture Hanging", "price": "$40 - $80"},
        {"name": "Drywall Patch & Repair", "price": "$75 - $200"},
        {"name": "Door Adjustment & Repair", "price": "$60 - $150"},
        {"name": "Window Screen Repair", "price": "$40 - $80"},
        {"name": "Caulking & Weatherstripping", "price": "$50 - $120"},
        {"name": "General Home Maintenance", "price": "$60 - $150"},
    ]
}


def run():
    with sync_playwright() as p:
        print("🚀 Запуск Chrome с твоим профилем...")

        # Используем твой Chrome профиль — уже залогинен в Google
        browser = p.chromium.launch_persistent_context(
            user_data_dir=CHROME_USER_DATA,
            headless=False,  # Видимый браузер для дебага
            channel="chrome",
            args=["--profile-directory=Default"]
        )

        page = browser.new_page()

        print("📍 Открываю Google Business Profile...")
        page.goto("https://business.google.com/", wait_until="networkidle", timeout=30000)
        time.sleep(3)

        # Скриншот стартовой страницы
        page.screenshot(path="/tmp/gbp_start.png")
        print("📸 Скриншот: /tmp/gbp_start.png")

        current_url = page.url
        print(f"📌 URL: {current_url}")

        # Если редирект на логин — значит профиль не нашёл сессию
        if "accounts.google.com" in current_url or "signin" in current_url.lower():
            print("❌ Google просит логин. Chrome профиль не подхватил сессию.")
            print("   Запусти скрипт снова вручную и войди в Google.")
            browser.close()
            return

        print("✅ Залогинен! Ищу FixCraftVP...")
        time.sleep(2)

        # Ищем карточку бизнеса
        page.screenshot(path="/tmp/gbp_dashboard.png")
        print("📸 Dashboard: /tmp/gbp_dashboard.png")

        # Попытка найти Edit Profile / Редактировать профиль
        edit_selectors = [
            "text=Edit profile",
            "text=Редактировать профиль",
            "[data-item-id='edit_profile']",
            "button:has-text('Edit')",
        ]

        edit_clicked = False
        for sel in edit_selectors:
            try:
                el = page.wait_for_selector(sel, timeout=3000)
                if el:
                    el.click()
                    edit_clicked = True
                    print(f"✅ Нажал: {sel}")
                    time.sleep(2)
                    break
            except:
                continue

        if not edit_clicked:
            # Пробуем напрямую URL бизнеса
            page.goto("https://business.google.com/edit", wait_until="networkidle", timeout=20000)
            time.sleep(2)

        page.screenshot(path="/tmp/gbp_edit.png")
        print("📸 Edit page: /tmp/gbp_edit.png")

        print("\n📋 СТАТУС:")
        print(f"   URL: {page.url}")
        print(f"   Title: {page.title()}")
        print("\n⚠️  Браузер открыт. Проверь скриншоты:")
        print("   /tmp/gbp_start.png")
        print("   /tmp/gbp_dashboard.png")
        print("   /tmp/gbp_edit.png")

        input("\n↵ Нажми Enter чтобы закрыть браузер...")
        browser.close()
        print("✅ Готово")


if __name__ == "__main__":
    run()
