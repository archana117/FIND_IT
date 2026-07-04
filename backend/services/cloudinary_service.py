import os
import uuid
from werkzeug.utils import secure_filename
from config import Config

HAS_CLOUDINARY = False
try:
    import cloudinary
    import cloudinary.uploader
    HAS_CLOUDINARY = True
except ImportError:
    pass

# Check configuration
cloudinary_configured = False
if HAS_CLOUDINARY:
    # If CLOUDINARY_URL environment variable is set, Cloudinary SDK automatically picks it up
    if os.environ.get('CLOUDINARY_URL'):
        cloudinary_configured = True
    elif hasattr(Config, 'CLOUDINARY_CLOUD_NAME') and Config.CLOUDINARY_CLOUD_NAME:
        try:
            cloudinary.config(
                cloud_name=Config.CLOUDINARY_CLOUD_NAME,
                api_key=Config.CLOUDINARY_API_KEY,
                api_secret=Config.CLOUDINARY_API_SECRET,
                secure=True
            )
            cloudinary_configured = True
        except Exception as e:
            print(f"Error configuring Cloudinary: {e}")

def upload_image(image_file, prefix="item"):
    """
    Uploads an image file to Cloudinary if configured. 
    Otherwise, saves it locally to static/uploads.
    Returns the URL/path of the saved image.
    """
    if not image_file or image_file.filename == '':
        return None

    filename = f"{prefix}_{uuid.uuid4().hex}_{secure_filename(image_file.filename)}"

    # 1. Cloudinary upload path
    if cloudinary_configured:
        try:
            # Upload with optimization options
            # Convert to webp and fetch with auto quality/width limits
            upload_result = cloudinary.uploader.upload(
                image_file,
                public_id=filename.rsplit('.', 1)[0],
                folder="findit",
                transformation=[
                    {"width": 800, "height": 800, "crop": "limit"},
                    {"quality": "auto", "fetch_format": "auto"}
                ]
            )
            return upload_result.get("secure_url")
        except Exception as e:
            print(f"Cloudinary upload failed: {e}. Falling back to local storage.")
            image_file.seek(0)  # Reset stream position

    # 2. Local fallback path
    try:
        from app import save_and_optimize_image
    except ImportError:
        # Avoid circular import if save_and_optimize_image is elsewhere
        def save_and_optimize_image(file, path):
            file.save(path)
            return True

    upload_folder = Config.UPLOAD_FOLDER
    os.makedirs(upload_folder, exist_ok=True)
    save_path = os.path.join(upload_folder, filename)
    
    if save_and_optimize_image(image_file, save_path):
        return f"static/uploads/{filename}"
    return None
