#!/usr/bin/env python3
"""
HaulWallet Google Play AAB-only upload script
Uses Google Play Android Developer API v3
Skips store listing, screenshots, feature graphic
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
AAB_DIR = os.path.expanduser("~/Папка тест/fixcraftvp/toll-navigator/builds")

import glob
def find_latest_aab():
    files = glob.glob(os.path.join(AAB_DIR, "haulwallet-v*.aab"))
    if not files:
        return None
    return max(files, key=os.path.getmtime)

AAB_PATH = find_latest_aab() or os.path.join(AAB_DIR, "haulwallet-v9.aab")

SCOPES = ["https://www.googleapis.com/auth/androidpublisher"]

def get_credentials():
    return service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )

def upload_bundle(service, edit_id):
    print(f"Uploading AAB: {AAB_PATH}")
    if not os.path.exists(AAB_PATH):
        print("ERROR: AAB file not found!")
        return None

    media = MediaFileUpload(
        AAB_PATH,
        mimetype="application/octet-stream",
        resumable=True
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

def assign_to_track(service, edit_id, version_code, track="internal"):
    print(f"Assigning version {version_code} to '{track}' track...")
    track_body = {
        "releases": [{
            "versionCodes": [str(version_code)],
            "status": "draft"
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
    print("HaulWallet → Google Play Console AAB-only Upload")
    print("=" * 60)

    creds = get_credentials()
    service = build("androidpublisher", "v3", credentials=creds)

    # Create edit
    print("\nCreating new edit...")
    edit = service.edits().insert(packageName=PACKAGE_NAME).execute()
    edit_id = edit["id"]
    print(f"✅ Edit created: {edit_id}")

    try:
        # Upload AAB
        version_code = upload_bundle(service, edit_id)

        if version_code:
            # Assign to internal track
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
