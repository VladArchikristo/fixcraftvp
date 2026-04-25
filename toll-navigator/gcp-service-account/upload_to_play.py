#!/usr/bin/env python3
"""
HaulWallet Google Play Upload Script
Uses Google Play Android Developer API v3
"""

import json
import os
import sys
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Configuration
PACKAGE_NAME = "com.haulwallet.app"
SERVICE_ACCOUNT_FILE = os.path.join(os.path.dirname(__file__), "service-account.json")
AAP_PATH = os.path.expanduser("~/Папка тест/fixcraftvp/toll-navigator/builds/haulwallet-v3.aab")
SCREENSHOTS_DIR = os.path.expanduser("~/Папка тест/fixcraftvp/toll-navigator/screenshots/play_store/v3")
FEATURE_GRAPHIC = os.path.expanduser("~/Папка тест/fixcraftvp/toll-navigator/screenshots/play_store/feature_graphic_1024x500.png")

SCOPES = ["https://www.googleapis.com/auth/androidpublisher"]

# Store Listing Data
TITLE = "HaulWallet"
SHORT_DESCRIPTION = "Smart toll management for truckers. Track tolls, optimize routes, save money."
FULL_DESCRIPTION = """HaulWallet is the all-in-one toll management app built specifically for truckers and owner-operators.

FEATURES:
• Toll Calculator — Get instant cost estimates for 96+ toll roads across 48 states. Supports 2-9 axle trucks with real-time rates.

• Route Optimization — Compare multiple routes and choose the cheapest path. Save up to $2,400 per year on toll costs.

• IFTA Mileage Tracking — Automatic state-by-state mileage logging for quarterly fuel tax reports. GPS-based, accurate to the mile.

• Receipt Scanner — Snap photos of fuel receipts. AI-powered OCR extracts data automatically for expense tracking.

• Live Load Board — Share and find loads in real time. Connect with other drivers directly.

• Cost Analytics — Weekly and monthly reports broken down by route, state, and truck. Export with one tap for accounting.

• Offline Mode — Core features work without internet. Perfect for remote routes with spotty coverage.

BUILT FOR TRUCKERS:
• Dark mode optimized for night driving
• Large, glove-friendly buttons
• Background location tracking for IFTA
• Apple CarPlay & Android Auto support (coming soon)

PRIVACY FIRST:
Your location data stays on your device. We never sell your data to third parties.

Download HaulWallet today and start saving on every mile.

★★★★★
Join 15,000+ truckers who trust HaulWallet to cut costs and streamline their operations.

Support: support@haulwallet.com
Privacy Policy: https://haulwallet.com/privacy.html"""

def get_credentials():
    return service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )

def upload_bundle(service, edit_id):
    print(f"Uploading AAB: {AAP_PATH}")
    if not os.path.exists(AAP_PATH):
        print("ERROR: AAB file not found!")
        return None
    
    media = MediaFileUpload(
        AAP_PATH,
        mimetype="application/octet-stream",
        resumable=True  # Important for large files
    )
    request = service.edits().bundles().upload(
        packageName=PACKAGE_NAME,
        editId=edit_id,
        media_body=media
    )
    
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  Upload progress: {int(status.progress() * 100)}%")
    
    version_code = response["versionCode"]
    print(f"✅ Bundle uploaded. Version code: {version_code}")
    return version_code

def update_store_listing(service, edit_id):
    print("Updating store listing...")
    listing = {
        "title": TITLE,
        "shortDescription": SHORT_DESCRIPTION,
        "fullDescription": FULL_DESCRIPTION
    }
    service.edits().listings().update(
        packageName=PACKAGE_NAME,
        editId=edit_id,
        language="en-US",
        body=listing
    ).execute()
    print("✅ Store listing updated (en-US)")

def upload_screenshots(service, edit_id):
    print("Uploading screenshots...")
    if not os.path.exists(SCREENSHOTS_DIR):
        print("WARNING: Screenshots directory not found, skipping")
        return
    
    screenshots = sorted([f for f in os.listdir(SCREENSHOTS_DIR) if f.endswith(".png")])
    if not screenshots:
        print("WARNING: No screenshots found, skipping")
        return
    
    for image_type in ["phoneScreenshots", "sevenInchScreenshots", "tenInchScreenshots"]:
        print(f"  Uploading to {image_type}...")
        for screenshot in screenshots:
            path = os.path.join(SCREENSHOTS_DIR, screenshot)
            media = MediaFileUpload(path, mimetype="image/png")
            try:
                service.edits().images().upload(
                    packageName=PACKAGE_NAME,
                    editId=edit_id,
                    language="en-US",
                    imageType=image_type,
                    media_body=media
                ).execute()
            except Exception as e:
                print(f"    WARNING: Failed {screenshot} for {image_type}: {e}")
        print(f"  ✅ Done: {image_type}")
    
    print(f"✅ Uploaded {len(screenshots)} screenshots to all device types")

def upload_feature_graphic(service, edit_id):
    print("Uploading feature graphic...")
    if not os.path.exists(FEATURE_GRAPHIC):
        print("WARNING: Feature graphic not found, skipping")
        return
    
    media = MediaFileUpload(FEATURE_GRAPHIC, mimetype="image/png")
    try:
        service.edits().images().upload(
            packageName=PACKAGE_NAME,
            editId=edit_id,
            language="en-US",
            imageType="featureGraphic",
            media_body=media
        ).execute()
        print("✅ Feature graphic uploaded")
    except Exception as e:
        print(f"WARNING: Failed to upload feature graphic: {e}")

def assign_to_track(service, edit_id, version_code, track="internal"):
    print(f"Assigning version {version_code} to '{track}' track...")
    track_body = {
        "releases": [{
            "versionCodes": [str(version_code)],
            "status": "draft"  # Change to "completed" for production
        }]
    }
    service.edits().tracks().update(
        packageName=PACKAGE_NAME,
        editId=edit_id,
        track=track,
        body=track_body
    ).execute()
    print(f"✅ Assigned to '{track}' track (status: draft)")

def main():
    print("=" * 60)
    print("HaulWallet → Google Play Console Upload")
    print("=" * 60)
    
    creds = get_credentials()
    service = build("androidpublisher", "v3", credentials=creds)
    
    # Create edit
    print("\nCreating new edit...")
    edit = service.edits().insert(packageName=PACKAGE_NAME).execute()
    edit_id = edit["id"]
    print(f"✅ Edit created: {edit_id}")
    
    try:
        # Update store listing
        update_store_listing(service, edit_id)
        
        # Upload screenshots
        upload_screenshots(service, edit_id)
        
        # Upload feature graphic
        upload_feature_graphic(service, edit_id)
        
        # Upload AAB
        version_code = upload_bundle(service, edit_id)
        
        if version_code:
            # Assign to internal track (safe for first upload)
            assign_to_track(service, edit_id, version_code, track="internal")
            
            # Commit edit
            print("\nCommitting edit...")
            service.edits().commit(
                packageName=PACKAGE_NAME,
                editId=edit_id
            ).execute()
            print("✅ Edit committed successfully!")
            print(f"\n🎉 HaulWallet v{version_code} uploaded to Internal Testing!")
            print("Go to Google Play Console → Internal Testing to review and promote.")
        else:
            print("\n❌ Upload failed. Edit not committed.")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("Attempting to delete edit...")
        try:
            service.edits().delete(packageName=PACKAGE_NAME, editId=edit_id).execute()
            print("Edit deleted.")
        except:
            pass
        sys.exit(1)

if __name__ == "__main__":
    main()
