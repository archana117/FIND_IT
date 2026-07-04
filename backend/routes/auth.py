import re
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort
from werkzeug.security import generate_password_hash, check_password_hash
from database import (
    create_user, get_user_by_username, get_user_by_email, get_user_by_id
)
from utils.security import limit_rate, verify_csrf_token, clean_input, generate_jwt_token
from services.fraud_detector import send_and_save_otp, verify_otp, is_user_blocked

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['GET', 'POST'])
@limit_rate(limit=10, period=60)
def register():
    if session.get('user_id'):
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        verify_csrf_token()
        username = clean_input(request.form.get('username', ''))
        email = clean_input(request.form.get('email', ''))
        phone = clean_input(request.form.get('phone', ''))
        password = request.form.get('password', '')
        
        if not username or not email or not password:
            flash('Please fill in all required fields.', 'error')
            return render_template('register.html')
            
        # Email validation pattern
        if not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            flash('Invalid email address format.', 'error')
            return render_template('register.html')
            
        # Strong password validation
        if len(password) < 8 or not re.search(r"[a-z]", password) or not re.search(r"[A-Z]", password) or not re.search(r"[0-9]", password) or not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
            flash('Password must be at least 8 characters long and contain lowercase, uppercase, number, and special character.', 'error')
            return render_template('register.html')
            
        # Check existing user
        if get_user_by_username(username) or get_user_by_email(email):
            flash('Username or Email already exists.', 'error')
            return render_template('register.html')
            
        password_hash = generate_password_hash(password)
        user_id = create_user(username, email, password_hash, phone, role='user')
        
        if user_id:
            # Trigger OTP Verification Code
            if send_and_save_otp(user_id):
                session['otp_user_id'] = user_id
                flash('Account created! An OTP has been sent to your email. Please verify.', 'info')
                return redirect(url_for('auth.verify_account'))
            else:
                flash('Registration successful! Please login.', 'success')
                return redirect(url_for('auth.login'))
        else:
            flash('Error creating account. Try again later.', 'error')
            
    return render_template('register.html')

@auth_bp.route('/verify-otp', methods=['GET', 'POST'])
def verify_account():
    user_id = session.get('otp_user_id')
    if not user_id:
        flash('Session expired. Please login.', 'error')
        return redirect(url_for('auth.login'))
        
    if request.method == 'POST':
        verify_csrf_token()
        otp_code = clean_input(request.form.get('otp', ''))
        
        if verify_otp(user_id, otp_code):
            session.pop('otp_user_id', None)
            # Log the user in directly
            user = get_user_by_id(user_id)
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            flash('Email verified successfully! Welcome to FindIt.', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid or expired OTP. Please try again.', 'error')
            
    return render_template('login.html', show_otp=True)

@auth_bp.route('/resend-otp', methods=['POST'])
def resend_otp():
    user_id = session.get('otp_user_id')
    if not user_id:
        return {"status": "error", "message": "No active verification session."}, 400
        
    if send_and_save_otp(user_id):
        flash('A new OTP has been sent to your email.', 'success')
    else:
        flash('Failed to resend OTP or maximum limit reached. Please try again later.', 'error')
        
    # Redirect to whichever verification context is currently active
    if session.get('reset_password_allowed'):
        return redirect(url_for('auth.reset_password'))
    return redirect(url_for('auth.verify_account'))

@auth_bp.route('/login', methods=['GET', 'POST'])
@limit_rate(limit=10, period=60)
def login():
    if session.get('user_id'):
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        verify_csrf_token()
        username = clean_input(request.form.get('username', ''))
        password = request.form.get('password', '')
        remember = request.form.get('remember')
        
        user = get_user_by_username(username)
        if user:
            # Check blocking
            if is_user_blocked(user['id']):
                flash('Your account has been blocked by the administrator.', 'error')
                return render_template('login.html')

            if check_password_hash(user['password_hash'], password):
                # Check verification status
                if not user.get('is_verified', 0):
                    session['otp_user_id'] = user['id']
                    send_and_save_otp(user['id'])
                    flash('Please verify your email to login. OTP sent.', 'info')
                    return redirect(url_for('auth.verify_account'))

                session['user_id'] = user['id']
                session['username'] = user['username']
                session['role'] = user['role']
                
                # Enforce session persistence for "Remember Me"
                if remember:
                    session.permanent = True
                else:
                    session.permanent = False
                
                # Generate JWT for client API authorization
                token = generate_jwt_token(user['id'], user['username'], user['role'])
                session['auth_token'] = token
                
                flash(f'Welcome back, {user["username"]}!', 'success')
                return redirect(url_for('index'))
                
        flash('Invalid username or password.', 'error')
            
    return render_template('login.html')

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if session.get('user_id'):
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        verify_csrf_token()
        email = clean_input(request.form.get('email', ''))
        
        if not email:
            flash('Please enter your email address.', 'error')
            return render_template('forgot_password.html')
            
        user = get_user_by_email(email)
        if user:
            if send_and_save_otp(user['id']):
                session['otp_user_id'] = user['id']
                session['reset_password_allowed'] = True
                flash('A password reset OTP has been sent to your email.', 'info')
                return redirect(url_for('auth.reset_password'))
            else:
                flash('Failed to generate reset code or rate-limit exceeded. Try again later.', 'error')
        else:
            flash('If the email is registered, a password reset OTP has been sent.', 'info')
            
    return render_template('forgot_password.html')

@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    user_id = session.get('otp_user_id')
    if not user_id or not session.get('reset_password_allowed'):
        flash('Session expired or access denied.', 'error')
        return redirect(url_for('auth.login'))
        
    if request.method == 'POST':
        verify_csrf_token()
        otp_code = clean_input(request.form.get('otp', ''))
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not otp_code or not new_password or not confirm_password:
            flash('Please fill in all fields.', 'error')
            return render_template('reset_password.html')
            
        if new_password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('reset_password.html')
            
        # Password strength validation
        if len(new_password) < 8 or not re.search(r"[a-z]", new_password) or not re.search(r"[A-Z]", new_password) or not re.search(r"[0-9]", new_password) or not re.search(r"[!@#$%^&*(),.?\":{}|<>]", new_password):
            flash('Password must be at least 8 characters long and contain lowercase, uppercase, number, and special character.', 'error')
            return render_template('reset_password.html')
            
        if verify_otp(user_id, otp_code):
            from database import get_db_connection
            import sqlite3
            conn = get_db_connection()
            try:
                password_hash = generate_password_hash(new_password)
                conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))
                conn.commit()
                
                session.pop('otp_user_id', None)
                session.pop('reset_password_allowed', None)
                
                flash('Password reset successful! Please log in.', 'success')
                return redirect(url_for('auth.login'))
            except sqlite3.Error as e:
                print(f"Error resetting password: {e}")
                flash('Database error occurred. Please try again.', 'error')
            finally:
                conn.close()
        else:
            flash('Invalid or expired OTP. Please try again.', 'error')
            
    return render_template('reset_password.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('index'))
