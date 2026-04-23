"""
Google Drive File Viewer & Interactor
======================================
Simple script to see and interact with files in your Google Drive.

Installation:
    pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client

Setup (one-time):
    1. Go to: https://console.cloud.google.com
    2. Create project and enable Google Drive API
    3. Create OAuth 2.0 Credentials (Desktop Application)
    4. Download credentials.json and save to project root
    5. Run: python google_drive_auth.py
"""

import pickle
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient import discovery
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
CREDS_FILE = PROJECT_ROOT / "credentials.json"
TOKEN_FILE = PROJECT_ROOT / ".google_drive_token.pickle"
SCOPES = ["https://www.googleapis.com/auth/drive"]


def authenticate():
    """Authenticate with Google Drive."""
    creds = None

    if TOKEN_FILE.exists():
        with open(TOKEN_FILE, "rb") as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDS_FILE.exists():
                print(f"❌ Missing credentials.json")
                print("   1. Go to https://console.cloud.google.com")
                print("   2. Enable Google Drive API")
                print("   3. Create OAuth credentials (Desktop)")
                print("   4. Save as credentials.json in project root")
                return None

            flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "wb") as token:
            pickle.dump(creds, token)

    return discovery.build("drive", "v3", credentials=creds)


def list_files(service, limit=20):
    """List all files in Google Drive."""
    results = service.files().list(
        pageSize=limit,
        fields="files(id, name, mimeType, modifiedTime, size)",
        orderBy="modifiedTime desc"
    ).execute()

    files = results.get("files", [])
    
    if not files:
        print("No files found.")
        return []

    print(f"\n{'Filename':<40} {'Type':<15} {'Size':<10} {'Modified':<19}")
    print("-" * 90)
    
    for file in files:
        name = file["name"][:39]
        mime = file.get("mimeType", "").split("/")[-1][:14]
        size = file.get("size", "0")
        size_str = f"{int(size) / 1024 / 1024:.1f}MB" if int(size) > 0 else "-"
        modified = file.get("modifiedTime", "")[:10]
        
        print(f"{name:<40} {mime:<15} {size_str:<10} {modified:<19}")
    
    return files


def download_file(service, file_name, save_path=None):
    """Download a file from Google Drive."""
    query = f"name='{file_name}' and trashed=false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])
    
    if not files:
        print(f"❌ File '{file_name}' not found")
        return None
    
    file_id = files[0]["id"]
    
    if save_path is None:
        save_path = PROJECT_ROOT / file_name
    
    request = service.files().get_media(fileId=file_id)
    with open(save_path, "wb") as f:
        f.write(request.execute())
    
    print(f"✓ Downloaded '{file_name}' to {save_path}")
    return save_path


def upload_file(service, file_path, folder_name=None):
    """Upload a file to Google Drive."""
    file_path = Path(file_path)
    
    if not file_path.exists():
        print(f"❌ File '{file_path}' not found")
        return None
    
    file_metadata = {"name": file_path.name}
    media = discovery.MediaFileUpload(file_path)
    
    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id, name"
    ).execute()
    
    print(f"✓ Uploaded '{file_path.name}' to Google Drive")
    return file


# ============================================================================
# Main
# ============================================================================
if __name__ == "__main__":
    print("🔐 Connecting to Google Drive...")
    service = authenticate()
    
    if not service:
        exit(1)
    
    print("✓ Connected!\n")
    
    # List files
    print("Your Google Drive files:")
    list_files(service, limit=20)
    
    # Examples
    print("\n" + "="*90)
    print("USAGE EXAMPLES:")
    print("="*90)
    print("\nIn Python:")
    print("  service = authenticate()")
    print("  list_files(service)  # See all files")
    print("  download_file(service, 'my_file.csv')  # Download")
    print("  upload_file(service, 'data.csv')  # Upload")
