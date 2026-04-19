#!/usr/bin/env python3
"""
YouTube Upload via Playwright — persistent profile (reuses Google login session)
Run ONCE interactively to login. After that sessions are saved.
"""

import asyncio
import os
import sys
from pathlib import Path

VIDEO_PATH = Path(__file__).parent / "haulwallet-promo.mp4"
PROFILE_DIR = Path.home() / ".yt_upload_profile"
PROFILE_DIR.mkdir(exist_ok=True)

TITLE = "HaulWallet App — Free Tool for Owner-Operators & Truck Drivers"
DESCRIPTION = """HaulWallet is the free app built for independent truck drivers and owner-operators across the USA. Stop running your trucking business from sticky notes and spreadsheets. Everything you need is right here — load board, cargo tracking, invoice generator, and fast payment tools — all in one place.

⏱ TIMESTAMPS
0:00 — The everyday chaos: paperwork, broker calls, missed money
0:12 — Meet HaulWallet: your road, your rules
0:16 — Find loads and compare rates instantly
0:18 — Track your cargo with live map updates
0:20 — Get paid fast with auto-generated invoices
0:25 — What real drivers are earning with HaulWallet

🚛 WHO THIS IS FOR
→ Owner-operators running 1 truck
→ Small fleet owners (2-5 trucks)
→ Dispatchers managing independent drivers
→ CDL drivers thinking about going independent
→ Anyone tired of broker lowballing and lost paperwork

📱 WHAT HAULWALLET DOES
Load Board - Browse and accept loads in seconds. See rate per mile upfront.
Cargo Tracker - Live map with real-time ETA.
Invoice Generator - Auto-create professional invoices. PDF, done.
Fast Pay - Get paid faster. No waiting 30-45 days.
Expense Tracker - Log fuel, maintenance, tolls.
Earnings Dashboard - Weekly and monthly summaries.

💰 Most owner-operators lose $200-$500/month to disorganized paperwork. HaulWallet fixes that.

Free to download. Free to start. Built for the road.

Download: https://haulwallet.app

#HaulWallet #TruckDriver #OwnerOperator #TruckingApp #CDLDriver #LoadBoard #TruckerLife #TruckingBusiness"""

def log(msg):
    print(f"[YT] {msg}", flush=True)

async def main():
    from playwright.async_api import async_playwright, TimeoutError as PWTimeout

    if not VIDEO_PATH.exists():
        log(f"ERROR: Video not found: {VIDEO_PATH}")
        sys.exit(1)

    log(f"Video: {VIDEO_PATH} ({VIDEO_PATH.stat().st_size / 1_000_000:.1f} MB)")
    log(f"Profile: {PROFILE_DIR}")

    async with async_playwright() as p:
        # Persistent context — сохраняет cookies между запусками
        context = await p.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=False,
            channel=None,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--start-maximized",
                "--disable-web-security",
            ],
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
            ignore_https_errors=True,
        )

        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)

        page = await context.new_page()

        log("Opening YouTube Studio...")
        await page.goto("https://studio.youtube.com", wait_until="domcontentloaded", timeout=60_000)
        await page.wait_for_timeout(3000)

        current_url = page.url
        log(f"URL: {current_url}")

        # Если нужен логин — ждём ручного входа
        if "accounts.google.com" in current_url or "signin" in current_url:
            log("=" * 50)
            log("LOGIN REQUIRED!")
            log("Please login manually in the browser window.")
            log("After login completes, press Enter here to continue...")
            log("=" * 50)
            input()
            await page.wait_for_timeout(3000)
            log(f"After login URL: {page.url}")

        # Ждём Studio
        log("Waiting for Studio...")
        try:
            await page.wait_for_url("**/studio.youtube.com**", timeout=30_000)
        except PWTimeout:
            log(f"Not in Studio yet. URL: {page.url}")

        await page.wait_for_load_state("networkidle", timeout=30_000)
        await page.wait_for_timeout(2000)

        log("Looking for CREATE button...")
        # Разные селекторы для кнопки Create
        create_selectors = [
            "#create-icon",
            "[aria-label='Create']",
            "[aria-label='CREATE']",
            "ytcp-button:has-text('Create')",
            "#upload-icon",
        ]

        clicked = False
        for sel in create_selectors:
            try:
                btn = page.locator(sel)
                if await btn.count() > 0:
                    await btn.first.click(timeout=5_000)
                    log(f"Clicked: {sel}")
                    clicked = True
                    break
            except:
                continue

        if not clicked:
            log("CREATE button not found, trying direct upload URL...")
            await page.goto("https://www.youtube.com/upload", wait_until="domcontentloaded", timeout=30_000)

        await page.wait_for_timeout(1500)

        # Upload video option
        upload_selectors = [
            "tp-yt-paper-item:has-text('Upload video')",
            "ytcp-menu-item:has-text('Upload video')",
            "[test-id='upload-beta']",
        ]
        for sel in upload_selectors:
            try:
                opt = page.locator(sel)
                if await opt.count() > 0:
                    await opt.first.click(timeout=5_000)
                    log("Clicked Upload video")
                    break
            except:
                continue

        await page.wait_for_timeout(2000)

        # File input
        log(f"Setting file: {VIDEO_PATH}")
        file_input = page.locator("input[type='file']")
        try:
            await file_input.wait_for(state="attached", timeout=30_000)
            await file_input.set_input_files(str(VIDEO_PATH))
            log("File selected!")
        except PWTimeout:
            log("ERROR: File input not found")
            input("Browser stays open. Press Enter to close...")
            await context.close()
            sys.exit(1)

        # Wait for metadata form
        log("Waiting for metadata form (upload starting)...")
        title_input = page.locator("#title-textarea #textbox")
        try:
            await title_input.first.wait_for(state="visible", timeout=120_000)
            log("Metadata form ready!")
        except PWTimeout:
            log("Metadata form timeout")
            input("Press Enter to close...")
            await context.close()
            sys.exit(1)

        await page.wait_for_timeout(1000)

        # Title
        log("Setting title...")
        tf = page.locator("#title-textarea #textbox").first
        await tf.click()
        await tf.press("Control+a")
        await tf.press("Backspace")
        await tf.type(TITLE, delay=20)
        log(f"Title: {TITLE}")

        await page.wait_for_timeout(500)

        # Description
        log("Setting description...")
        df = page.locator("#description-textarea #textbox").first
        await df.click()
        await df.press("Control+a")
        await df.press("Backspace")
        await df.type(DESCRIPTION[:4900], delay=3)
        log("Description set")

        await page.wait_for_timeout(500)

        # Not for kids
        try:
            nfk = page.locator("tp-yt-paper-radio-button[name='VIDEO_MADE_FOR_KIDS_NOT_MFK']")
            await nfk.click(timeout=8_000)
            log("Set: Not for kids")
        except:
            log("Audience: skipped")

        # NEXT x3
        for step in ["Video elements", "Checks", "Visibility"]:
            try:
                nb = page.locator("ytcp-button#next-button")
                await nb.first.click(timeout=20_000)
                log(f"Next -> {step}")
                await page.wait_for_timeout(2000)
            except PWTimeout:
                log(f"Next button timeout at {step}")
                break

        # Public
        try:
            pub = page.locator("tp-yt-paper-radio-button[name='PUBLIC']")
            await pub.first.click(timeout=20_000)
            log("Visibility: Public")
        except:
            log("Public radio: not found")

        await page.wait_for_timeout(1000)

        # Publish
        log("Publishing...")
        try:
            done = page.locator("ytcp-button#done-button")
            await done.first.click(timeout=30_000)
            log("PUBLISH clicked!")
        except PWTimeout:
            log("Publish button not found")

        # Confirm
        try:
            await page.wait_for_selector(
                "ytcp-video-share-dialog, [dialog-title*='live']",
                timeout=120_000
            )
            log("SUCCESS: Video published!")
        except PWTimeout:
            log("Could not confirm publish — check YouTube Studio manually")

        # Get URL
        try:
            vlink = await page.locator("a[href*='youtu.be'], a[href*='youtube.com/watch']").first.get_attribute("href")
            if vlink:
                log(f"Video URL: {vlink}")
        except:
            pass

        log("Done! Closing in 10 seconds...")
        await page.wait_for_timeout(10000)
        await context.close()


if __name__ == "__main__":
    asyncio.run(main())
