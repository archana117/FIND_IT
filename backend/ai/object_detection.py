import os
from PIL import Image

HAS_ULTRALYTICS = False
HAS_TORCH = False
HAS_TRANSFORMERS = False

try:
    from ultralytics import YOLO
    HAS_ULTRALYTICS = True
except ImportError:
    pass

try:
    import torch
    HAS_TORCH = True
except ImportError:
    pass

try:
    from transformers import CLIPProcessor, CLIPModel
    HAS_TRANSFORMERS = True
except ImportError:
    pass

# Target items list
TARGET_LABELS = [
    "Mobile Phone", "Wallet", "Keys", "Laptop", "ID Card",
    "Earbuds", "Watch", "Bag", "Bottle", "Passport", "Purse"
]

# Mapping to standard categories
CATEGORY_MAPPING = {
    "Mobile Phone": "Mobile",
    "Wallet": "Wallet",
    "Keys": "Keys",
    "Laptop": "Electronics",
    "ID Card": "ID Card",
    "Earbuds": "Electronics",
    "Watch": "Electronics",
    "Bag": "Bag",
    "Bottle": "Others",
    "Passport": "ID Card",
    "Purse": "Bag"
}

yolo_model = None
clip_model = None
clip_processor = None

def resolve_image_path(image_path):
    if not image_path:
        return image_path
    if image_path.startswith('http'):
        return image_path
    if os.path.exists(image_path):
        return image_path
    
    # Try resolving relative to FRONTEND_DIR or BASE_DIR
    try:
        from config import Config
        resolved_path = os.path.join(Config.FRONTEND_DIR, image_path)
        if os.path.exists(resolved_path):
            return resolved_path
        resolved_path = os.path.join(Config.BASE_DIR, image_path)
        if os.path.exists(resolved_path):
            return resolved_path
    except Exception:
        pass
        
    return image_path

def load_models():
    global yolo_model, clip_model, clip_processor
    # Load YOLO
    if HAS_ULTRALYTICS and yolo_model is None:
        try:
            # Load lightweight nano model
            yolo_model = YOLO("yolov8n.pt")
        except Exception as e:
            print(f"YOLO loading failed: {e}")
            
    # Load CLIP for zero-shot classification
    if HAS_TORCH and HAS_TRANSFORMERS and clip_model is None:
        try:
            clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
            clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
            clip_model.eval()
        except Exception as e:
            print(f"CLIP loading failed: {e}")

def detect_objects_and_classify(image_path):
    """
    Analyzes the image at image_path using YOLO and zero-shot CLIP classification.
    Returns a dict with 'detected_item', 'category', and 'confidence'.
    """
    image_path = resolve_image_path(image_path)
    if not image_path or not os.path.exists(image_path):
        return None

    load_models()

    detected_name = None
    category = "Others"
    confidence = 0.0

    # 1. Zero-shot CLIP classification (Best for the specific list of 11 items)
    if clip_model is not None and clip_processor is not None:
        try:
            image = Image.open(image_path).convert("RGB")
            # Create text prompts
            prompts = [f"a photo of a {label.lower()}" for label in TARGET_LABELS]
            
            inputs = clip_processor(text=prompts, images=image, return_tensors="pt", padding=True)
            with torch.no_grad():
                outputs = clip_model(**inputs)
                # Image-text similarity scores
                logits_per_image = outputs.logits_per_image
                probs = logits_per_image.softmax(dim=-1).cpu().numpy()[0]
                
            max_idx = probs.argmax()
            confidence = float(probs[max_idx])
            
            # Threshold to ensure it's not complete noise
            if confidence > 0.15:
                detected_name = TARGET_LABELS[max_idx]
                category = CATEGORY_MAPPING.get(detected_name, "Others")
        except Exception as e:
            print(f"Zero-shot CLIP classification failed: {e}")

    # 2. YOLO fallback/verification for standard classes (like cell phone, laptop, bottle, backpack)
    if yolo_model is not None and (detected_name is None or confidence < 0.3):
        try:
            results = yolo_model(image_path, verbose=False)
            if results and len(results[0].boxes) > 0:
                # Find the box with highest confidence
                best_box = None
                best_conf = 0.0
                for box in results[0].boxes:
                    conf = float(box.conf[0])
                    if conf > best_conf:
                        best_conf = conf
                        best_box = box
                
                if best_box is not None and best_conf > 0.4:
                    cls_id = int(best_box.cls[0])
                    label = yolo_model.names[cls_id]
                    
                    # Map to target items
                    yolo_mapping = {
                        "cell phone": ("Mobile Phone", "Mobile"),
                        "laptop": ("Laptop", "Electronics"),
                        "bottle": ("Bottle", "Others"),
                        "backpack": ("Bag", "Bag"),
                        "handbag": ("Purse", "Bag"),
                        "suitcase": ("Bag", "Bag"),
                        "clock": ("Watch", "Electronics")
                    }
                    
                    if label in yolo_mapping:
                        detected_name, category = yolo_mapping[label]
                        confidence = best_conf
        except Exception as e:
            print(f"YOLO object detection failed: {e}")

    if detected_name:
        return {
            "detected_item": detected_name,
            "category": category,
            "confidence": round(confidence * 100, 2)
        }
        
    return {
        "detected_item": "Unknown Item",
        "category": "Others",
        "confidence": 0.0
    }
