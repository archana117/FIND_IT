import os
from flask import Blueprint, request, jsonify, session
from werkzeug.utils import secure_filename
from config import Config

from utils.security import login_required, clean_input
from ai.object_detection import detect_objects_and_classify
from ai.ocr_processor import extract_text_from_image, parse_ocr_details
from ai.desc_generator import generate_description_from_image
from ai.semantic_search import get_text_embedding, get_semantic_similarity
from services.fraud_detector import report_item
from database import get_all_lost_items, get_all_found_items, get_db_connection
from matching import haversine_distance

api_bp = Blueprint('api', __name__)

@api_bp.route('/api/analyze-image', methods=['POST'])
@login_required
def analyze_image():
    """
    Accepts an uploaded image, runs YOLO/CLIP classification and EasyOCR,
    and returns auto-fill data.
    """
    image_file = request.files.get('image')
    if not image_file or image_file.filename == '':
        return jsonify({"status": "error", "message": "No image file provided."}), 400

    # Save to temp file
    temp_dir = os.path.join(Config.FRONTEND_DIR, 'static', 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    temp_filename = f"temp_{secure_filename(image_file.filename)}"
    temp_path = os.path.join(temp_dir, temp_filename)
    
    try:
        image_file.save(temp_path)
        
        # 1. Object Detection / Category Classification
        detection_result = detect_objects_and_classify(temp_path)
        
        # 2. OCR Text Extraction and Parsing
        raw_text = extract_text_from_image(temp_path)
        ocr_details = parse_ocr_details(raw_text)
        
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)
            
        return jsonify({
            "status": "success",
            "detected_item": detection_result["detected_item"],
            "category": detection_result["category"],
            "confidence": detection_result["confidence"],
            "ocr_text": raw_text,
            "ocr_details": ocr_details
        })
    except Exception as e:
        print(f"Error in image analysis API: {e}")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return jsonify({"status": "error", "message": "Image analysis failed."}), 500

@api_bp.route('/api/generate-description', methods=['POST'])
@login_required
def generate_description():
    """
    Generates a description from a temporarily uploaded image file.
    """
    image_file = request.files.get('image')
    category = request.form.get('category')
    
    if not image_file or image_file.filename == '':
        return jsonify({"status": "error", "message": "No image file provided."}), 400

    temp_dir = os.path.join(Config.FRONTEND_DIR, 'static', 'temp')
    os.makedirs(temp_dir, exist_ok=True)
    temp_filename = f"temp_desc_{secure_filename(image_file.filename)}"
    temp_path = os.path.join(temp_dir, temp_filename)
    
    try:
        image_file.save(temp_path)
        description = generate_description_from_image(temp_path, category=category)
        
        if os.path.exists(temp_path):
            os.remove(temp_path)
            
        return jsonify({
            "status": "success",
            "description": description
        })
    except Exception as e:
        print(f"Error generating description: {e}")
        if os.path.exists(temp_path):
            os.remove(temp_path)
        return jsonify({"status": "error", "message": "Description generation failed."}), 500

@api_bp.route('/api/report-fake/<string:item_type>/<int:item_id>', methods=['POST'])
@login_required
def report_fake_item(item_type, item_id):
    if report_item(item_type, item_id):
        return jsonify({"status": "success", "message": "Listing has been reported for review."})
    return jsonify({"status": "error", "message": "Failed to report listing."}), 400

@api_bp.route('/api/semantic-search', methods=['GET'])
def semantic_search_api():
    """
    Endpoint for advanced semantic text vector search and nearby location coordinate queries.
    """
    q = request.args.get('q', '').strip()
    category = request.args.get('category', '').strip()
    status = request.args.get('status', 'all').strip()
    
    # Location coordinates & search radius (meters)
    lat_val = request.args.get('lat')
    lng_val = request.args.get('lng')
    radius = request.args.get('radius') # 100, 500, 1000 (1km), 5000 (5km)
    
    lat = float(lat_val) if lat_val else None
    lng = float(lng_val) if lng_val else None
    radius_km = float(radius) / 1000.0 if radius and radius.isdigit() else None

    # Load all items from SQLite
    items = []
    if status == 'lost' or status == 'all':
        items.extend([dict(i) for i in get_all_lost_items(category=category)])
    if status == 'found' or status == 'all':
        items.extend([dict(i) for i in get_all_found_items(category=category)])

    results = []
    
    for item in items:
        # 1. Nearby Search filtering by geo-coordinates if enabled
        if lat is not None and lng is not None and radius_km is not None:
            if item.get('latitude') is not None and item.get('longitude') is not None:
                dist = haversine_distance(lat, lng, item['latitude'], item['longitude'])
                if dist is None or dist > radius_km:
                    continue  # Filter out items outside the radius
                item['distance_km'] = round(dist, 3)
            else:
                continue  # Skip items that do not have coordinates set
                
        # 2. Semantic query matching score
        if q:
            # Match query against item name, description and OCR details
            item_text = f"{item['item_name']} {item['description']} {item.get('ocr_text', '')}"
            semantic_score = get_semantic_similarity(q, item_text)
            item['search_score'] = round(semantic_score * 100, 2)
            
            # Gating threshold for query results
            if item['search_score'] < 30.0:
                continue
        else:
            item['search_score'] = 100.0  # Default score if no query text
            
        results.append(item)

    # Sort results
    if q:
        # Sort primarily by semantic match score
        results.sort(key=lambda x: x['search_score'], reverse=True)
    elif lat is not None and lng is not None:
        # Sort primarily by closest physical distance
        results.sort(key=lambda x: x.get('distance_km', 999999.0))
    else:
        # Sort by creation date
        def get_date(x):
            return x.get('date_lost') or x.get('date_found') or ''
        results.sort(key=get_date, reverse=True)

    return jsonify({
        "status": "success",
        "count": len(results),
        "results": results
    })
