#!/usr/bin/env python3

import os
import json
import requests
import numpy as np
import shutil
import math
from PIL import Image, ImageOps, ImageEnhance
import clip
import torch
from sklearn.linear_model import LogisticRegression
from tqdm import tqdm
import tempfile
from urllib.parse import urlparse
import re


INPUT_JSON_DIR = "inputJsons"
OUTPUT_BASE_DIR = "output"
LABELED_DIR = "labeled_samples"
AUGMENTATIONS = ["original", "flip", "rotate+10", "rotate-10", "bright", "contrast"]
TOP_K = 3

print("🔄 Loading CLIP model...")
device = "cuda" if torch.cuda.is_available() else "cpu"
model, preprocess = clip.load("ViT-B/32", device=device)
print(f"✅ CLIP model loaded on {device}")

def download_google_drive_file(file_id, output_path):
    try:
        urls_to_try = [
            f"https://drive.google.com/uc?export=download&id={file_id}",
            f"https://drive.google.com/uc?id={file_id}&export=download", 
            f"https://drive.google.com/uc?id={file_id}"
        ]
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        session = requests.Session()
        
        for url in urls_to_try:
            try:
                response = session.get(url, headers=headers, timeout=30)
                
                if 'Google Drive - Virus scan warning' in response.text or 'download_warning' in response.text:
                    import re
                    confirm_match = re.search(r'/uc\?export=download&amp;confirm=([^&]+)&amp;id=' + file_id, response.text)
                    if confirm_match:
                        confirm_token = confirm_match.group(1)
                        confirm_url = f"https://drive.google.com/uc?export=download&confirm={confirm_token}&id={file_id}"
                        response = session.get(confirm_url, headers=headers, timeout=30)
                
                content_type = response.headers.get('content-type', '').lower()
                if 'text/html' in content_type and len(response.content) < 100000:
                    continue
                
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, 'wb') as f:
                    f.write(response.content)
                
                try:
                    with Image.open(output_path) as img:
                        img.verify()
                    return True
                except:
                    if os.path.exists(output_path):
                        os.remove(output_path)
                    continue
                    
            except Exception as e:
                continue
        
        return False
        
    except Exception as e:
        print(f"❌ Google Drive download failed: {e}")
        return False

def download_image(url, output_path):
    try:
        if 'drive.google.com' in url and 'id=' in url:
            file_id = url.split('id=')[1].split('&')[0]
            return download_google_drive_file(file_id, output_path)
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, stream=True, timeout=30)
        response.raise_for_status()
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        try:
            with Image.open(output_path) as img:
                img.verify()
            return True
        except Exception as verify_error:
            print(f"⚠️ Downloaded file is not a valid image: {verify_error}")
            if os.path.exists(output_path):
                os.remove(output_path)
            return False
        
    except Exception as e:
        print(f"❌ Failed to download {url}: {e}")
        return False

def crop_and_rotate_image(image_path, crop_properties, rotation_degrees=0):
    try:
        image = Image.open(image_path).convert("RGB")
        original_width, original_height = image.size
        
        left_offset = crop_properties.get('leftOffset', 0)
        right_offset = crop_properties.get('rightOffset', 0)
        top_offset = crop_properties.get('topOffset', 0)
        bottom_offset = crop_properties.get('bottomOffset', 0)
        
        left = int(left_offset * original_width)
        right = int(original_width - (right_offset * original_width))
        top = int(top_offset * original_height)
        bottom = int(original_height - (bottom_offset * original_height))
        
        left = max(0, min(left, original_width))
        right = max(left, min(right, original_width))
        top = max(0, min(top, original_height))
        bottom = max(top, min(bottom, original_height))
        
        image = image.crop((left, top, right, bottom))
        
        if abs(rotation_degrees) > 0.001:
            image = image.rotate(-rotation_degrees, expand=True)
        
        return image
        
    except Exception as e:
        print(f"❌ Error processing image {image_path}: {e}")
        return None

def augment_image(image, mode):
    if mode == "flip":
        return ImageOps.mirror(image)
    elif mode == "rotate+10":
        return image.rotate(10, expand=True)
    elif mode == "rotate-10":
        return image.rotate(-10, expand=True)
    elif mode == "bright":
        return ImageEnhance.Brightness(image).enhance(1.2)
    elif mode == "contrast":
        return ImageEnhance.Contrast(image).enhance(1.2)
    return image

def get_image_embedding(image):
    image_input = preprocess(image).unsqueeze(0).to(device)
    with torch.no_grad():
        embedding = model.encode_image(image_input)
        embedding /= embedding.norm(dim=-1, keepdim=True)
    return embedding.cpu().numpy().flatten()

def load_training_data_from_output():
    print("🔍 Loading training data from output folder...")
    embeddings = []
    labels = []
    total_images = 0
    
    categories_with_classification = ['preTreatment', 'postTreatment']
    classification_categories = set()
    
    if not os.path.exists(OUTPUT_BASE_DIR):
        print(f"❌ Output directory {OUTPUT_BASE_DIR} not found!")
        return None, None
    
    for case_folder in os.listdir(OUTPUT_BASE_DIR):
        case_path = os.path.join(OUTPUT_BASE_DIR, case_folder)
        if os.path.isdir(case_path):
            for category_folder in categories_with_classification:
                category_path = os.path.join(case_path, category_folder)
                if os.path.exists(category_path):
                    for class_name in os.listdir(category_path):
                        class_path = os.path.join(category_path, class_name)
                        if os.path.isdir(class_path):
                            classification_categories.add(class_name)
    
    classification_categories = sorted(list(classification_categories))
    print(f"📁 Found classification categories: {classification_categories}")
    
    for case_folder in tqdm(os.listdir(OUTPUT_BASE_DIR), desc="Loading training data"):
        case_path = os.path.join(OUTPUT_BASE_DIR, case_folder)
        if os.path.isdir(case_path):
            for category_folder in categories_with_classification:
                category_path = os.path.join(case_path, category_folder)
                if os.path.exists(category_path):
                    for class_name in classification_categories:
                        class_path = os.path.join(category_path, class_name)
                        if os.path.exists(class_path):
                            for fname in os.listdir(class_path):
                                if fname.lower().endswith((".png", ".jpg", ".jpeg")):
                                    image_path = os.path.join(class_path, fname)
                                    try:
                                        image = Image.open(image_path).convert("RGB")
                                        for aug in AUGMENTATIONS:
                                            aug_img = augment_image(image, aug)
                                            emb = get_image_embedding(aug_img)
                                            embeddings.append(emb)
                                            labels.append(class_name)
                                            total_images += 1
                                    except Exception as e:
                                        print(f"❌ Failed to process {image_path}: {e}")
    
    if not embeddings:
        print("⚠️ No training data found in output folder. Falling back to labeled_samples...")
        return load_labeled_data_fallback()
    
    print(f"✅ Loaded {total_images} training samples from {len(classification_categories)} classes")
    print(f"📊 Training data distribution:")
    for class_name in classification_categories:
        count = labels.count(class_name)
        print(f"   - {class_name}: {count} samples")
    
    return np.array(embeddings), labels

def load_labeled_data_fallback():
    print("🔍 Loading labeled training data from labeled_samples (fallback)...")
    embeddings = []
    labels = []
    
    if not os.path.exists(LABELED_DIR):
        print(f"❌ Neither output folder nor {LABELED_DIR} found for training!")
        return None, None
    
    for class_name in os.listdir(LABELED_DIR):
        class_path = os.path.join(LABELED_DIR, class_name)
        if os.path.isdir(class_path):
            print(f"📁 Loading class: {class_name}")
            for fname in os.listdir(class_path):
                if fname.lower().endswith((".png", ".jpg", ".jpeg")):
                    path = os.path.join(class_path, fname)
                    try:
                        image = Image.open(path).convert("RGB")
                        for aug in AUGMENTATIONS:
                            aug_img = augment_image(image, aug)
                            emb = get_image_embedding(aug_img)
                            embeddings.append(emb)
                            labels.append(class_name)
                    except Exception as e:
                        print(f"❌ Failed to process {path}: {e}")
    
    print(f"✅ Loaded {len(embeddings)} training samples from {len(set(labels))} classes")
    return np.array(embeddings), labels

def get_classification_categories():
    categories = []
    
    if os.path.exists(OUTPUT_BASE_DIR):
        categories_with_classification = ['preTreatment', 'postTreatment']
        for case_folder in os.listdir(OUTPUT_BASE_DIR):
            case_path = os.path.join(OUTPUT_BASE_DIR, case_folder)
            if os.path.isdir(case_path):
                for category_folder in categories_with_classification:
                    category_path = os.path.join(case_path, category_folder)
                    if os.path.exists(category_path):
                        for item in os.listdir(category_path):
                            item_path = os.path.join(category_path, item)
                            if os.path.isdir(item_path):
                                categories.append(item)
                break
    
    if not categories and os.path.exists(LABELED_DIR):
        for item in os.listdir(LABELED_DIR):
            item_path = os.path.join(LABELED_DIR, item)
            if os.path.isdir(item_path):
                categories.append(item)
    
    return sorted(list(set(categories)))

def create_classification_folders(case_output_dir, category_folder):
    classification_categories = get_classification_categories()
    
    for class_name in classification_categories:
        folder_path = os.path.join(case_output_dir, category_folder, class_name)
        os.makedirs(folder_path, exist_ok=True)
    
    print(f"📁 Created classification folders: {classification_categories}")

def train_classifier():
    print("🧠 Training improved classifier from output folder...")
    X_train, y_train = load_training_data_from_output()
    
    if X_train is None or y_train is None:
        print("❌ Failed to load training data!")
        return None
    
    classifier = LogisticRegression(max_iter=1000, random_state=42)
    classifier.fit(X_train, y_train)
    
    print(f"✅ Improved classifier trained with classes: {list(classifier.classes_)}")
    return classifier

def classify_image(classifier, image):
    try:
        emb = get_image_embedding(image).reshape(1, -1)
        probs = classifier.predict_proba(emb)[0]
        top_indices = np.argsort(probs)[::-1][:TOP_K]
        top_preds = [(classifier.classes_[i], round(float(probs[i]), 3)) for i in top_indices]
        return top_preds[0][0]
    except Exception as e:
        print(f"❌ Classification failed: {e}")
        return "Unknown"

def process_images_from_slide(slide, case_name, classifier, should_classify=True):
    category = slide.get('assumedCategory', 'UNKNOWN')
    images = slide.get('images', [])
    
    category_mapping = {
        'PRE_TREATMENT': 'preTreatment',
        'POST_TREATMENT': 'postTreatment', 
        'PRE_TREATMENT_RADIOGRAPH': 'pre_treatment_radiograph',
        'SMILE_SUMMARY': 'smile_summary'
    }
    
    category_folder = category_mapping.get(category)
    if not category_folder:
        return
    
    print(f"📷 Processing {len(images)} images from {category} category")
    
    case_output_dir = os.path.join(OUTPUT_BASE_DIR, case_name)
    
    if should_classify:
        create_classification_folders(case_output_dir, category_folder)
    else:
        os.makedirs(os.path.join(case_output_dir, category_folder), exist_ok=True)
    
    for i, image_info in enumerate(images):
        if image_info.get('assumedCategory') == 'ZENYUM_LOGO' or 'downloadUrl' not in image_info:
            continue
            
        download_url = image_info['downloadUrl']
        file_name = image_info.get('fileName', f"{case_name}_{category}_img_{i+1}.jpg")
        
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            if download_image(download_url, temp_path):
                crop_properties = image_info.get('crop', {})
                rotation_angle = image_info.get('rotation', 0)
                
                processed_image = crop_and_rotate_image(temp_path, crop_properties, rotation_angle)
                
                if processed_image is not None:
                    if should_classify and classifier is not None:
                        predicted_class = classify_image(classifier, processed_image)
                        final_output_dir = os.path.join(case_output_dir, category_folder, predicted_class)
                    else:
                        final_output_dir = os.path.join(case_output_dir, category_folder)
                    
                    os.makedirs(final_output_dir, exist_ok=True)
                    output_path = os.path.join(final_output_dir, file_name)
                    processed_image.save(output_path, 'JPEG', quality=95)
                    print(f"✅ Saved: {output_path}")
                    
        except Exception as e:
            print(f"❌ Failed to process image {file_name}: {e}")
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

def process_json_file(json_path, classifier):
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        case_name = data.get('name', 'unknown_case')
        slides = data.get('slides', [])
        
        print(f"\n🔄 Processing case: {case_name}")
        print(f"📋 Found {len(slides)} slides")
        
        for slide in slides:
            category = slide.get('assumedCategory', 'UNKNOWN')
            
            if category == 'PRE_TREATMENT':
                process_images_from_slide(slide, case_name, classifier, should_classify=True)
            elif category == 'POST_TREATMENT':
                process_images_from_slide(slide, case_name, classifier, should_classify=True)
            elif category in ['PRE_TREATMENT_RADIOGRAPH', 'SMILE_SUMMARY']:
                process_images_from_slide(slide, case_name, classifier, should_classify=False)
        
        print(f"✅ Completed processing case: {case_name}")
        
    except Exception as e:
        print(f"❌ Failed to process {json_path}: {e}")

def main():
    print("🚀 Starting improved JSON image processing...")
    print("📈 Using existing output folder for enhanced training data!")
    
    if not os.path.exists(INPUT_JSON_DIR):
        print(f"❌ Input directory {INPUT_JSON_DIR} not found!")
        return
    
    json_files = [f for f in os.listdir(INPUT_JSON_DIR) if f.endswith('.json')]
    
    if not json_files:
        print(f"❌ No JSON files found in {INPUT_JSON_DIR}")
        return
    
    print(f"📁 Found {len(json_files)} JSON files to process")
    
    classifier = train_classifier()
    
    if classifier is None:
        print("❌ Failed to train classifier!")
        return
    
    os.makedirs(OUTPUT_BASE_DIR, exist_ok=True)
    
    for json_file in tqdm(json_files, desc="Processing JSON files"):
        json_path = os.path.join(INPUT_JSON_DIR, json_file)
        process_json_file(json_path, classifier)
    
    print("\n🎉 All JSON files processed with improved classification!")
    print(f"📂 Results saved in: {OUTPUT_BASE_DIR}")

if __name__ == "__main__":
    main() 