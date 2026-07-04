import secrets
import string
import datetime
import sqlite3
import hashlib
from database import get_db_connection
from services.mail_service import send_otp

def generate_otp():
    """Generates a secure 6-digit numerical OTP."""
    return "".join(secrets.choice(string.digits) for _ in range(6))

def send_and_save_otp(user_id):
    """
    Generates OTP, hashes it, sets expiry to 5 minutes from now,
    enforces resend limits, and triggers mail.
    """
    conn = get_db_connection()
    try:
        user = conn.execute(
            "SELECT username, email, otp_resends, otp_resend_expiry FROM users WHERE id = ?", 
            (user_id,)
        ).fetchone()
        
        if not user:
            return False
            
        now = datetime.datetime.now()
        
        # Enforce maximum resend limit (3 resends allowed, then blocked for 15 minutes)
        if user['otp_resends'] is not None and user['otp_resends'] >= 3:
            if user['otp_resend_expiry']:
                resend_expiry = datetime.datetime.strptime(user['otp_resend_expiry'], "%Y-%m-%d %H:%M:%S")
                if now < resend_expiry:
                    print(f"Resend limit reached for user {user_id}. Blocked until {user['otp_resend_expiry']}")
                    return False
            
            # Lock has expired, reset resends
            conn.execute("UPDATE users SET otp_resends = 0, otp_resend_expiry = NULL WHERE id = ?", (user_id,))
            conn.commit()
            resends = 0
        else:
            resends = user['otp_resends'] or 0

        otp = generate_otp()
        hashed_otp = hashlib.sha256(otp.encode()).hexdigest()
        expiry = (now + datetime.timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
        
        new_resends = resends + 1
        resend_expiry_str = None
        if new_resends >= 3:
            resend_expiry_str = (now + datetime.timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")

        conn.execute('''
            UPDATE users 
            SET otp_code = ?, otp_expiry = ?, otp_attempts = 0, otp_resends = ?, otp_resend_expiry = ? 
            WHERE id = ?
        ''', (hashed_otp, expiry, new_resends, resend_expiry_str, user_id))
        conn.commit()
        
        # Send mail (using mail service, mock logs if not configured)
        send_otp(user['email'], user['username'], otp)
        return True
    except sqlite3.Error as e:
        print(f"Error saving OTP: {e}")
        return False
    finally:
        conn.close()

def verify_otp(user_id, code):
    """
    Verifies input OTP code. If correct and not expired, sets is_verified=1.
    Locks after 5 failed attempts.
    """
    if not code:
        return False
    conn = get_db_connection()
    try:
        user = conn.execute(
            "SELECT otp_code, otp_expiry, otp_attempts FROM users WHERE id = ?", 
            (user_id,)
        ).fetchone()
        
        if not user or not user['otp_code']:
            return False
            
        attempts = user['otp_attempts'] or 0
        if attempts >= 5:
            # Clear OTP details
            conn.execute('''
                UPDATE users 
                SET otp_code = NULL, otp_expiry = NULL, otp_attempts = 0, otp_resends = 0, otp_resend_expiry = NULL 
                WHERE id = ?
            ''', (user_id,))
            conn.commit()
            print(f"Max attempts exceeded for user {user_id}. OTP cleared.")
            return False
            
        # Check expiry
        now = datetime.datetime.now()
        expiry = datetime.datetime.strptime(user['otp_expiry'], "%Y-%m-%d %H:%M:%S")
        
        if now > expiry:
            # Auto delete expired OTP
            conn.execute('''
                UPDATE users 
                SET otp_code = NULL, otp_expiry = NULL, otp_attempts = 0 
                WHERE id = ?
            ''', (user_id,))
            conn.commit()
            print(f"OTP expired for user {user_id}. Auto deleted.")
            return False
            
        hashed_incoming = hashlib.sha256(code.encode()).hexdigest()
        if user['otp_code'] == hashed_incoming:
            conn.execute('''
                UPDATE users 
                SET is_verified = 1, otp_code = NULL, otp_expiry = NULL, otp_attempts = 0, otp_resends = 0, otp_resend_expiry = NULL 
                WHERE id = ?
            ''', (user_id,))
            conn.commit()
            return True
        else:
            # Mismatch - increment attempts
            conn.execute("UPDATE users SET otp_attempts = otp_attempts + 1 WHERE id = ?", (user_id,))
            conn.commit()
            return False
    except sqlite3.Error as e:
        print(f"Error verifying OTP: {e}")
        return False
    finally:
        conn.close()

def block_user(user_id):
    conn = get_db_connection()
    try:
        conn.execute("UPDATE users SET is_blocked = 1 WHERE id = ?", (user_id,))
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Error blocking user: {e}")
        return False
    finally:
        conn.close()

def unblock_user(user_id):
    conn = get_db_connection()
    try:
        conn.execute("UPDATE users SET is_blocked = 0 WHERE id = ?", (user_id,))
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Error unblocking user: {e}")
        return False
    finally:
        conn.close()

def is_user_blocked(user_id):
    conn = get_db_connection()
    try:
        res = conn.execute("SELECT is_blocked FROM users WHERE id = ?", (user_id,)).fetchone()
        return res['is_blocked'] == 1 if res else False
    except sqlite3.Error as e:
        print(f"Error checking user block: {e}")
        return False
    finally:
        conn.close()

def report_item(item_type, item_id):
    """
    Reports an item as fake or spam. 
    If report count exceeds 3, flags the listing automatically as fake.
    """
    if item_type not in ['lost', 'found']:
        return False
        
    table = "lost_items" if item_type == 'lost' else "found_items"
    
    conn = get_db_connection()
    try:
        # Increment report count
        conn.execute(f'''
            UPDATE {table} 
            SET report_count = report_count + 1 
            WHERE id = ?
        ''', (item_id,))
        
        # Check if we should flag it
        item = conn.execute(f"SELECT report_count FROM {table} WHERE id = ?", (item_id,)).fetchone()
        if item and item['report_count'] >= 3:
            conn.execute(f'''
                UPDATE {table} 
                SET is_flagged_fake = 1 
                WHERE id = ?
            ''', (item_id,))
            
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Error reporting item: {e}")
        return False
    finally:
        conn.close()

def get_flagged_items():
    """
    Retrieves all items flagged as fake or having reports for admin review.
    """
    conn = get_db_connection()
    try:
        lost = conn.execute('''
            SELECT id, 'lost' as item_type, item_name, owner_name as reporter_name, is_flagged_fake, report_count 
            FROM lost_items WHERE report_count > 0 OR is_flagged_fake = 1
        ''').fetchall()
        
        found = conn.execute('''
            SELECT id, 'found' as item_type, item_name, finder_name as reporter_name, is_flagged_fake, report_count 
            FROM found_items WHERE report_count > 0 OR is_flagged_fake = 1
        ''').fetchall()
        
        return [dict(x) for x in lost] + [dict(x) for x in found]
    except sqlite3.Error as e:
        print(f"Error fetching flagged items: {e}")
        return []
    finally:
        conn.close()

def is_duplicate_listing(user_id, item_name, category, description, item_type='lost'):
    """
    Checks if a user is submitting a duplicate item within a short timeframe (last 24 hours).
    Checks category matching and similarity of names.
    """
    if not user_id:
        return False
        
    table = "lost_items" if item_type == 'lost' else "found_items"
    conn = get_db_connection()
    try:
        # Get items reported by this user in the last 24 hours
        time_limit = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        
        rows = conn.execute(f'''
            SELECT item_name, description FROM {table}
            WHERE user_id = ? AND category = ? AND created_at >= ?
        ''', (user_id, category, time_limit)).fetchall()
        
        from ai.semantic_search import get_semantic_similarity
        
        for row in rows:
            # If name matches closely (SequenceMatcher ratio > 0.85) or descriptions match semantically
            name_sim = get_semantic_similarity(row['item_name'], item_name)
            desc_sim = get_semantic_similarity(row['description'], description)
            if name_sim > 0.85 or desc_sim > 0.85:
                return True
                
        return False
    except Exception as e:
        print(f"Duplicate listing check failed: {e}")
        return False
    finally:
        conn.close()
