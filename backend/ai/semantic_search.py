import os
import json
import numpy as np
import difflib

HAS_SENTENCE_TRANSFORMERS = False
model = None

try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    pass

def load_semantic_model():
    global model
    if not HAS_SENTENCE_TRANSFORMERS:
        return False
    if model is None:
        try:
            model = SentenceTransformer('all-MiniLM-L6-v2')
        except Exception as e:
            print(f"Failed to load SentenceTransformer: {e}")
            return False
    return True

def get_text_embedding(text):
    """
    Generates a 384-dimensional vector embedding for the input text.
    Returns list of floats or None.
    """
    if not text:
        return None
    if not load_semantic_model():
        return None
    try:
        embedding = model.encode(text)
        return embedding.tolist()
    except Exception as e:
        print(f"Error generating text embedding: {e}")
        return None

def get_semantic_similarity(text1, text2):
    """
    Computes cosine similarity between two text strings using SentenceTransformer.
    Falls back to SequenceMatcher if model is unavailable.
    """
    if not text1 or not text2:
        return 0.0
        
    emb1 = get_text_embedding(text1)
    emb2 = get_text_embedding(text2)
    
    if emb1 is not None and emb2 is not None:
        # Cosine similarity
        a = np.array(emb1)
        b = np.array(emb2)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        sim = np.dot(a, b) / (norm_a * norm_b)
        return float(max(0.0, min(1.0, sim)))
        
    # Fallback to fuzzy ratio
    return float(difflib.SequenceMatcher(None, text1.lower(), text2.lower()).ratio())
