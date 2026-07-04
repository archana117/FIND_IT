import time
import uuid
import re
from functools import wraps
from flask import request, session, abort, flash, redirect, url_for, g
from config import Config

# Try loading JWT
HAS_JWT = False
try:
    import jwt
    HAS_JWT = True
except ImportError:
    pass

# Custom Rate Limiter Storage: IP address -> list of timestamps
rate_limit_records = {}

def clean_input(text):
    """
    Sanitizes string inputs to prevent Basic Cross-Site Scripting (XSS).
    """
    if not text:
        return ""
    # Strip HTML tags
    clean = re.sub(r'<[^>]*>', '', str(text))
    # Replace special characters with HTML entities
    clean = clean.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&#x27;')
    return clean.strip()

def limit_rate(limit=20, period=60):
    """
    Custom decorator to rate limit endpoints.
    limit: Max number of requests allowed in the period.
    period: Time window in seconds.
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            ip = request.remote_addr
            now = time.time()
            
            # Initialize record for IP
            if ip not in rate_limit_records:
                rate_limit_records[ip] = []
                
            # Filter timestamps to keep only those within the current window
            rate_limit_records[ip] = [t for t in rate_limit_records[ip] if now - t < period]
            
            if len(rate_limit_records[ip]) >= limit:
                abort(429, description="Too many requests. Please try again later.")
                
            rate_limit_records[ip].append(now)
            return f(*args, **kwargs)
        return wrapped
    return decorator

# CSRF Protection
def generate_csrf_token():
    if '_csrf_token' not in session:
        session['_csrf_token'] = uuid.uuid4().hex
    return session['_csrf_token']

def verify_csrf_token():
    if request.method == "POST":
        token = request.form.get('_csrf_token') or request.headers.get('X-CSRF-Token')
        expected = session.get('_csrf_token')
        if not expected or token != expected:
            abort(400, description="CSRF token validation failed.")

# JWT Token Auth Helpers
def generate_jwt_token(user_id, username, role):
    """
    Generates a JWT token for APIs. Falls back to session-based token.
    """
    payload = {
        'user_id': user_id,
        'username': username,
        'role': role,
        'exp': time.time() + 86400  # 1 day expiration
    }
    if HAS_JWT:
        try:
            return jwt.encode(payload, Config.SECRET_KEY, algorithm='HS256')
        except Exception as e:
            print(f"JWT encode error: {e}")
            
    # Session fallback token
    return f"session_token_{user_id}_{int(payload['exp'])}"

def decode_jwt_token(token):
    """
    Decodes and verifies a JWT token.
    """
    if not token:
        return None
        
    if token.startswith("session_token_"):
        parts = token.split("_")
        try:
            user_id = int(parts[2])
            exp = int(parts[3])
            if time.time() < exp:
                return {'user_id': user_id}
        except (IndexError, ValueError):
            pass
        return None

    if HAS_JWT:
        try:
            payload = jwt.decode(token, Config.SECRET_KEY, algorithms=['HS256'])
            return payload
        except jwt.ExpiredSignatureError:
            print("JWT token expired")
        except jwt.InvalidTokenError:
            print("Invalid JWT token")
            
    return None

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('auth.login'))
            
        # Check if blocked
        from services.fraud_detector import is_user_blocked
        if is_user_blocked(session['user_id']):
            session.clear()
            flash('Your account has been blocked by the administrator.', 'error')
            return redirect(url_for('auth.login'))
            
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id') or session.get('role') != 'admin':
            abort(403, description="Administrator access required.")
        return f(*args, **kwargs)
    return decorated_function
