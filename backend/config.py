import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev_key_findit_9918237')
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, '..'))
    DATABASE = os.environ.get('DATABASE_URL', os.path.join(BASE_DIR, 'findit.db'))
    FRONTEND_DIR = os.path.join(PROJECT_ROOT, 'frontend')
    UPLOAD_FOLDER = os.path.join(FRONTEND_DIR, 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max image upload size
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
