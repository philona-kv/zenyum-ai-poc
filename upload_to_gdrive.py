#!/usr/bin/env python3
"""
Google Drive Upload Script for Dental Image Classification Output
This script uploads all output folders to Google Drive with proper folder structure.
"""

import os
import sys
from pathlib import Path
import mimetypes
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from tqdm import tqdm
import json


SCOPES = ['https://www.googleapis.com/auth/drive.file']

class GoogleDriveUploader:
    def __init__(self, credentials_file='credentials.json', token_file='token.json'):
        """Initialize the Google Drive uploader with authentication."""
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.service = None
        self.authenticate()
    
    def authenticate(self):
        """Authenticate with Google Drive API."""
        creds = None
        
        
        if os.path.exists(self.token_file):
            creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)
        
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                print("🔄 Refreshing expired credentials...")
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_file):
                    print(f"❌ Error: {self.credentials_file} not found!")
                    print("Please download the credentials file from Google Cloud Console.")
                    print("Follow the setup instructions in the README.")
                    sys.exit(1)
                
                print("🔐 Starting OAuth flow...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, SCOPES)
                creds = flow.run_local_server(port=0)
            
            
            with open(self.token_file, 'w') as token:
                token.write(creds.to_json())
        
        self.service = build('drive', 'v3', credentials=creds)
        print("✅ Successfully authenticated with Google Drive!")
    
    def create_folder(self, name, parent_id=None):
        """Create a folder in Google Drive."""
        folder_metadata = {
            'name': name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        
        if parent_id:
            folder_metadata['parents'] = [parent_id]
        
        try:
            folder = self.service.files().create(
                body=folder_metadata,
                fields='id'
            ).execute()
            return folder.get('id')
        except Exception as e:
            print(f"❌ Error creating folder '{name}': {e}")
            return None
    
    def upload_file(self, file_path, folder_id=None, filename=None):
        """Upload a single file to Google Drive."""
        if not os.path.exists(file_path):
            print(f"❌ File not found: {file_path}")
            return None
        
        if not filename:
            filename = os.path.basename(file_path)
        
        
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = 'application/octet-stream'
        
        file_metadata = {'name': filename}
        if folder_id:
            file_metadata['parents'] = [folder_id]
        
        try:
            media = MediaFileUpload(file_path, mimetype=mime_type, resumable=True)
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            return file.get('id')
        except Exception as e:
            print(f"❌ Error uploading file '{filename}': {e}")
            return None
    
    def upload_directory(self, local_path, parent_folder_id=None, progress_callback=None):
        """Recursively upload a directory to Google Drive."""
        local_path = Path(local_path)
        
        if not local_path.exists():
            print(f"❌ Directory not found: {local_path}")
            return None
        
        
        folder_id = self.create_folder(local_path.name, parent_folder_id)
        if not folder_id:
            return None
        
        print(f"📁 Created folder: {local_path.name}")
        
        
        all_items = list(local_path.rglob('*'))
        files = [item for item in all_items if item.is_file()]
        dirs = [item for item in all_items if item.is_dir()]
        
        
        for file_path in files:
            if file_path.parent == local_path:
                filename = file_path.name
                print(f"📤 Uploading: {filename}")
                self.upload_file(str(file_path), folder_id, filename)
                if progress_callback:
                    progress_callback()
        
        
        for dir_path in dirs:
            if dir_path.parent == local_path:
                self.upload_directory(str(dir_path), folder_id, progress_callback)
        
        return folder_id
    
    def upload_output_folders(self, base_path='.'):
        """Upload all output folders from the project."""
        base_path = Path(base_path)
        
        
        output_dirs = []
        for item in base_path.iterdir():
            if item.is_dir() and item.name.startswith('output'):
                output_dirs.append(item)
        
        if not output_dirs:
            print("❌ No output directories found!")
            return
        
        print(f"🔍 Found {len(output_dirs)} output directories:")
        for dir_path in output_dirs:
            print(f"  - {dir_path.name}")
        
        
        project_folder_id = self.create_folder("DentalImageClassification_Output")
        if not project_folder_id:
            print("❌ Failed to create main project folder!")
            return
        
        print(f"📁 Created main project folder in Google Drive")
        
        
        total_files = 0
        for output_dir in output_dirs:
            total_files += sum(1 for _ in output_dir.rglob('*') if _.is_file())
        
        print(f"📊 Total files to upload: {total_files}")
        
        
        uploaded_files = 0
        
        def progress_callback():
            nonlocal uploaded_files
            uploaded_files += 1
            if uploaded_files % 10 == 0:
                print(f"📈 Progress: {uploaded_files}/{total_files} files uploaded")
        
        for output_dir in output_dirs:
            print(f"\n🚀 Uploading {output_dir.name}...")
            self.upload_directory(str(output_dir), project_folder_id, progress_callback)
        
        print(f"\n🎉 Upload completed! {uploaded_files} files uploaded to Google Drive.")
        print(f"📁 All files are in the 'DentalImageClassification_Output' folder in your Google Drive.")


def main():
    """Main function to upload output folders to Google Drive."""
    print("🚀 Google Drive Upload Tool for Dental Image Classification")
    print("="*60)
    
    
    try:
        uploader = GoogleDriveUploader()
        uploader.upload_output_folders()
        
    except Exception as e:
        print(f"❌ An error occurred: {e}")
        print("💡 Make sure you have proper internet connection and valid credentials.")


if __name__ == "__main__":
    main() 