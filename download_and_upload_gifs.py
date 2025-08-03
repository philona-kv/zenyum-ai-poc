#!/usr/bin/env python3
"""
Specialized GIF Downloader and Uploader for Dental Image Classification
This script downloads only animated GIFs from JSON files and uploads them to the latest Google Drive folder.
"""

import os
import sys
import json
import requests
import tempfile
from pathlib import Path
from datetime import datetime
import mimetypes
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import shutil

SCOPES = ['https://www.googleapis.com/auth/drive.file']

class GIFDownloadUploader:
    def __init__(self, credentials_file='credentials.json', token_file='token.json'):
        """Initialize the GIF downloader and uploader."""
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.service = None
        self.authenticate()
        self.temp_dir = tempfile.mkdtemp(prefix='gifs_')
        print(f"📁 Created temporary directory: {self.temp_dir}")
    
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
                    sys.exit(1)
                
                print("🔐 Starting OAuth flow...")
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, SCOPES)
                creds = flow.run_local_server(port=0)
            
            
            with open(self.token_file, 'w') as token:
                token.write(creds.to_json())
        
        self.service = build('drive', 'v3', credentials=creds)
        print("✅ Successfully authenticated with Google Drive!")
    
    def find_latest_drive_folder(self):
        """Find the latest/most recent folder in Google Drive that contains dental image classification data."""
        try:
            query = "mimeType='application/vnd.google-apps.folder' and (name contains 'DentalImageClassification' or name contains 'dental' or name contains 'Dental')"
            results = self.service.files().list(
                q=query,
                orderBy='modifiedTime desc',
                fields='files(id, name, modifiedTime, parents)'
            ).execute()
            
            folders = results.get('files', [])
            
            if not folders:
                query = "mimeType='application/vnd.google-apps.folder'"
                results = self.service.files().list(
                    q=query,
                    orderBy='modifiedTime desc',
                    pageSize=10,
                    fields='files(id, name, modifiedTime)'
                ).execute()
                folders = results.get('files', [])
            
            if folders:
                latest_folder = folders[0]
                print(f"📁 Found latest folder: {latest_folder['name']} (ID: {latest_folder['id']})")
                return latest_folder['id']
            else:
                print("⚠️ No suitable folders found. Will upload to root directory.")
                return None
                
        except Exception as e:
            print(f"❌ Error finding latest folder: {e}")
            print("💡 You can manually specify a folder ID by setting DRIVE_FOLDER_ID environment variable")
            manual_folder_id = os.environ.get('DRIVE_FOLDER_ID')
            if manual_folder_id:
                print(f"📁 Using manually specified folder ID: {manual_folder_id}")
                return manual_folder_id
            return None
    
    def download_gif_from_google_drive(self, file_id, output_path):
        """Download a GIF file from Google Drive without PIL verification to preserve animation."""
        try:
            url = f"https://drive.google.com/uc?id={file_id}&export=download"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            session = requests.Session()
            response = session.get(url, headers=headers, stream=True)
            

            if response.status_code == 200:
                if 'download_warning' in response.text or 'virus scan' in response.text.lower():
                    for line in response.text.split('\n'):
                        if 'confirm=' in line:
                            confirm_token = line.split('confirm=')[1].split('&')[0].split('"')[0]
                            break
                    else:
                        confirm_token = 't'
                    
                    url = f"https://drive.google.com/uc?export=download&confirm={confirm_token}&id={file_id}"
                    response = session.get(url, headers=headers, stream=True)
            
            response.raise_for_status()
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            
            if os.path.getsize(output_path) < 1000:
                print(f"⚠️ Downloaded file seems too small, might be an error page")
                return False
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to download GIF from {file_id}: {e}")
            return False
    
    def download_regular_gif(self, url, output_path):
        """Download GIF from regular URL."""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, stream=True, timeout=30)
            response.raise_for_status()
            
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to download {url}: {e}")
            return False
    
    def upload_file_to_drive(self, file_path, folder_id=None, filename=None):
        """Upload a file to Google Drive."""
        if not os.path.exists(file_path):
            print(f"❌ File not found: {file_path}")
            return None
        
        if not filename:
            filename = os.path.basename(file_path)
        
        
        mime_type = 'image/gif'
        
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
    
    def filter_gif_containing_jsons(self, json_dir="inputJsons"):
        """Pre-filter JSON files that likely contain GIFs (from 50_ZC onwards)."""
        json_path = Path(json_dir)
        
        if not json_path.exists():
            print(f"❌ JSON directory not found: {json_dir}")
            return []
        
        all_json_files = list(json_path.glob("*.json"))
        if not all_json_files:
            print(f"❌ No JSON files found in {json_dir}")
            return []
        
        
        gif_candidate_files = []
        for json_file in all_json_files:
            filename = json_file.stem
            try:
                if '_' in filename:
                    case_num_str = filename.split('_')[0]
                    if case_num_str.isdigit():
                        case_num = int(case_num_str)
                        if case_num >= 50:
                            gif_candidate_files.append(json_file)
                    else:
                        for i, char in enumerate(case_num_str):
                            if not char.isdigit():
                                break
                        if i > 0:
                            case_num = int(case_num_str[:i])
                            if case_num >= 50:
                                gif_candidate_files.append(json_file)
            except (ValueError, IndexError):
                gif_candidate_files.append(json_file)
        
        print(f"🔍 Filtered {len(gif_candidate_files)} JSON files (from 50_ZC onwards) out of {len(all_json_files)} total")
        return sorted(gif_candidate_files)
    
    def process_json_files(self, json_dir="inputJsons"):
        """Process filtered JSON files to find and download GIFs."""
        from tqdm import tqdm
        
        json_files = self.filter_gif_containing_jsons(json_dir)
        
        if not json_files:
            print("❌ No JSON files found that likely contain GIFs")
            return []
        
        downloaded_gifs = []
        
        with tqdm(total=len(json_files), desc="🎬 Processing JSON files", unit="file") as pbar:
            for json_file in json_files:
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    case_name = data.get('name', json_file.stem)
                    pbar.set_description(f"🎬 Processing: {case_name}")
                    
                    slides = data.get('slides', [])
                    gif_found = False
                    
                    for slide in slides:
                        images = slide.get('images', [])
                        for image in images:
                            content_type = image.get('contentType', '')
                            assumed_category = image.get('assumedCategory', '')
                            
                            if content_type == 'image/gif' or assumed_category == 'SMILE_SUMMARY_ANIMATION':
                                download_url = image.get('downloadUrl', '')
                                filename = image.get('fileName', f"{case_name}_animation.gif")
                                
                                if download_url:
                                    gif_found = True
                                    output_path = os.path.join(self.temp_dir, filename)
                                    
                                    success = False
                                    if 'drive.google.com' in download_url and 'id=' in download_url:
                                        file_id = download_url.split('id=')[1].split('&')[0]
                                        success = self.download_gif_from_google_drive(file_id, output_path)
                                    else:
                                        success = self.download_regular_gif(download_url, output_path)
                                    
                                    if success and os.path.exists(output_path):
                                        downloaded_gifs.append(output_path)
                                        tqdm.write(f"✅ Downloaded: {filename} ({os.path.getsize(output_path):,} bytes)")
                                    else:
                                        tqdm.write(f"❌ Failed to download: {filename}")
                                else:
                                    tqdm.write(f"⚠️ No download URL for GIF in {case_name}")
                    
                    if not gif_found:
                        tqdm.write(f"⚠️ No GIFs found in {case_name}")
                        
                except Exception as e:
                    tqdm.write(f"❌ Error processing {json_file}: {e}")
                
                pbar.update(1)
        
        return downloaded_gifs
    
    def create_gif_folder(self):
        """Create a dedicated 'Animation GIFs' folder in Google Drive."""
        try:
            query = "mimeType='application/vnd.google-apps.folder' and name='Animation GIFs'"
            results = self.service.files().list(
                q=query,
                fields='files(id, name)'
            ).execute()
            
            existing_folders = results.get('files', [])
            
            if existing_folders:
                folder_id = existing_folders[0]['id']
                print(f"📁 Found existing 'Animation GIFs' folder (ID: {folder_id})")
                return folder_id
            else:
                folder_metadata = {
                    'name': 'Animation GIFs',
                    'mimeType': 'application/vnd.google-apps.folder'
                }
                
                folder = self.service.files().create(
                    body=folder_metadata,
                    fields='id'
                ).execute()
                
                folder_id = folder.get('id')
                print(f"📁 Created new 'Animation GIFs' folder (ID: {folder_id})")
                return folder_id
                
        except Exception as e:
            print(f"❌ Error creating/finding Animation GIFs folder: {e}")
            return None
    
    def create_patient_smile_folder(self, patient_id, main_gif_folder_id):
        """Create patient folder and smile_summary subfolder structure."""
        try:
            query = f"mimeType='application/vnd.google-apps.folder' and name='{patient_id}' and '{main_gif_folder_id}' in parents"
            results = self.service.files().list(
                q=query,
                fields='files(id, name)'
            ).execute()
            
            patient_folders = results.get('files', [])
            
            if patient_folders:
                patient_folder_id = patient_folders[0]['id']
            else:
                patient_metadata = {
                    'name': patient_id,
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [main_gif_folder_id]
                }
                
                patient_folder = self.service.files().create(
                    body=patient_metadata,
                    fields='id'
                ).execute()
                
                patient_folder_id = patient_folder.get('id')
            
            
            query = f"mimeType='application/vnd.google-apps.folder' and name='smile_summary' and '{patient_folder_id}' in parents"
            results = self.service.files().list(
                q=query,
                fields='files(id, name)'
            ).execute()
            
            smile_folders = results.get('files', [])
            
            if smile_folders:
                smile_folder_id = smile_folders[0]['id']
            else:
                
                smile_metadata = {
                    'name': 'smile_summary',
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [patient_folder_id]
                }
                
                smile_folder = self.service.files().create(
                    body=smile_metadata,
                    fields='id'
                ).execute()
                
                smile_folder_id = smile_folder.get('id')
            
            return smile_folder_id
            
        except Exception as e:
            print(f"❌ Error creating patient folder structure for {patient_id}: {e}")
            return None
    
    def extract_patient_id_from_filename(self, filename):
        """Extract patient ID from GIF filename (e.g., '50_ZC_SG' from '50_ZC_SG_Slide8_SMILE_SUMMARY_ANIMATION_Img2.gif')."""
        try:
            parts = filename.split('_')
            if len(parts) >= 3:
                return f"{parts[0]}_{parts[1]}_{parts[2]}"
            elif len(parts) >= 2:
                return f"{parts[0]}_{parts[1]}"
            else:
                return parts[0]
        except:
            return filename.split('.')[0]
    
    def upload_gifs_to_drive(self, gif_files, target_folder_id=None):
        """Upload all downloaded GIFs to organized Animation GIFs folder structure."""
        from tqdm import tqdm
        
        if not gif_files:
            print("❌ No GIF files to upload")
            return
        
        
        gif_folder_id = self.create_gif_folder()
        if not gif_folder_id:
            print("❌ Could not create/find Animation GIFs folder")
            return
        
        print(f"\n🚀 Starting upload of {len(gif_files)} GIF files with organized folder structure...")
        
        uploaded_count = 0
        with tqdm(total=len(gif_files), desc="📤 Uploading GIFs", unit="file") as pbar:
            for gif_file in gif_files:
                filename = os.path.basename(gif_file)
                patient_id = self.extract_patient_id_from_filename(filename)
                
                pbar.set_description(f"📤 Uploading: {patient_id}")
                
                
                smile_folder_id = self.create_patient_smile_folder(patient_id, gif_folder_id)
                
                if smile_folder_id and self.upload_file_to_drive(gif_file, smile_folder_id, filename):
                    uploaded_count += 1
                    tqdm.write(f"✅ Uploaded: {patient_id}/smile_summary/{filename}")
                else:
                    tqdm.write(f"❌ Failed to upload: {filename}")
                
                pbar.update(1)
        
        print(f"\n🎉 Upload completed! {uploaded_count}/{len(gif_files)} GIFs uploaded successfully with organized structure.")
    
    def cleanup(self):
        """Clean up temporary directory."""
        try:
            shutil.rmtree(self.temp_dir)
            print(f"🧹 Cleaned up temporary directory: {self.temp_dir}")
        except Exception as e:
            print(f"⚠️ Could not clean up temporary directory: {e}")
    
    def run(self):
        """Main execution method."""
        try:
            print("🎬 Starting GIF Download and Upload Process")
            print("=" * 60)
            
            
            gif_files = self.process_json_files()
            
            if not gif_files:
                print("❌ No GIF files were downloaded successfully")
                return
            
            
            self.upload_gifs_to_drive(gif_files)
            
        finally:
            
            self.cleanup()

def main():
    """Main function."""
    if not os.path.exists('credentials.json'):
        print("❌ Error: credentials.json not found!")
        print("Please download the credentials file from Google Cloud Console.")
        print("Follow the setup instructions in README_GoogleDrive.md")
        return
    
    try:
        downloader = GIFDownloadUploader()
        downloader.run()
    except KeyboardInterrupt:
        print("\n⏹️ Process interrupted by user")
    except Exception as e:
        print(f"❌ An error occurred: {e}")

if __name__ == "__main__":
    main() 