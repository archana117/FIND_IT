import os
import uuid
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from flask_socketio import SocketIO
from PIL import Image, ImageOps

from config import Config
from database import (
    init_db, get_dashboard_stats, get_all_lost_items, get_all_found_items, get_user_by_id
)
from utils.security import (
    generate_csrf_token, verify_csrf_token, clean_input, decode_jwt_token
)

app = Flask(
    __name__,
    template_folder=os.path.join(Config.FRONTEND_DIR, 'templates'),
    static_folder=os.path.join(Config.FRONTEND_DIR, 'static')
)
app.config.from_object(Config)

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize SocketIO for Real-Time Chat
socketio = SocketIO(app, cors_allowed_origins="*")

# Helper function to check allowed file extensions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def save_and_optimize_image(image_file, save_path, max_size=(800, 800)):
    """
    Normalizes image orientation and resizes it to fit within max_size to optimize storage and similarity calculation.
    """
    try:
        img = Image.open(image_file)
        img = ImageOps.exif_transpose(img)
        if img.mode in ('RGBA', 'P') and not save_path.lower().endswith('.png') and not save_path.lower().endswith('.webp'):
            img = img.convert('RGB')
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        img.save(save_path, optimize=True, quality=85)
        return True
    except Exception as e:
        print(f"Error optimizing image: {e}")
        try:
            image_file.seek(0)
            image_file.save(save_path)
            return True
        except Exception:
            return False

# Initialize database schema on startup
with app.app_context():
    init_db()

# --- CSRF and Session Context Hooks ---
@app.context_processor
def inject_csrf():
    return dict(csrf_token=generate_csrf_token)

@app.before_request
def security_before_request():
    # Enforce CSRF verification on all POST requests unless authenticated via JWT API key
    if request.method == "POST":
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            payload = decode_jwt_token(token)
            if payload:
                # Save user to global flask request state
                from flask import g
                g.user_id = payload['user_id']
                return # Skip standard CSRF for API requests
        verify_csrf_token()

# --- Import and Register Blueprints ---
from routes.auth import auth_bp
from routes.items import items_bp
from routes.matches import matches_bp
from routes.chat import chat_bp
from routes.admin import admin_bp
from routes.api import api_bp

app.register_blueprint(auth_bp)
app.register_blueprint(items_bp)
app.register_blueprint(matches_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(api_bp)

# --- Register SocketIO Event Handlers ---
from services.chat_service import init_socketio
init_socketio(socketio)

# --- PWA Static Endpoints ---
@app.route('/manifest.json')
def serve_manifest():
    return send_from_directory(app.static_folder, 'manifest.json')

@app.route('/sw.js')
def serve_sw():
    return send_from_directory(app.static_folder, 'sw.js')

# --- Frontend Page Handlers ---
@app.route('/')
def index():
    stats = get_dashboard_stats()
    return render_template('index.html', stats=stats)

@app.route('/search')
def search():
    q = clean_input(request.args.get('q', ''))
    category = clean_input(request.args.get('category', ''))
    location = clean_input(request.args.get('location', ''))
    status = clean_input(request.args.get('status', 'all'))
    search_type = clean_input(request.args.get('search_type', 'semantic'))
    
    # Nearby search coordinates & radius
    lat_val = request.args.get('lat')
    lng_val = request.args.get('lng')
    radius = request.args.get('radius')
    
    lat = float(lat_val) if lat_val else None
    lng = float(lng_val) if lng_val else None
    radius_km = float(radius) / 1000.0 if radius and radius.isdigit() else None
    
    items = []
    
    # Fetch base item listings
    if status == 'lost' or status == 'all':
        items.extend([dict(row) for row in get_all_lost_items(category=category, location=location if search_type == 'keyword' else None)])
        
    if status == 'found' or status == 'all':
        items.extend([dict(row) for row in get_all_found_items(category=category, location=location if search_type == 'keyword' else None)])
        
    # Apply advanced search logic
    filtered_items = []
    from ai.semantic_search import get_semantic_similarity
    from matching import haversine_distance
    
    for item in items:
        # 1. Coordinate check for Nearby Radius Search
        if lat is not None and lng is not None and radius_km is not None:
            if item.get('latitude') is not None and item.get('longitude') is not None:
                dist = haversine_distance(lat, lng, item['latitude'], item['longitude'])
                if dist is None or dist > radius_km:
                    continue
                item['distance_km'] = round(dist, 3)
            else:
                continue

        # 2. Semantic matching vs exact keyword matching
        if q:
            if search_type == 'semantic':
                item_text = f"{item['item_name']} {item['description']} {item.get('ocr_text', '')}"
                sim = get_semantic_similarity(q, item_text)
                item['search_score'] = round(sim * 100, 2)
                
                # Minimum threshold for semantic match
                if item['search_score'] < 30.0:
                    continue
            else:
                # Basic keyword filter
                query_lower = q.lower()
                if query_lower not in item['item_name'].lower() and query_lower not in item['description'].lower() and query_lower not in (item.get('ocr_text') or '').lower():
                    continue
                item['search_score'] = 100.0
        else:
            item['search_score'] = 100.0
            
        filtered_items.append(item)
        
    # Sort search results
    if q and search_type == 'semantic':
        filtered_items.sort(key=lambda x: x['search_score'], reverse=True)
    elif lat is not None and lng is not None:
        filtered_items.sort(key=lambda x: x.get('distance_km', 999999.0))
    else:
        def get_item_date(item):
            return item.get('date_lost') or item.get('date_found') or ''
        filtered_items.sort(key=get_item_date, reverse=True)
    
    filters = {
        'q': q, 
        'category': category, 
        'location': location, 
        'status': status, 
        'search_type': search_type,
        'lat': lat_val,
        'lng': lng_val,
        'radius': radius
    }
    return render_template('search.html', items=filtered_items, filters=filters)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
