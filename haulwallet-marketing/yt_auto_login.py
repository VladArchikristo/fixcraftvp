#!/usr/bin/env python3
"""
YouTube auto-login + upload (stealth mode)
Uses persistent profile to save session between runs.
"""

import asyncio
import sys
from pathlib import Path

VIDEO_PATH = Path(__file__).parent / "haulwallet-promo.mp4"
PROFILE_DIR = Path.home() / ".yt_upload_profile"
PROFILE_DIR.mkdir(exist_ok=True)

EMAIL = "fixcraftvp@gmail.com"
PASSWORD = "Ahozon67"

TITLE = "HaulWallet App — Free Tool for Owner-Operators & Truck Drivers"
DESCRIPTION = """HaulWallet is the free app built for independent truck drivers and owner-operators across the USA. Stop running your trucking business from sticky notes and spreadsheets. Everything you need is right here — load board, cargo tracking, invoice generator, and fast payment tools — all in one place.

TIMESTAMPS:
0:00 The everyday chaos: paperwork, broker calls, missed money
0:12 Meet HaulWallet: your road, your rules
0:16 Find loads and compare rates instantly
0:18 Track your cargo with live map updates
0:20 Get paid fast with auto-generated invoices
0:25 What real drivers are earning with HaulWallet

WHO THIS IS FOR:
Owner-operators running 1 truck
Small fleet owners (2-5 trucks)
Dispatchers managing independent drivers
CDL drivers thinking about going independent

WHAT HAULWALLET DOES:
Load Board - Browse and accept loads in seconds. See rate per mile upfront.
Cargo Tracker - Live map with real-time ETA.
Invoice Generator - Auto-create professional invoices. PDF ready.
Fast Pay - Get paid faster. No waiting 30-45 days.
Expense Tracker - Log fuel, maintenance, tolls.
Earnings Dashboard - Weekly and monthly summaries.

Most owner-operators lose $200-$500/month to disorganized paperwork. HaulWallet fixes that.

Free to download. Free to start. Built for the road.

Download: https://haulwallet.app

#HaulWallet #TruckDriver #OwnerOperator #TruckingApp #CDLDriver #LoadBoard #TruckerLife #TruckingBusiness #FreightApp #OwnerOperatorLife"""

def log(msg):
    print(f"[YT] {msg}", flush=True)

async def main():
    from playwright.async_api import async_playwright, TimeoutError as PWTimeout

    if not VIDEO_PATH.exists():
        log(f"ERROR: Video not found: {VIDEO_PATH}")
        sys.exit(1)

    log(f"Video: {VIDEO_PATH} ({VIDEO_PATH.stat().st_size / 1_000_000:.1f} MB)")

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-infobars",
                "--disable-extensions",
                "--start-maximized",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
            ignore_default_args=["--enable-automation"],
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 900},
        )

        # Anti-detection
        await context.add_init_script("""
            delete Object.getPrototypeOf(navigator).webdriver;
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            window.chrome = {
                app: { isInstalled: false },
                webstore: { onInstallStageChanged: {}, onDownloadProgress: {} },
                runtime: {
                    PlatformOs: { MAC: 'mac', WIN: 'win', ANDROID: 'android', CROS: 'cros', LINUX: 'linux', OPENBSD: 'openbsd' },
                    PlatformArch: { ARM: 'arm', X86_32: 'x86-32', X86_64: 'x86-64' },
                    PlatformNaclArch: { ARM: 'arm', X86_32: 'x86-32', X86_64: 'x86-64' },
                    RequestUpdateCheckStatus: { THROTTLED: 'throttled', NO_UPDATE: 'no_update', UPDATE_AVAILABLE: 'update_available' },
                    OnInstalledReason: { INSTALL: 'install', UPDATE: 'update', CHROME_UPDATE: 'chrome_update', SHARED_MODULE_UPDATE: 'shared_module_update' },
                    OnRestartRequiredReason: { APP_UPDATE: 'app_update', OS_UPDATE: 'os_update', PERIODIC: 'periodic' }
                }
            };
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        """)

        page = await context.new_page()

        # Check if already logged in
        log("Going to YouTube Studio...")
        await page.goto("https://studio.youtube.com", wait_until="domcontentloaded", timeout=60_000)
        await page.wait_for_timeout(4000)

        url = page.url
        log(f"URL: {url}")

        if "accounts.google.com" in url or "signin" in url:
            log("Need to login...")

            # Check if rejected page
            if "rejected" in url:
                log("Google blocked automation login. Need manual login.")
                log("Please login manually in the browser window.")
                log("Waiting up to 3 minutes for manual login...")
                try:
                    await page.wait_for_url("**/studio.youtube.com**", timeout=180_000)
                    log("Manual login successful!")
                except PWTimeout:
                    log("Timeout waiting for login. Exiting.")
                    await context.close()
                    sys.exit(1)
            else:
                # Try auto-login
                try:
                    email_el = page.locator("input[type='email']")
                    await email_el.wait_for(state="visible", timeout=15_000)
                    await email_el.fill(EMAIL)
                    await page.wait_for_timeout(800)
                    await email_el.press("Enter")
                    log("Email submitted")
                    await page.wait_for_timeout(4000)
                except Exception as e:
                    log(f"Email error: {e}")

                # Check if rejected
                if "rejected" in page.url:
                    log("Google blocked. Waiting for manual login (3 min)...")
                    try:
                        await page.wait_for_url("**/studio.youtube.com**", timeout=180_000)
                    except PWTimeout:
                        log("Timeout. Exiting.")
                        await context.close()
                        sys.exit(1)
                else:
                    try:
                        pwd_el = page.locator("input[type='password']:visible")
                        await pwd_el.wait_for(state="visible", timeout=20_000)
                        await pwd_el.fill(PASSWORD)
                        await page.wait_for_timeout(800)
                        await pwd_el.press("Enter")
                        log("Password submitted")
                        await page.wait_for_timeout(5000)
                    except Exception as e:
                        log(f"Password error: {e}. Waiting for manual completion...")

                    log(f"Post-login URL: {page.url}")
                    if "studio.youtube.com" not in page.url:
                        log("Waiting for manual completion (2FA, etc)... up to 3 min")
                        try:
                            await page.wait_for_url("**/studio.youtube.com**", timeout=180_000)
                        except PWTimeout:
                            log("Timeout. Exiting.")
                            await context.close()
                            sys.exit(1)

        log("In YouTube Studio!")
        await page.wait_for_load_state("networkidle", timeout=30_000)
        await page.wait_for_timeout(2000)

        # Click Create
        log("Looking for Create/Upload button...")
        create_found = False
        for sel in ["#create-icon", "[aria-label='Create']", "ytcp-button:has-text('Create')"]:
            try:
                el = page.locator(sel)
                if await el.count() > 0:
                    await el.first.click(timeout=5_000)
                    log(f"Clicked Create ({sel})")
                    create_found = True
                    break
            except:
                continue

        if not create_found:
            log("Create not found, going to upload page directly...")
            await page.goto("https://www.youtube.com/upload")
            await page.wait_for_timeout(3000)

        await page.wait_for_timeout(1500)

        # Upload video option
        for sel in ["tp-yt-paper-item:has-text('Upload video')", "ytcp-menu-item:has-text('Upload video')"]:
            try:
                el = page.locator(sel)
                if await el.count() > 0:
                    await el.first.click(timeout=5_000)
                    log("Clicked 'Upload video'")
                    break
            except:
                continue

        await page.wait_for_timeout(2000)

        # File input
        log("Setting video file...")
        file_in = page.locator("input[type='file']")
        try:
            await file_in.wait_for(state="attached", timeout=30_000)
            await file_in.set_input_files(str(VIDEO_PATH))
            log("File set!")
        except PWTimeout:
            log("ERROR: No file input. Upload dialog may not have opened.")
            log("Keeping browser open for 60 seconds...")
            await page.wait_for_timeout(60_000)
            await context.close()
            sys.exit(1)

        # Wait for metadata form
        log("Waiting for metadata form (upload in progress)...")
        title_box = page.locator("#title-textarea #textbox")
        try:
            await title_box.first.wait_for(state="visible", timeout=120_000)
            log("Metadata form ready!")
        except PWTimeout:
            log("Metadata form timeout")
            await page.wait_for_timeout(30_000)
            await context.close()
            sys.exit(1)

        await page.wait_for_timeout(1000)

        # Title
        tf = page.locator("#title-textarea #textbox").first
        await tf.click()
        await tf.press("Meta+a")
        await tf.press("Backspace")
        await tf.type(TITLE, delay=30)
        log(f"Title set")

        await page.wait_for_timeout(500)

        # Description
        df = page.locator("#description-textarea #textbox").first
        await df.click()
        await df.press("Meta+a")
        await df.press("Backspace")
        await df.type(DESCRIPTION, delay=3)
        log("Description set")

        await page.wait_for_timeout(500)

        # Not for kids
        try:
            await page.locator("tp-yt-paper-radio-button[name='VIDEO_MADE_FOR_KIDS_NOT_MFK']").click(timeout=8_000)
            log("Audience: not for kids")
        except:
            log("Audience: skipped")

        # NEXT x3
        for step in ["Video elements", "Checks", "Visibility"]:
            try:
                await page.locator("ytcp-button#next-button").first.click(timeout=20_000)
                log(f"-> {step}")
                await page.wait_for_timeout(2500)
            except PWTimeout:
                log(f"NEXT timeout at {step}")
                break

        # Public
        try:
            await page.locator("tp-yt-paper-radio-button[name='PUBLIC']").first.click(timeout=15_000)
            log("Visibility: Public")
        except:
            log("Public: not found")

        await page.wait_for_timeout(1000)

        # Publish
        try:
            await page.locator("ytcp-button#done-button").first.click(timeout=30_000)
            log("PUBLISH clicked!")
        except PWTimeout:
            log("Publish button not found")

        # Confirm
        log("Waiting for confirmation...")
        try:
            await page.wait_for_selector("ytcp-video-share-dialog", timeout=120_000)
            log("SUCCESS: Video published!")
        except PWTimeout:
            log("No confirmation dialog — check YouTube Studio")

        # Video URL
        try:
            vl = await page.locator("a[href*='youtu.be']").first.get_attribute("href")
            if vl:
                log(f"Video URL: {vl}")
        except:
            pass

        log("Done! Closing in 10 seconds...")
        await page.wait_for_timeout(10_000)
        await context.close()


if __name__ == "__main__":
    log("=== YouTube Upload (Stealth) ===")
    asyncio.run(main())
