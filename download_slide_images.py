#!/usr/bin/env python3
"""
Script to download PRE_TREATMENT and POST_TREATMENT images from JSON files.
Downloads images from slides array in JSON files, excluding logo images.
Saves files in outputDownload folder under individual slide name folders.
"""

import json
import os
import requests
import sys
from pathlib import Path
from urllib.parse import urlparse
from typing import Dict, List, Any


def create_directory(path: str) -> None:
    """Create directory if it doesn't exist."""
    Path(path).mkdir(parents=True, exist_ok=True)


def download_image(url: str, file_path: str) -> bool:
    """
    Download an image from URL and save to file_path.
    
    Args:
        url: Download URL for the image
        file_path: Local path where to save the image
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        print(f"Downloading: {os.path.basename(file_path)}")
        
        # Send GET request with headers to mimic a browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, stream=True, timeout=30)
        response.raise_for_status()
        
        # Write file in chunks
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        print(f"✓ Downloaded: {os.path.basename(file_path)}")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"✗ Error downloading {os.path.basename(file_path)}: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error downloading {os.path.basename(file_path)}: {e}")
        return False


def process_json_file(json_file_path: str, output_base_dir: str) -> Dict[str, int]:
    """
    Process a single JSON file and download relevant images.
    
    Args:
        json_file_path: Path to the JSON file
        output_base_dir: Base output directory
        
    Returns:
        Dict with download statistics
    """
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"✗ Error reading {json_file_path}: {e}")
        return {"downloaded": 0, "failed": 0, "skipped": 0}
    
    # Get the case name from JSON
    case_name = data.get('name', os.path.splitext(os.path.basename(json_file_path))[0])
    
    # Create output directory for this case
    case_output_dir = os.path.join(output_base_dir, case_name)
    create_directory(case_output_dir)
    
    print(f"\nProcessing case: {case_name}")
    print(f"Output directory: {case_output_dir}")
    
    downloaded = 0
    failed = 0
    skipped = 0
    
    # Process slides
    slides = data.get('slides', [])
    
    for slide in slides:
        slide_category = slide.get('assumedCategory', '')
        
        # Only process PRE_TREATMENT and POST_TREATMENT slides
        if slide_category not in ['PRE_TREATMENT', 'POST_TREATMENT']:
            continue
            
        print(f"\n--- Processing {slide_category} slide (index {slide.get('index', 'unknown')}) ---")
        
        # Process images in the slide
        images = slide.get('images', [])
        
        for image in images:
            image_category = image.get('assumedCategory', '')
            download_url = image.get('downloadUrl', '')
            file_name = image.get('fileName', '')
            
            # Skip logo images
            if image_category == 'ZENYUM_LOGO':
                print(f"Skipping logo image")
                skipped += 1
                continue
            
            # Skip if no download URL or filename
            if not download_url or not file_name:
                print(f"Skipping image - missing download URL or filename")
                skipped += 1
                continue
            
            # Create full file path
            file_path = os.path.join(case_output_dir, file_name)
            
            # Skip if file already exists
            if os.path.exists(file_path):
                print(f"File already exists, skipping: {file_name}")
                skipped += 1
                continue
            
            # Download the image
            if download_image(download_url, file_path):
                downloaded += 1
            else:
                failed += 1
    
    return {"downloaded": downloaded, "failed": failed, "skipped": skipped}


def main():
    """Main function to process all JSON files."""
    input_dir = "inputDownload"
    output_dir = "outputDownload"
    
    # Check if input directory exists
    if not os.path.exists(input_dir):
        print(f"✗ Input directory '{input_dir}' not found!")
        sys.exit(1)
    
    # Create output directory
    create_directory(output_dir)
    
    # Get all JSON files in input directory
    json_files = [f for f in os.listdir(input_dir) if f.endswith('.json')]
    
    if not json_files:
        print(f"✗ No JSON files found in '{input_dir}'!")
        sys.exit(1)
    
    print(f"Found {len(json_files)} JSON files to process:")
    for json_file in json_files:
        print(f"  - {json_file}")
    
    # Process each JSON file
    total_downloaded = 0
    total_failed = 0
    total_skipped = 0
    
    for json_file in json_files:
        json_file_path = os.path.join(input_dir, json_file)
        stats = process_json_file(json_file_path, output_dir)
        
        total_downloaded += stats["downloaded"]
        total_failed += stats["failed"]
        total_skipped += stats["skipped"]
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"DOWNLOAD SUMMARY")
    print(f"{'='*60}")
    print(f"Total files downloaded: {total_downloaded}")
    print(f"Total files failed: {total_failed}")
    print(f"Total files skipped: {total_skipped}")
    print(f"Total files processed: {total_downloaded + total_failed + total_skipped}")
    
    if total_failed == 0:
        print(f"\n✓ All downloads completed successfully!")
    else:
        print(f"\n⚠ {total_failed} downloads failed. Check the output above for details.")


if __name__ == "__main__":
    main() 