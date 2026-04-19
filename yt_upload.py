#!/usr/bin/env python3
"""YouTube upload script via Playwright browser automation"""
import asyncio
import os
from playwright.async_api import async_playwright

VIDEO_PATH = os.path.expanduser("~/Папка тест/fixcraftvp/haulwallet-marketing/haulwallet-promo.mp4")
EMAIL = "fixcraftvp@gmail.com"
PASSWORD = "Ahozon67"

VIDEO_TITLE = "HaulWallet — Smart Load Management for Truckers"
VIDEO_DESC = """HaulWallet helps truck drivers and fleet managers track loads, manage earnings, and navigate smarter.

✅ Real-time GPS navigation
✅ Load tracking & earnings management
✅ Fuel cost optimization
✅ Digital document storage

Download HaulWallet on Google Play!

#trucking #logistics #fleetmanagement #hauling #truckdriver"""
TAGS = "trucking,logistics,truck driver,fleet management,haul wallet,load management,gps navigation"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=500)
        context = await browser.new_context()
        page = await context.new_page()

        print("Opening YouTube Studio...")
        await page.goto("https://accounts.google.com/signin/v2/identifier?service=youtube")
        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(2)

        print("Entering email...")
        await page.fill('input[type="email"]', EMAIL)
        await page.press('input[type="email"]', "Enter")
        await asyncio.sleep(3)

        print("Entering password...")
        await page.fill('input[type="password"]', PASSWORD)
        await page.press('input[type="password"]', "Enter")
        await asyncio.sleep(5)

        print("Going to YouTube Studio...")
        await page.goto("https://studio.youtube.com")
        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(4)

        print(f"Current URL: {page.url}")

        # Click CREATE button
        print("Looking for upload button...")
        try:
            create_btn = page.locator("ytcp-button#create-icon, button[aria-label='Create'], ytcp-icon-button[id='create-icon']")
            await create_btn.first.click(timeout=10000)
            await asyncio.sleep(2)

            # Click "Upload videos"
            upload_option = page.locator("tp-yt-paper-item:has-text('Upload videos'), ytcp-ve:has-text('Upload videos')")
            await upload_option.first.click(timeout=10000)
            await asyncio.sleep(2)
        except Exception as e:
            print(f"Create button error: {e}")
            # Try direct navigation to upload
            await page.goto("https://www.youtube.com/upload")
            await asyncio.sleep(3)

        print("Setting video file...")
        try:
            file_input = page.locator('input[type="file"]')
            await file_input.set_input_files(VIDEO_PATH, timeout=10000)
            print("File set successfully!")
        except Exception as e:
            print(f"File input error: {e}")
            # Try to find hidden file input
            await page.evaluate("document.querySelector('input[type=file]').style.display = 'block'")
            file_input = page.locator('input[type="file"]')
            await file_input.set_input_files(VIDEO_PATH)

        await asyncio.sleep(5)
        print("Waiting for upload form...")

        # Fill title
        try:
            title_field = page.locator('#textbox[aria-label*="Title"], ytcp-social-suggestions-textbox[id="title-textarea"] #textbox')
            await title_field.first.click()
            await title_field.first.fill("")
            await title_field.first.type(VIDEO_TITLE)
            print("Title filled!")
        except Exception as e:
            print(f"Title error: {e}")

        await asyncio.sleep(1)

        # Fill description
        try:
            desc_field = page.locator('#textbox[aria-label*="Description"], ytcp-social-suggestions-textbox[id="description-textarea"] #textbox')
            await desc_field.first.click()
            await desc_field.first.fill(VIDEO_DESC)
            print("Description filled!")
        except Exception as e:
            print(f"Description error: {e}")

        await asyncio.sleep(1)

        # Select "Not made for kids"
        try:
            no_kids = page.locator('tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT"]')
            await no_kids.click(timeout=5000)
            print("Not for kids selected!")
        except Exception as e:
            print(f"Kids radio error: {e}")

        # Click Next through details
        for i in range(3):
            try:
                next_btn = page.locator('ytcp-button#next-button, button:has-text("Next")')
                await next_btn.first.click(timeout=5000)
                await asyncio.sleep(2)
                print(f"Clicked Next ({i+1}/3)")
            except Exception as e:
                print(f"Next button {i+1} error: {e}")

        # Set to Public and Publish
        try:
            public_radio = page.locator('tp-yt-paper-radio-button[name="PUBLIC"]')
            await public_radio.click(timeout=5000)
            print("Set to Public!")
            await asyncio.sleep(1)

            publish_btn = page.locator('ytcp-button#done-button, button:has-text("Publish")')
            await publish_btn.first.click(timeout=10000)
            print("PUBLISHED!")
            await asyncio.sleep(10)
        except Exception as e:
            print(f"Publish error: {e}")

        print(f"Final URL: {page.url}")

        # Take screenshot
        await page.screenshot(path="/Users/vladimirprihodko/Папка тест/fixcraftvp/yt_result.png")
        print("Screenshot saved to yt_result.png")

        await asyncio.sleep(5)
        await browser.close()

asyncio.run(main())
