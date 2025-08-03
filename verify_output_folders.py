#!/usr/bin/env python3
"""
Script to verify that every folder in the output directory structure has at least one file.
Logs any empty directories to a CSV file.
"""

import os
import csv
from pathlib import Path
from datetime import datetime

def check_directory_has_files(directory_path):
    """
    Check if a directory contains at least one file (not just subdirectories).
    
    Args:
        directory_path (Path): Path to the directory to check
        
    Returns:
        bool: True if directory contains at least one file, False otherwise
    """
    try:
        for item in directory_path.iterdir():
            if item.is_file():
                return True
        return False
    except (OSError, PermissionError):
        return False

def verify_output_folders(output_dir="output", csv_filename="empty_folders_report.csv"):
    """
    Verify that all view folders in the output directory have at least one file.
    
    Args:
        output_dir (str): Path to the output directory
        csv_filename (str): Name of the CSV file to write the report
    """
    empty_folders = []
    total_folders_checked = 0
    
    output_path = Path(output_dir)
    
    if not output_path.exists():
        print(f"Error: Output directory '{output_dir}' does not exist!")
        return
    
    print(f"Starting verification of folders in '{output_dir}'...")
    print("=" * 60)
    
    # Get all patient directories
    patient_dirs = [d for d in output_path.iterdir() if d.is_dir()]
    
    for patient_dir in sorted(patient_dirs):
        print(f"Checking patient: {patient_dir.name}")
        
        # Get treatment directories (preTreatment, postTreatment, etc.)
        treatment_dirs = [d for d in patient_dir.iterdir() if d.is_dir()]
        
        for treatment_dir in treatment_dirs:
            # Skip if this is not a treatment directory that should have view folders
            if treatment_dir.name in ['smile_summary', 'pre_treatment_radiograph']:
                # These might have files directly, not view subdirectories
                if not check_directory_has_files(treatment_dir):
                    empty_folders.append({
                        'patient_id': patient_dir.name,
                        'treatment_type': treatment_dir.name,
                        'view_type': 'N/A',
                        'full_path': str(treatment_dir),
                        'checked_at': datetime.now().isoformat()
                    })
                    print(f"  ❌ EMPTY: {treatment_dir.name}")
                else:
                    print(f"  ✅ OK: {treatment_dir.name}")
                total_folders_checked += 1
                continue
            
            # For preTreatment and postTreatment, check view directories
            view_dirs = [d for d in treatment_dir.iterdir() if d.is_dir()]
            
            for view_dir in view_dirs:
                total_folders_checked += 1
                
                if check_directory_has_files(view_dir):
                    print(f"  ✅ OK: {treatment_dir.name}/{view_dir.name}")
                else:
                    empty_folders.append({
                        'patient_id': patient_dir.name,
                        'treatment_type': treatment_dir.name,
                        'view_type': view_dir.name,
                        'full_path': str(view_dir),
                        'checked_at': datetime.now().isoformat()
                    })
                    print(f"  ❌ EMPTY: {treatment_dir.name}/{view_dir.name}")
    
    # Write results to CSV
    if empty_folders:
        with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['patient_id', 'treatment_type', 'view_type', 'full_path', 'checked_at']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for folder in empty_folders:
                writer.writerow(folder)
        
        print("\n" + "=" * 60)
        print(f"❌ VERIFICATION FAILED!")
        print(f"Found {len(empty_folders)} empty folders out of {total_folders_checked} checked.")
        print(f"Empty folders logged to: {csv_filename}")
        
        print("\nEmpty folders summary:")
        for folder in empty_folders:
            if folder['view_type'] != 'N/A':
                print(f"  - {folder['patient_id']}: {folder['treatment_type']}/{folder['view_type']}")
            else:
                print(f"  - {folder['patient_id']}: {folder['treatment_type']}")
    else:
        print("\n" + "=" * 60)
        print(f"✅ VERIFICATION PASSED!")
        print(f"All {total_folders_checked} folders contain at least one file.")
        
        # Create an empty CSV with headers to indicate successful verification
        with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['patient_id', 'treatment_type', 'view_type', 'full_path', 'checked_at']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            # Write a comment row
            writer.writerow({
                'patient_id': '# Verification completed successfully',
                'treatment_type': f'# All {total_folders_checked} folders contain files',
                'view_type': f'# Checked at: {datetime.now().isoformat()}',
                'full_path': '# No empty folders found',
                'checked_at': ''
            })

def main():
    """Main function to run the verification."""
    try:
        verify_output_folders()
    except KeyboardInterrupt:
        print("\n\nVerification interrupted by user.")
    except Exception as e:
        print(f"\nError during verification: {e}")

if __name__ == "__main__":
    main() 