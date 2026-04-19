#!/usr/bin/env python3
"""
YouTube Upload Script via Playwright (headful Chrome)
Uploads haulwallet-promo.mp4 to YouTube Studio
"""

import asyncio
import os
import sys
from pathlib import Path

# ─── CONFIG ─────────────────────────────────────────────────────────────────

VIDEO_PATH = Path(__file__).parent / "haulwallet-promo.mp4"

TITLE = "HaulWallet App — Free Tool for Owner-Operators & Truck Drivers"

DESCRIPTION = """HaulWallet is the free app built for independent truck drivers and owner-operators across the USA. Stop running your trucking business from sticky notes and spreadsheets. Everything you need is right here — load board, cargo tracking, invoice generator, and fast payment tools — all in one place.

────────────────────────────────
⏱ TIMESTAMPS
────────────────────────────────
0:00 — The everyday chaos: paperwork, broker calls, missed money
0:12 — Meet HaulWallet: your road, your rules
0:16 — Find loads and compare rates instantly
0:18 — Track your cargo with live map updates
0:20 — Get paid fast with auto-generated invoices
0:25 — What real drivers are earning with HaulWallet

────────────────────────────────
🚛 WHO THIS IS FOR
────────────────────────────────
→ Owner-operators running 1 truck
→ Small fleet owners (2–5 trucks)
→ Dispatchers managing independent drivers
→ CDL drivers thinking about going independent
→ Anyone tired of broker lowballing and lost paperwork

────────────────────────────────
📱 WHAT HAULWALLET DOES
────────────────────────────────
✅ Load Board — Browse and accept loads in seconds. See rate per mile upfront.
✅ Cargo Tracker — Live map with real-time ETA. Shippers and dispatchers can follow along.
✅ Invoice Generator — Auto-create professional invoices from completed loads. PDF, done.
✅ Fast Pay — Get paid faster. No waiting 30–45 days for broker payments.
✅ Expense Tracker — Log fuel, maintenance, tolls. Know your real net pay before you move.
✅ Earnings Dashboard — Weekly and monthly summaries. Understand your business like a real operator.

────────────────────────────────
💰 THE NUMBERS MATTER
────────────────────────────────
Most owner-operators lose $200–$500/month to disorganized paperwork, disputed invoices, and broker lowballing. HaulWallet fixes that. Not with complicated software — just a clean, fast app that fits in your truck.

Free to download. Free to start. Built for the road.

────────────────────────────────
📥 DOWNLOAD FREE
────────────────────────────────
🔗 Google Play: https://haulwallet.app
🌐 Website: https://haulwallet.app

#HaulWallet #TruckDriver #OwnerOperator #TruckingApp #CDLDriver #FreightBroker #LoadBoard #TruckerLife #OwnerOperatorLife #TruckingBusiness #SemiTruck #18Wheeler #FreightLife #TruckerUSA #DispatchApp #TruckingIncome #BuiltForTheRoad"""

TAGS = "HaulWallet, truck driver app, owner operator app, trucking app USA, load board app, cargo tracking app, CDL driver app, trucking business tools, owner operator income, freight app, dispatch app, trucking expenses tracker, mileage tracker truck, trucker app, semi truck app, 18 wheeler app, trucker income, invoice app trucking, truck driver tools, owner operator business, fast pay trucking, freight broker alternative, trucker life, owner operator life, trucking software, truck driver tips, trucking money, independent truck driver"

CATEGORY = "Science & Technology"

# ─── LOGGING ────────────────────────────────────────────────────────────────

def log(msg: str):
    print(f"[YT-UPLOAD] {msg}", flush=True)

# ─── MAIN ───────────────────────────────────────────────────────────────────

async def upload():
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

    if not VIDEO_PATH.exists():
        log(f"ERROR: Video file not found: {VIDEO_PATH}")
        sys.exit(1)

    log(f"Video: {VIDEO_PATH} ({VIDEO_PATH.stat().st_size / 1_000_000:.1f} MB)")

    async with async_playwright() as p:
        log("Launching Chrome (headful)...")

        # Пробуем реальный Chrome, fallback на Chromium
        try:
            browser = await p.chromium.launch(
                channel="chrome",
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--start-maximized",
                ],
            )
            log("Using real Chrome")
        except Exception as e:
            log(f"Chrome not found ({e}), falling back to Chromium...")
            browser = await p.chromium.launch(
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--start-maximized",
                ],
            )
            log("Using Chromium")

        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            # Убираем navigator.webdriver
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        )

        # Скрываем признаки автоматизации
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)

        page = await context.new_page()

        # ── ШАГ 1: YouTube Studio ──────────────────────────────────────────
        log("Navigating to YouTube Studio...")
        await page.goto("https://studio.youtube.com", wait_until="domcontentloaded", timeout=60_000)
        await page.wait_for_timeout(2000)

        current_url = page.url
        log(f"Current URL: {current_url}")

        # Если редиректнуло на логин
        if "accounts.google.com" in current_url or "signin" in current_url:
            log("Login required — attempting automatic login...")

            # Шаг 1: Email
            try:
                email_input = page.locator("input[type='email']")
                await email_input.wait_for(state="visible", timeout=15_000)
                await email_input.click()
                await email_input.fill("fixcraftvp@gmail.com")
                log("Email entered")
                await page.wait_for_timeout(1000)

                # Нажимаем Enter вместо кнопки (надёжнее)
                await email_input.press("Enter")
                log("Pressed Enter (email)")
                await page.wait_for_timeout(3000)
            except Exception as e:
                log(f"Email step error: {e}")

            # Шаг 2: Password — ждём появления видимого поля
            try:
                # Ждём видимого поля пароля (не hidden)
                pwd_input = page.locator("input[type='password']:not([aria-hidden='true'])")
                await pwd_input.wait_for(state="visible", timeout=20_000)
                await pwd_input.click()
                await pwd_input.fill("Ahozon67")
                log("Password entered")
                await page.wait_for_timeout(1000)

                # Нажимаем Enter
                await pwd_input.press("Enter")
                log("Pressed Enter (password)")
                await page.wait_for_timeout(4000)
            except Exception as e:
                log(f"Password step error: {e}")

            # Шаг 3: Ждём 2FA или редирект в Studio
            log(f"After login attempt, URL: {page.url}")
            if "studio.youtube.com" in page.url:
                log("Login successful!")
            else:
                log("Waiting for 2FA or redirect to Studio (up to 120 sec)...")
                try:
                    await page.wait_for_url("**/studio.youtube.com**", timeout=120_000)
                    log("Login successful!")
                except PlaywrightTimeout:
                    log(f"ERROR: Login timeout. Current URL: {page.url}")
                    await browser.close()
                    sys.exit(1)

        # Ждём загрузки Studio
        log("Waiting for Studio to load...")
        await page.wait_for_load_state("networkidle", timeout=30_000)
        await page.wait_for_timeout(1500)

        # ── ШАГ 2: Кнопка CREATE / Upload ─────────────────────────────────
        log("Looking for CREATE button...")
        create_btn = page.locator("#create-icon, [aria-label='Create'], button:has-text('CREATE'), yt-button-renderer[button-renderer]:has-text('Create')")

        try:
            await create_btn.first.wait_for(state="visible", timeout=30_000)
            await create_btn.first.click()
            log("Clicked CREATE")
        except PlaywrightTimeout:
            log("Trying alternative: direct upload URL...")
            await page.goto("https://www.youtube.com/upload", wait_until="domcontentloaded", timeout=60_000)

        await page.wait_for_timeout(1000)

        # ── ШАГ 3: Upload video option ─────────────────────────────────────
        upload_option = page.locator("tp-yt-paper-item:has-text('Upload video'), [test-id='upload-beta'], ytcp-menu-item:has-text('Upload video')")
        try:
            await upload_option.first.wait_for(state="visible", timeout=10_000)
            await upload_option.first.click()
            log("Clicked 'Upload video'")
        except PlaywrightTimeout:
            log("Upload video option not found — may already be on upload dialog")

        await page.wait_for_timeout(1500)

        # ── ШАГ 4: Выбор файла ─────────────────────────────────────────────
        log(f"Selecting video file: {VIDEO_PATH}")
        file_input = page.locator("input[type='file']")

        try:
            await file_input.wait_for(state="attached", timeout=30_000)
            await file_input.set_input_files(str(VIDEO_PATH))
            log("File selected!")
        except PlaywrightTimeout:
            log("ERROR: File input not found. Check if upload dialog opened correctly.")
            await page.wait_for_timeout(5000)
            await browser.close()
            sys.exit(1)

        # ── ШАГ 5: Ждём появления формы метаданных ────────────────────────
        log("Waiting for metadata form (upload in progress)...")
        title_input = page.locator("#title-textarea #textbox, ytcp-social-suggestions-textbox[id='title-textarea'] #textbox")

        try:
            await title_input.first.wait_for(state="visible", timeout=120_000)
            log("Metadata form appeared!")
        except PlaywrightTimeout:
            log("ERROR: Metadata form timeout. Upload may have failed.")
            input("Press Enter to close browser...")
            await browser.close()
            sys.exit(1)

        await page.wait_for_timeout(1000)

        # ── ШАГ 6: Title ──────────────────────────────────────────────────
        log("Setting title...")
        title_field = page.locator("#title-textarea #textbox").first
        await title_field.click()
        await title_field.select_all()
        await title_field.press("Backspace")
        await title_field.type(TITLE, delay=30)
        log(f"Title set: {TITLE}")

        await page.wait_for_timeout(500)

        # ── ШАГ 7: Description ────────────────────────────────────────────
        log("Setting description...")
        desc_field = page.locator("#description-textarea #textbox").first
        await desc_field.click()
        await desc_field.select_all()
        await desc_field.press("Backspace")
        await desc_field.type(DESCRIPTION, delay=5)
        log("Description set")

        await page.wait_for_timeout(500)

        # ── ШАГ 8: Not made for kids ──────────────────────────────────────
        log("Setting audience (not for kids)...")
        not_for_kids = page.locator("tp-yt-paper-radio-button[name='VIDEO_MADE_FOR_KIDS_NOT_MFK']")
        try:
            await not_for_kids.click(timeout=10_000)
            log("Set: Not made for kids")
        except:
            log("Could not set audience — skipping")

        # ── ШАГ 9: More options → Tags ────────────────────────────────────
        log("Clicking 'More options'...")
        more_options = page.locator("ytcp-button:has-text('More options'), #toggle-button:has-text('More options')")
        try:
            await more_options.first.click(timeout=15_000)
            await page.wait_for_timeout(1000)
            log("More options expanded")
        except:
            log("'More options' not found — skipping tags")
            more_options = None

        if more_options:
            # Tags field
            tags_input = page.locator("input[aria-label='Tags'], #tags-container input")
            try:
                await tags_input.first.wait_for(state="visible", timeout=10_000)
                await tags_input.first.click()
                await tags_input.first.type(TAGS + ",", delay=5)
                await tags_input.first.press("Enter")
                log("Tags set")
            except:
                log("Tags input not found — skipping")

            # Category
            category_select = page.locator("ytcp-form-select[id='category-container'] button, #category button")
            try:
                await category_select.first.click(timeout=10_000)
                await page.wait_for_timeout(500)
                cat_option = page.locator(f"tp-yt-paper-item:has-text('Science & Technology')")
                await cat_option.first.click(timeout=10_000)
                log("Category set: Science & Technology")
            except:
                log("Category selector not found — skipping")

        # ── ШАГ 10: NEXT → NEXT → NEXT → Visibility ──────────────────────
        log("Clicking NEXT (Details → Video elements)...")
        for step_name in ["Video elements", "Checks", "Visibility"]:
            next_btn = page.locator("ytcp-button#next-button, button[aria-label='Next']")
            try:
                await next_btn.first.click(timeout=30_000)
                log(f"→ {step_name}")
                await page.wait_for_timeout(2000)
            except PlaywrightTimeout:
                log(f"NEXT button timeout at step '{step_name}'")
                break

        # ── ШАГ 11: Visibility → Public ───────────────────────────────────
        log("Setting visibility to Public...")
        public_radio = page.locator("tp-yt-paper-radio-button[name='PUBLIC'], ytcp-video-visibility-select [name='PUBLIC']")
        try:
            await public_radio.first.click(timeout=30_000)
            log("Visibility: Public")
        except:
            log("Public radio not found — check visibility manually")

        await page.wait_for_timeout(1000)

        # ── ШАГ 12: Publish ───────────────────────────────────────────────
        log("Clicking PUBLISH...")
        publish_btn = page.locator("ytcp-button#done-button, button[aria-label='Publish'], ytcp-button:has-text('Publish')")
        try:
            await publish_btn.first.click(timeout=30_000)
            log("PUBLISH clicked!")
        except PlaywrightTimeout:
            log("Publish button not found. Waiting 15 seconds before closing...")
            await page.wait_for_timeout(15000)

        # Ждём подтверждения
        log("Waiting for upload confirmation...")
        try:
            await page.wait_for_selector(
                "ytcp-video-share-dialog, [dialog-title='Your video is now live']",
                timeout=120_000
            )
            log("SUCCESS: Video published!")
        except PlaywrightTimeout:
            log("Could not confirm publish — check YouTube Studio manually")

        await page.wait_for_timeout(3000)

        # Получить ссылку на видео
        try:
            video_link = await page.locator("a[href*='youtu.be'], a[href*='youtube.com/watch']").first.get_attribute("href")
            if video_link:
                log(f"Video URL: {video_link}")
        except:
            pass

        log("Done! Closing browser in 5 seconds...")
        await page.wait_for_timeout(5000)
        await browser.close()


if __name__ == "__main__":
    log("=== YouTube Upload Script ===")
    log(f"Video: {VIDEO_PATH}")
    log(f"Title: {TITLE}")
    log("Starting...")
    asyncio.run(upload())
