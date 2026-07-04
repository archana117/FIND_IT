import sqlite3
from database import get_db_connection

def create_contact_request(item_type, item_id, requester_id, owner_id):
    """
    Creates a new contact request.
    Returns the request ID.
    """
    if requester_id == owner_id:
        return None  # Can't request contact with yourself
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Check if one already exists
        existing = cursor.execute('''
            SELECT id FROM contact_requests 
            WHERE item_type = ? AND item_id = ? AND requester_id = ? AND owner_id = ?
        ''', (item_type, item_id, requester_id, owner_id)).fetchone()
        
        if existing:
            return existing['id']
            
        cursor.execute('''
            INSERT INTO contact_requests (item_type, item_id, requester_id, owner_id, status)
            VALUES (?, ?, ?, ?, 'pending')
        ''', (item_type, item_id, requester_id, owner_id))
        conn.commit()
        req_id = cursor.lastrowid
        return req_id
    except sqlite3.Error as e:
        print(f"Database error in create_contact_request: {e}")
        return None
    finally:
        conn.close()

def approve_contact_request(request_id, approver_id):
    """
    Approves a contact request. Only the item owner/receiver can approve.
    """
    conn = get_db_connection()
    try:
        # Verify the approver matches owner_id
        req = conn.execute('SELECT * FROM contact_requests WHERE id = ?', (request_id,)).fetchone()
        if not req:
            return False
            
        if req['owner_id'] != approver_id:
            return False
            
        conn.execute('UPDATE contact_requests SET status = "approved" WHERE id = ?', (request_id,))
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Error approving contact request: {e}")
        return False
    finally:
        conn.close()

def reject_contact_request(request_id, rejecter_id):
    """
    Rejects a contact request.
    """
    conn = get_db_connection()
    try:
        req = conn.execute('SELECT * FROM contact_requests WHERE id = ?', (request_id,)).fetchone()
        if not req or req['owner_id'] != rejecter_id:
            return False
            
        conn.execute('UPDATE contact_requests SET status = "rejected" WHERE id = ?', (request_id,))
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Error rejecting contact request: {e}")
        return False
    finally:
        conn.close()

def check_contact_permission(requester_id, owner_id, item_type, item_id):
    """
    Returns True if requester has permission to view the owner's contact details.
    Permission is granted if requester is the owner, or if there is an approved request.
    """
    if requester_id == owner_id:
        return True
        
    conn = get_db_connection()
    try:
        # Check in both directions (in case finder requests owner, or owner requests finder)
        res = conn.execute('''
            SELECT status FROM contact_requests 
            WHERE item_type = ? AND item_id = ? 
            AND ((requester_id = ? AND owner_id = ?) OR (requester_id = ? AND owner_id = ?))
            AND status = 'approved'
        ''', (item_type, item_id, requester_id, owner_id, owner_id, requester_id)).fetchone()
        return res is not None
    except sqlite3.Error as e:
        print(f"Error checking contact permission: {e}")
        return False
    finally:
        conn.close()

def get_contact_request_state(item_type, item_id, requester_id, owner_id):
    """
    Returns the details of the contact request between two users for a specific item.
    """
    conn = get_db_connection()
    try:
        res = conn.execute('''
            SELECT * FROM contact_requests 
            WHERE item_type = ? AND item_id = ? 
            AND ((requester_id = ? AND owner_id = ?) OR (requester_id = ? AND owner_id = ?))
        ''', (item_type, item_id, requester_id, owner_id, owner_id, requester_id)).fetchone()
        return dict(res) if res else None
    except sqlite3.Error as e:
        print(f"Error getting contact request: {e}")
        return None
    finally:
        conn.close()

def get_user_contact_requests(user_id):
    """
    Gets all incoming and outgoing contact requests for a user.
    """
    conn = get_db_connection()
    try:
        # Incoming requests (others wanting to contact this user)
        # We join with users and lost/found tables to get context
        incoming = conn.execute('''
            SELECT r.id as request_id, r.item_type, r.item_id, r.status, r.created_at,
                   u.username as requester_name, u.email as requester_email
            FROM contact_requests r
            JOIN users u ON r.requester_id = u.id
            WHERE r.owner_id = ? AND r.status = 'pending'
        ''', (user_id,)).fetchall()
        
        # Outgoing requests (this user wanting to contact others)
        outgoing = conn.execute('''
            SELECT r.id as request_id, r.item_type, r.item_id, r.status, r.created_at,
                   u.username as owner_name, u.email as owner_email
            FROM contact_requests r
            JOIN users u ON r.owner_id = u.id
            WHERE r.requester_id = ?
        ''', (user_id,)).fetchall()
        
        return {
            'incoming': [dict(r) for r in incoming],
            'outgoing': [dict(r) for r in outgoing]
        }
    except sqlite3.Error as e:
        print(f"Error getting user contact requests: {e}")
        return {'incoming': [], 'outgoing': []}
    finally:
        conn.close()
