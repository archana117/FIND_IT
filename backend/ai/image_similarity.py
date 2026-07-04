import os
import json
import numpy as np
from PIL import Image

HAS_TORCH = False
HAS_TRANSFORMERS = False

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

def load_clip_model():
    global clip_model, clip_processor
    if not HAS_TORCH or not HAS_TRANSFORMERS:
        return False
    if clip_model is None:
        try:
            # Using openai/clip-vit-base-patch32, which is lightweight and standard
            clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
            clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
            clip_model.eval()
        except Exception as e:
            print(f"Warning: Failed to load CLIP model: {e}. Fallbacks will be used.")
            return False
    return True

def get_image_embedding(image_path):
    """
    Extracts a normalized image embedding using CLIP (ViT).
    Returns a list of floats (embedding) or None if model load fails.
    """
    image_path = resolve_image_path(image_path)
    if not image_path or not os.path.exists(image_path):
        return None
    if not load_clip_model():
        return None
    try:
        image = Image.open(image_path).convert("RGB")
        inputs = clip_processor(images=image, return_tensors="pt")
        with torch.no_grad():
            image_features = clip_model.get_image_features(**inputs)
            # Normalize the embedding
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            embedding = image_features.cpu().numpy()[0].tolist()
            return embedding
    except Exception as e:
        print(f"Error extracting image embedding: {e}")
        return None

def calculate_cosine_similarity(emb1, emb2):
    """
    Computes cosine similarity between two vector embeddings.
    """
    if not emb1 or not emb2:
        return 0.0
    arr1 = np.array(emb1)
    arr2 = np.array(emb2)
    norm1 = np.linalg.norm(arr1)
    norm2 = np.linalg.norm(arr2)
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return float(np.dot(arr1, arr2) / (norm1 * norm2))

def get_image_similarity_score(image_path1, image_path2):
    """
    Returns image similarity score as a percentage (0.0 to 100.0).
    First tries CLIP embeddings, falls back to HSV color histograms if unavailable.
    """
    emb1 = get_image_embedding(image_path1)
    emb2 = get_image_embedding(image_path2)

    if emb1 is not None and emb2 is not None:
        sim = calculate_cosine_similarity(emb1, emb2)
        # Cosine similarity normally ranges from -1 to 1; scale similarity score
        # so that it fits nicely on a 0-100% scale
        scaled_sim = max(0.0, min(100.0, sim * 100.0))
        return round(scaled_sim, 2)
    
    # Fallback to the original histogram-based comparison
    return round(fallback_histogram_similarity(image_path1, image_path2) * 100.0, 2)

def fallback_histogram_similarity(img_path1, img_path2):
    """
    Original color-histogram based image similarity.
    """
    img_path1 = resolve_image_path(img_path1)
    img_path2 = resolve_image_path(img_path2)
    if not img_path1 or not img_path2 or not os.path.exists(img_path1) or not os.path.exists(img_path2):
        return 0.0
    try:
        img1 = Image.open(img_path1).convert('RGB').resize((128, 128))
        img2 = Image.open(img_path2).convert('RGB').resize((128, 128))
        
        arr1 = np.array(img1)
        arr2 = np.array(img2)
        
        hist1_r, _ = np.histogram(arr1[:,:,0], bins=32, range=(0, 256), density=True)
        hist1_g, _ = np.histogram(arr1[:,:,1], bins=32, range=(0, 256), density=True)
        hist1_b, _ = np.histogram(arr1[:,:,2], bins=32, range=(0, 256), density=True)
        
        hist2_r, _ = np.histogram(arr2[:,:,0], bins=32, range=(0, 256), density=True)
        hist2_g, _ = np.histogram(arr2[:,:,1], bins=32, range=(0, 256), density=True)
        hist2_b, _ = np.histogram(arr2[:,:,2], bins=32, range=(0, 256), density=True)
        
        intersection_r = np.minimum(hist1_r, hist2_r).sum() / np.maximum(hist1_r, hist2_r).sum()
        intersection_g = np.minimum(hist1_g, hist2_g).sum() / np.maximum(hist1_g, hist2_g).sum()
        intersection_b = np.minimum(hist1_b, hist2_b).sum() / np.maximum(hist1_b, hist2_b).sum()
        
        color_sim = (intersection_r + intersection_g + intersection_b) / 3.0
        
        gray1 = np.array(img1.convert('L'))
        gray2 = np.array(img2.convert('L'))
        g1 = gray1.flatten() / 255.0
        g2 = gray2.flatten() / 255.0
        
        norm1 = np.linalg.norm(g1)
        norm2 = np.linalg.norm(g2)
        structural_sim = np.dot(g1, g2) / (norm1 * norm2) if norm1 > 0 and norm2 > 0 else 0.0
            
        return float(max(0.0, min(1.0, (0.7 * color_sim) + (0.3 * structural_sim))))
    except Exception as e:
        print(f"Error in fallback histogram calculation: {e}")
        return 0.0
