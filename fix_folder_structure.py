#!/usr/bin/env python3

import os

OUTPUT_BASE_DIR = "output"
LABELED_DIR = "labeled_samples"

def get_classification_categories():
    """Get all available classification categories from labeled_samples directory"""
    categories = []
    if os.path.exists(LABELED_DIR):
        for item in os.listdir(LABELED_DIR):
            item_path = os.path.join(LABELED_DIR, item)
            if os.path.isdir(item_path):
                categories.append(item)
    return sorted(categories)

def fix_existing_folder_structure():
    """Fix folder structure for all existing case folders in output directory"""
    if not os.path.exists(OUTPUT_BASE_DIR):
        print(f"❌ Output directory {OUTPUT_BASE_DIR} not found!")
        return
    
    print("🔧 Fixing existing folder structure...")
    classification_categories = get_classification_categories()
    categories_with_classification = ['preTreatment', 'postTreatment']
    
    if not classification_categories:
        print(f"❌ No classification categories found in {LABELED_DIR}")
        return
    
    print(f"📁 Found classification categories: {classification_categories}")
    
    cases_processed = 0
    folders_created = 0
    
    for case_folder in os.listdir(OUTPUT_BASE_DIR):
        case_path = os.path.join(OUTPUT_BASE_DIR, case_folder)
        if os.path.isdir(case_path):
            print(f"\n🔄 Processing case: {case_folder}")
            case_folders_created = 0
            
            for category_folder in categories_with_classification:
                category_path = os.path.join(case_path, category_folder)
                
                if os.path.exists(category_path):
                    print(f"  📂 Found {category_folder} folder")
                    
                    for class_name in classification_categories:
                        class_folder_path = os.path.join(category_path, class_name)
                        
                        if not os.path.exists(class_folder_path):
                            os.makedirs(class_folder_path, exist_ok=True)
                            print(f"    ✅ Created: {class_name}")
                            case_folders_created += 1
                            folders_created += 1
                        else:
                            print(f"    ✓ Exists: {class_name}")
                else:
                    print(f"  ⚠️ {category_folder} folder not found - skipping")
            
            if case_folders_created > 0:
                print(f"  📁 Created {case_folders_created} folders for {case_folder}")
            else:
                print(f"  ✓ {case_folder} already has complete structure")
            
            cases_processed += 1
    
    print(f"\n🎉 Folder structure fix completed!")
    print(f"📊 Summary:")
    print(f"   - Cases processed: {cases_processed}")
    print(f"   - Folders created: {folders_created}")
    print(f"   - Classification categories: {classification_categories}")

def main():
    """Main function"""
    print("🚀 Starting folder structure fix...")
    
    if not os.path.exists(LABELED_DIR):
        print(f"❌ Labeled samples directory {LABELED_DIR} not found!")
        print("This directory is needed to determine the classification categories.")
        return
    
    fix_existing_folder_structure()

if __name__ == "__main__":
    main() 