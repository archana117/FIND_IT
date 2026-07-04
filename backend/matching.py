import os
import math
from datetime import datetime
import numpy as np

from ai.image_similarity import get_image_similarity_score
from ai.semantic_search import get_semantic_similarity
from database import get_lost_item, get_all_found_items, create_match

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculates the great-circle distance between two points on the Earth
    in kilometers using the Haversine formula.
    """
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return None
        
    try:
        lat1, lon1, lat2, lon2 = map(float, [lat1, lon1, lat2, lon2])
        r = 6371.0  # Earth's radius in kilometers
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        
        a = (math.sin(delta_phi / 2.0) ** 2 + 
             math.cos(phi1) * math.cos(phi2) * 
             math.sin(delta_lambda / 2.0) ** 2)
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return r * c
    except Exception as e:
        print(f"Error calculating distance: {e}")
        return None

def compute_overall_match(lost_item, found_item):
    """
    Computes a composite similarity score between a lost item and a found item
    using the advanced AI scoring weights:
      - Image Similarity (40%)
      - Item Name Similarity (20%)
      - Description Similarity (15%)
      - Category Match (10%)
      - Location Similarity (10%)
      - Date Similarity (5%)
    Returns a dictionary with the breakdown and overall percentage.
    """
    # 1. Category Match (10%)
    cat_match = lost_item['category'].lower().strip() == found_item['category'].lower().strip()
    cat_sim = 100.0 if cat_match else 0.0

    # 2. Item Name Similarity (20%)
    # Use semantic text similarity
    name_sim = get_semantic_similarity(lost_item['item_name'], found_item['item_name']) * 100.0

    # 3. Description Similarity (15%)
    # Include OCR results if available to enrich description comparison
    lost_desc = lost_item['description']
    if lost_item.get('ocr_text'):
        lost_desc += " " + lost_item['ocr_text']
        
    found_desc = found_item['description']
    if found_item.get('ocr_text'):
        found_desc += " " + found_item['ocr_text']
        
    desc_sim = get_semantic_similarity(lost_desc, found_desc) * 100.0

    # 4. Location Similarity (10%)
    # If both have lat/lng coordinates, use Haversine distance
    has_coords = (lost_item.get('latitude') is not None and lost_item.get('longitude') is not None and
                  found_item.get('latitude') is not None and found_item.get('longitude') is not None)
                  
    if has_coords:
        dist = haversine_distance(lost_item['latitude'], lost_item['longitude'],
                                  found_item['latitude'], found_item['longitude'])
        if dist is not None:
            # Score decay based on distance:
            # <= 100m (0.1km) -> 100%
            # <= 500m (0.5km) -> 90%
            # <= 1km -> 80%
            # <= 5km -> 60%
            # <= 10km -> 40%
            # else decays down to 0
            if dist <= 0.1:
                loc_sim = 100.0
            elif dist <= 0.5:
                loc_sim = 90.0
            elif dist <= 1.0:
                loc_sim = 80.0
            elif dist <= 5.0:
                loc_sim = 60.0
            elif dist <= 10.0:
                loc_sim = 40.0
            else:
                loc_sim = max(0.0, 40.0 - (dist - 10.0) * 2)
        else:
            # Fallback to text match if distance calc errors
            loc_sim = get_semantic_similarity(lost_item['location'], found_item['location']) * 100.0
    else:
        # Fallback to fuzzy text match on location name
        loc_sim = get_semantic_similarity(lost_item['location'], found_item['location']) * 100.0

    # 5. Date Similarity (5%)
    try:
        # Expected formats: YYYY-MM-DD or string
        d1 = datetime.strptime(str(lost_item['date_lost']), "%Y-%m-%d") if isinstance(lost_item['date_lost'], str) else lost_item['date_lost']
        d2 = datetime.strptime(str(found_item['date_found']), "%Y-%m-%d") if isinstance(found_item['date_found'], str) else found_item['date_found']
        # Convert strings to datetime if they are SQLite string returns
        if isinstance(d1, str):
            d1 = datetime.strptime(d1.split()[0], "%Y-%m-%d")
        if isinstance(d2, str):
            d2 = datetime.strptime(d2.split()[0], "%Y-%m-%d")
            
        diff_days = abs((d1 - d2).days)
        # Decay: 100% if same day, drops by 5% per day gap, minimum 0%
        date_sim = max(0.0, 100.0 - (diff_days * 5.0))
    except Exception as e:
        print(f"Error comparing dates: {e}")
        date_sim = 50.0  # Safe default

    # 6. Image Similarity (40%)
    # Check if both items have images
    has_images = bool(lost_item.get('image_path') and found_item.get('image_path'))
    img_sim = 0.0
    if has_images:
        img_sim = get_image_similarity_score(lost_item['image_path'], found_item['image_path'])

    # Weighted calculation
    if has_images:
        overall_score = (0.40 * img_sim) + (0.20 * name_sim) + (0.15 * desc_sim) + (0.10 * cat_sim) + (0.10 * loc_sim) + (0.05 * date_sim)
    else:
        # No images: Re-distribute the 40% image weight proportionally to the other fields:
        # Name Similarity: 35% (up 15%)
        # Description Similarity: 30% (up 15%)
        # Category Match: 15% (up 5%)
        # Location Similarity: 15% (up 5%)
        # Date Similarity: 5% (unchanged)
        overall_score = (0.35 * name_sim) + (0.30 * desc_sim) + (0.15 * cat_sim) + (0.15 * loc_sim) + (0.05 * date_sim)

    overall_score = max(0.0, min(100.0, overall_score))

    return {
        'overall_score': round(overall_score, 2),
        'image_score': round(img_sim, 2) if has_images else None,
        'name_score': round(name_sim, 2),
        'desc_score': round(desc_sim, 2),
        'category_score': round(cat_sim, 2),
        'location_score': round(loc_sim, 2),
        'date_score': round(date_sim, 2),
        'is_match': overall_score >= 50.0
    }

def run_matching_for_lost_item(lost_item_id):
    """
    Compares a lost item against all open found items in database.
    Saves match relationships and sends email notifications for score >= 80%.
    """
    lost_item = get_lost_item(lost_item_id)
    if not lost_item or lost_item['status'] != 'open':
        return []
        
    found_items = get_all_found_items()
    matches_created = []
    
    for found_item in found_items:
        if found_item['status'] != 'open' or found_item['is_flagged_fake'] == 1:
            continue
            
        res = compute_overall_match(lost_item, found_item)
        
        # Save matching in DB if score >= 40%
        if res['overall_score'] >= 40.0:
            create_match(lost_item['id'], found_item['id'], res['overall_score'])
            matches_created.append({
                'found_item': found_item,
                'score': res['overall_score'],
                'details': res
            })
            
            # Send Notification Emails for high confidence match (>80%)
            if res['overall_score'] >= 80.0:
                try:
                    from services.mail_service import send_match_notification
                    from flask import url_for
                    # Secure Link to contact authorization
                    secure_link = f"http://localhost:5000/matches/{lost_item['id']}"
                    send_match_notification(
                        owner_email=lost_item['email'],
                        owner_name=lost_item['owner_name'],
                        finder_email=found_item['email'],
                        finder_name=found_item['finder_name'],
                        lost_item=lost_item,
                        found_item=found_item,
                        score=res['overall_score'],
                        secure_link=secure_link
                    )
                except Exception as e:
                    print(f"Failed to dispatch match email: {e}")
                
    return matches_created
