import os
import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from werkzeug.utils import secure_filename

from database import (
    create_lost_item, create_found_item, get_all_lost_items, get_all_found_items, get_user_by_id
)
from utils.security import login_required, verify_csrf_token, clean_input
from services.cloudinary_service import upload_image
from services.fraud_detector import is_duplicate_listing
from ai.ocr_processor import extract_text_from_image
from ai.image_similarity import get_image_embedding
from ai.semantic_search import get_text_embedding
from matching import run_matching_for_lost_item

items_bp = Blueprint('items', __name__)

# Allowed file check helper
def allowed_file(filename):
    from config import Config
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS

@items_bp.route('/report-lost', methods=['GET', 'POST'])
@login_required
def report_lost():
    user = get_user_by_id(session['user_id'])
    
    if request.method == 'POST':
        verify_csrf_token()
        owner_name = clean_input(request.form.get('owner_name', ''))
        contact_number = clean_input(request.form.get('contact_number', ''))
        email = clean_input(request.form.get('email', ''))
        item_name = clean_input(request.form.get('item_name', ''))
        category = clean_input(request.form.get('category', ''))
        description = clean_input(request.form.get('description', ''))
        location = clean_input(request.form.get('location', ''))
        date_lost = clean_input(request.form.get('date_lost', ''))
        additional_notes = clean_input(request.form.get('additional_notes', ''))
        
        # Geolocation parameters
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        latitude = float(latitude) if latitude else None
        longitude = float(longitude) if longitude else None

        if not owner_name or not contact_number or not email or not item_name or not category or not description or not location or not date_lost:
            flash('Please fill in all required fields.', 'error')
            return render_template('report_lost.html', user=user)

        # 1. Spam/Duplicate Listing Check
        if is_duplicate_listing(session['user_id'], item_name, category, description, item_type='lost'):
            flash('Duplicate listing warning: You have already submitted a very similar report in the last 24 hours.', 'error')
            return render_template('report_lost.html', user=user)

        # 2. Image Processing
        image_file = request.files.get('image')
        image_path = None
        ocr_text = None
        image_embedding = None

        if image_file and image_file.filename != '':
            if allowed_file(image_file.filename):
                image_path = upload_image(image_file, prefix="lost")
                if image_path:
                    # Run OCR
                    full_image_path = image_path
                    if not image_path.startswith('http'):
                        # If saved locally, get absolute path
                        from config import Config
                        full_image_path = os.path.join(Config.FRONTEND_DIR, image_path)
                    
                    # Extract OCR text
                    ocr_text = extract_text_from_image(full_image_path)
                    # Extract Vision embeddings
                    image_embedding = get_image_embedding(full_image_path)
                else:
                    flash('Error processing uploaded image.', 'error')
                    return render_template('report_lost.html', user=user)
            else:
                flash('Unsupported image format. Allowed formats: PNG, JPG, JPEG, WEBP.', 'error')
                return render_template('report_lost.html', user=user)

        # Generate text description embedding for semantic search
        desc_embedding = get_text_embedding(f"{item_name} {description} {ocr_text or ''}")

        lost_id = create_lost_item(
            session['user_id'], owner_name, contact_number, email, item_name, 
            category, description, image_path, location, date_lost, additional_notes,
            latitude=latitude, longitude=longitude, ocr_text=ocr_text,
            image_embedding=image_embedding, desc_embedding=desc_embedding
        )
        
        if lost_id:
            # Trigger Smart Matching algorithm immediately
            run_matching_for_lost_item(lost_id)
            flash('Lost item reported successfully! Match analysis is ready.', 'success')
            return redirect(url_for('matches.match_results', lost_id=lost_id))
        else:
            flash('Failed to submit report. Please verify inputs.', 'error')
            
    return render_template('report_lost.html', user=user)

@items_bp.route('/report-found', methods=['GET', 'POST'])
@login_required
def report_found():
    user = get_user_by_id(session['user_id'])
    
    if request.method == 'POST':
        verify_csrf_token()
        finder_name = clean_input(request.form.get('finder_name', ''))
        contact_number = clean_input(request.form.get('contact_number', ''))
        email = clean_input(request.form.get('email', ''))
        item_name = clean_input(request.form.get('item_name', ''))
        category = clean_input(request.form.get('category', ''))
        description = clean_input(request.form.get('description', ''))
        location = clean_input(request.form.get('location', ''))
        date_found = clean_input(request.form.get('date_found', ''))
        additional_notes = clean_input(request.form.get('additional_notes', ''))
        
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        latitude = float(latitude) if latitude else None
        longitude = float(longitude) if longitude else None

        # Found items require an image for claim validation
        image_file = request.files.get('image')
        if not image_file or image_file.filename == '':
            flash('An image file is required when reporting a found item.', 'error')
            return render_template('report_found.html', user=user)
            
        if not finder_name or not contact_number or not email or not item_name or not category or not description or not location or not date_found:
            flash('Please fill in all required fields.', 'error')
            return render_template('report_found.html', user=user)

        # 1. Spam/Duplicate Listing Check
        if is_duplicate_listing(session['user_id'], item_name, category, description, item_type='found'):
            flash('Duplicate listing warning: You have already submitted a very similar report in the last 24 hours.', 'error')
            return render_template('report_found.html', user=user)

        image_path = None
        ocr_text = None
        image_embedding = None

        if allowed_file(image_file.filename):
            image_path = upload_image(image_file, prefix="found")
            if image_path:
                full_image_path = image_path
                if not image_path.startswith('http'):
                    from config import Config
                    full_image_path = os.path.join(Config.FRONTEND_DIR, image_path)
                
                # Extract OCR and Embeddings
                ocr_text = extract_text_from_image(full_image_path)
                image_embedding = get_image_embedding(full_image_path)
            else:
                flash('Error processing uploaded image.', 'error')
                return render_template('report_found.html', user=user)
        else:
            flash('Unsupported image format.', 'error')
            return render_template('report_found.html', user=user)
            
        desc_embedding = get_text_embedding(f"{item_name} {description} {ocr_text or ''}")

        found_id = create_found_item(
            session['user_id'], finder_name, contact_number, email, item_name,
            category, description, image_path, location, date_found, additional_notes,
            latitude=latitude, longitude=longitude, ocr_text=ocr_text,
            image_embedding=image_embedding, desc_embedding=desc_embedding
        )
        
        if found_id:
            # Re-run matches for any open lost items in the database
            lost_items = get_all_lost_items()
            for lost_item in lost_items:
                if lost_item['status'] == 'open':
                    run_matching_for_lost_item(lost_item['id'])
                    
            flash('Found item reported successfully! Match analysis is ready.', 'success')
            return redirect(url_for('search'))
        else:
            flash('Failed to submit found report.', 'error')
            
    return render_template('report_found.html', user=user)
