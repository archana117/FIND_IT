import os
from PIL import Image

HAS_TORCH = False
HAS_TRANSFORMERS = False

try:
    import torch
    HAS_TORCH = True
except ImportError:
    pass

try:
    from transformers import BlipProcessor, BlipForConditionalGeneration
    HAS_TRANSFORMERS = True
except ImportError:
    pass

blip_model = None
blip_processor = None

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

def load_blip_model():
    global blip_model, blip_processor
    if not HAS_TORCH or not HAS_TRANSFORMERS:
        return False
    if blip_model is None:
        try:
            # Salesforce/blip-image-captioning-base is standard, fast, and light
            blip_processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
            blip_model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
            blip_model.eval()
        except Exception as e:
            print(f"Failed to load BLIP captioning model: {e}")
            return False
    return True

def generate_description_from_image(image_path, category=None):
    """
    Generates a description from the image. 
    Falls back to a template-based description using detected category/metadata if model is offline.
    """
    image_path = resolve_image_path(image_path)
    if not image_path or not os.path.exists(image_path):
        return ""

    if load_blip_model():
        try:
            raw_image = Image.open(image_path).convert('RGB')
            # Generate conditional description if category is provided
            text = f"a photo of a {category.lower()}" if category else "a photo of a"
            inputs = blip_processor(raw_image, text, return_tensors="pt")
            
            with torch.no_grad():
                out = blip_model.generate(**inputs, max_new_tokens=40)
            
            caption = blip_processor.decode(out[0], skip_special_tokens=True)
            # Capitalize first letter
            if caption:
                caption = caption[0].upper() + caption[1:]
                return caption
        except Exception as e:
            print(f"BLIP image caption generation failed: {e}")

    # Fallback template-based description generator
    from ai.object_detection import detect_objects_and_classify
    info = detect_objects_and_classify(image_path)
    if info and info.get("detected_item") and info["detected_item"] != "Unknown Item":
        item_name = info["detected_item"]
        cat = info["category"]
        return f"A recently reported {item_name.lower()} belonging to the {cat.lower()} category."
    
    cat_str = f"a {category.lower()} item" if category else "an item"
    return f"A photograph of {cat_str} uploaded for identification purposes."
