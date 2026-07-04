import sqlite3
import os
import json
from config import Config

def get_db_connection():
    db_path = Config.DATABASE
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Create Users table (added is_verified, is_blocked, otp_code, otp_expiry, otp_attempts, otp_resends, otp_resend_expiry)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username VARCHAR(80) UNIQUE NOT NULL,
        email VARCHAR(120) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        phone VARCHAR(20),
        role VARCHAR(20) DEFAULT 'user',
        otp_code VARCHAR(10),
        otp_expiry TIMESTAMP,
        otp_attempts INTEGER DEFAULT 0,
        otp_resends INTEGER DEFAULT 0,
        otp_resend_expiry TIMESTAMP,
        is_verified INTEGER DEFAULT 0,
        is_blocked INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # 2. Create Lost_Items table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS lost_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        owner_name VARCHAR(100) NOT NULL,
        contact_number VARCHAR(20) NOT NULL,
        email VARCHAR(120) NOT NULL,
        item_name VARCHAR(100) NOT NULL,
        category VARCHAR(50) NOT NULL,
        description TEXT NOT NULL,
        image_path VARCHAR(255),
        location VARCHAR(150) NOT NULL,
        date_lost DATE NOT NULL,
        additional_notes TEXT,
        status VARCHAR(20) DEFAULT 'open',
        latitude REAL,
        longitude REAL,
        ocr_text TEXT,
        image_embedding TEXT,
        desc_embedding TEXT,
        is_flagged_fake INTEGER DEFAULT 0,
        report_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
    )
    ''')
    
    # 3. Create Found_Items table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS found_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        finder_name VARCHAR(100) NOT NULL,
        contact_number VARCHAR(20) NOT NULL,
        email VARCHAR(120) NOT NULL,
        item_name VARCHAR(100) NOT NULL,
        category VARCHAR(50) NOT NULL,
        description TEXT NOT NULL,
        image_path VARCHAR(255),
        location VARCHAR(150) NOT NULL,
        date_found DATE NOT NULL,
        additional_notes TEXT,
        status VARCHAR(20) DEFAULT 'open',
        latitude REAL,
        longitude REAL,
        ocr_text TEXT,
        image_embedding TEXT,
        desc_embedding TEXT,
        is_flagged_fake INTEGER DEFAULT 0,
        report_count INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
    )
    ''')
    
    # 4. Create Matches table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        lost_item_id INTEGER NOT NULL,
        found_item_id INTEGER NOT NULL,
        similarity_score FLOAT NOT NULL,
        status VARCHAR(20) DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (lost_item_id) REFERENCES lost_items(id) ON DELETE CASCADE,
        FOREIGN KEY (found_item_id) REFERENCES found_items(id) ON DELETE CASCADE,
        UNIQUE(lost_item_id, found_item_id)
    )
    ''')

    # 5. Create Contact Requests table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS contact_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_type VARCHAR(20) NOT NULL,
        item_id INTEGER NOT NULL,
        requester_id INTEGER NOT NULL,
        owner_id INTEGER NOT NULL,
        status VARCHAR(20) DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (requester_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
    )
    ''')

    # 6. Create Chat Messages table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id INTEGER NOT NULL,
        receiver_id INTEGER NOT NULL,
        message TEXT,
        image_path VARCHAR(255),
        is_read INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (receiver_id) REFERENCES users(id) ON DELETE CASCADE
    )
    ''')
    
    # Run Schema Migrations (Add missing columns dynamically for backward compatibility)
    alter_queries = [
        # For users
        ("ALTER TABLE users ADD COLUMN otp_code VARCHAR(10)", "users", "otp_code"),
        ("ALTER TABLE users ADD COLUMN otp_expiry TIMESTAMP", "users", "otp_expiry"),
        ("ALTER TABLE users ADD COLUMN otp_attempts INTEGER DEFAULT 0", "users", "otp_attempts"),
        ("ALTER TABLE users ADD COLUMN otp_resends INTEGER DEFAULT 0", "users", "otp_resends"),
        ("ALTER TABLE users ADD COLUMN otp_resend_expiry TIMESTAMP", "users", "otp_resend_expiry"),
        ("ALTER TABLE users ADD COLUMN is_verified INTEGER DEFAULT 0", "users", "is_verified"),
        ("ALTER TABLE users ADD COLUMN is_blocked INTEGER DEFAULT 0", "users", "is_blocked"),
        # For lost_items
        ("ALTER TABLE lost_items ADD COLUMN latitude REAL", "lost_items", "latitude"),
        ("ALTER TABLE lost_items ADD COLUMN longitude REAL", "lost_items", "longitude"),
        ("ALTER TABLE lost_items ADD COLUMN ocr_text TEXT", "lost_items", "ocr_text"),
        ("ALTER TABLE lost_items ADD COLUMN image_embedding TEXT", "lost_items", "image_embedding"),
        ("ALTER TABLE lost_items ADD COLUMN desc_embedding TEXT", "lost_items", "desc_embedding"),
        ("ALTER TABLE lost_items ADD COLUMN is_flagged_fake INTEGER DEFAULT 0", "lost_items", "is_flagged_fake"),
        ("ALTER TABLE lost_items ADD COLUMN report_count INTEGER DEFAULT 0", "lost_items", "report_count"),
        # For found_items
        ("ALTER TABLE found_items ADD COLUMN latitude REAL", "found_items", "latitude"),
        ("ALTER TABLE found_items ADD COLUMN longitude REAL", "found_items", "longitude"),
        ("ALTER TABLE found_items ADD COLUMN ocr_text TEXT", "found_items", "ocr_text"),
        ("ALTER TABLE found_items ADD COLUMN image_embedding TEXT", "found_items", "image_embedding"),
        ("ALTER TABLE found_items ADD COLUMN desc_embedding TEXT", "found_items", "desc_embedding"),
        ("ALTER TABLE found_items ADD COLUMN is_flagged_fake INTEGER DEFAULT 0", "found_items", "is_flagged_fake"),
        ("ALTER TABLE found_items ADD COLUMN report_count INTEGER DEFAULT 0", "found_items", "report_count"),
    ]

    for query, table, column in alter_queries:
        try:
            # Check if column exists
            info = cursor.execute(f"PRAGMA table_info({table})").fetchall()
            col_names = [col[1] for col in info]
            if column not in col_names:
                cursor.execute(query)
                print(f"Migration: Added column '{column}' to table '{table}'")
        except sqlite3.Error as err:
            print(f"Migration notice (table {table}, col {column}): {err}")
            
    # Add indexes for performance optimization and fast embeddings similarity lookup
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_lost_items_category ON lost_items(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_found_items_category ON found_items(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_lost_items_status ON lost_items(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_found_items_status ON found_items(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_sender_receiver ON chat_messages(sender_id, receiver_id)")
    except sqlite3.Error as err:
        print(f"Index creation error: {err}")

    # Create default Admin if not exists
    cursor.execute("SELECT * FROM users WHERE role = 'admin'")
    if not cursor.fetchone():
        from werkzeug.security import generate_password_hash
        admin_pass = generate_password_hash('admin123')
        cursor.execute(
            "INSERT INTO users (username, email, password_hash, phone, role, is_verified) VALUES (?, ?, ?, ?, ?, 1)",
            ('admin', 'admin@findit.com', admin_pass, '1234567890', 'admin')
        )
    
    conn.commit()
    conn.close()

# User Helpers
def create_user(username, email, password_hash, phone=None, role='user'):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, email, password_hash, phone, role, is_verified) VALUES (?, ?, ?, ?, ?, 0)",
            (username, email, password_hash, phone, role)
        )
        conn.commit()
        user_id = cursor.lastrowid
        return user_id
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def get_user_by_id(user_id):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(user) if user else None

def get_user_by_username(username):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return dict(user) if user else None

def get_user_by_email(email):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return dict(user) if user else None

def get_all_users():
    conn = get_db_connection()
    users = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(u) for u in users]

def delete_user(user_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

# Lost Items Helpers
def create_lost_item(user_id, owner_name, contact_number, email, item_name, category, description, image_path, location, date_lost, additional_notes, latitude=None, longitude=None, ocr_text=None, image_embedding=None, desc_embedding=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Serialize embeddings if present
    img_emb_str = json.dumps(image_embedding) if image_embedding is not None else None
    desc_emb_str = json.dumps(desc_embedding) if desc_embedding is not None else None

    cursor.execute('''
        INSERT INTO lost_items (
            user_id, owner_name, contact_number, email, item_name, category, 
            description, image_path, location, date_lost, additional_notes,
            latitude, longitude, ocr_text, image_embedding, desc_embedding
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id, owner_name, contact_number, email, item_name, category, 
        description, image_path, location, date_lost, additional_notes,
        latitude, longitude, ocr_text, img_emb_str, desc_emb_str
    ))
    conn.commit()
    item_id = cursor.lastrowid
    conn.close()
    return item_id

def get_lost_item(item_id):
    conn = get_db_connection()
    item = conn.execute("SELECT * FROM lost_items WHERE id = ?", (item_id,)).fetchone()
    conn.close()
    if item:
        res = dict(item)
        # Deserialize embeddings
        res['image_embedding'] = json.loads(res['image_embedding']) if res.get('image_embedding') else None
        res['desc_embedding'] = json.loads(res['desc_embedding']) if res.get('desc_embedding') else None
        return res
    return None

def get_all_lost_items(category=None, location=None, query=None):
    conn = get_db_connection()
    sql = "SELECT * FROM lost_items WHERE status = 'open' AND is_flagged_fake = 0"
    params = []
    if category:
        sql += " AND category = ?"
        params.append(category)
    if location:
        sql += " AND location LIKE ?"
        params.append(f"%{location}%")
    if query:
        # Basic text fallback, advanced uses semantic_search route
        sql += " AND (item_name LIKE ? OR description LIKE ? OR ocr_text LIKE ?)"
        params.extend([f"%{query}%", f"%{query}%", f"%{query}%"])
    sql += " ORDER BY date_lost DESC"
    items = conn.execute(sql, params).fetchall()
    conn.close()
    
    results = []
    for r in items:
        d = dict(r)
        d['image_embedding'] = json.loads(d['image_embedding']) if d.get('image_embedding') else None
        d['desc_embedding'] = json.loads(d['desc_embedding']) if d.get('desc_embedding') else None
        results.append(d)
    return results

def update_lost_item_status(item_id, status):
    conn = get_db_connection()
    conn.execute("UPDATE lost_items SET status = ? WHERE id = ?", (status, item_id))
    conn.commit()
    conn.close()

def delete_lost_item(item_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM lost_items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()

# Found Items Helpers
def create_found_item(user_id, finder_name, contact_number, email, item_name, category, description, image_path, location, date_found, additional_notes, latitude=None, longitude=None, ocr_text=None, image_embedding=None, desc_embedding=None):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Serialize embeddings if present
    img_emb_str = json.dumps(image_embedding) if image_embedding is not None else None
    desc_emb_str = json.dumps(desc_embedding) if desc_embedding is not None else None

    cursor.execute('''
        INSERT INTO found_items (
            user_id, finder_name, contact_number, email, item_name, category, 
            description, image_path, location, date_found, additional_notes,
            latitude, longitude, ocr_text, image_embedding, desc_embedding
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        user_id, finder_name, contact_number, email, item_name, category, 
        description, image_path, location, date_found, additional_notes,
        latitude, longitude, ocr_text, img_emb_str, desc_emb_str
    ))
    conn.commit()
    item_id = cursor.lastrowid
    conn.close()
    return item_id

def get_found_item(item_id):
    conn = get_db_connection()
    item = conn.execute("SELECT * FROM found_items WHERE id = ?", (item_id,)).fetchone()
    conn.close()
    if item:
        res = dict(item)
        res['image_embedding'] = json.loads(res['image_embedding']) if res.get('image_embedding') else None
        res['desc_embedding'] = json.loads(res['desc_embedding']) if res.get('desc_embedding') else None
        return res
    return None

def get_all_found_items(category=None, location=None, query=None):
    conn = get_db_connection()
    sql = "SELECT * FROM found_items WHERE status = 'open' AND is_flagged_fake = 0"
    params = []
    if category:
        sql += " AND category = ?"
        params.append(category)
    if location:
        sql += " AND location LIKE ?"
        params.append(f"%{location}%")
    if query:
        sql += " AND (item_name LIKE ? OR description LIKE ? OR ocr_text LIKE ?)"
        params.extend([f"%{query}%", f"%{query}%", f"%{query}%"])
    sql += " ORDER BY date_found DESC"
    items = conn.execute(sql, params).fetchall()
    conn.close()
    
    results = []
    for r in items:
        d = dict(r)
        d['image_embedding'] = json.loads(d['image_embedding']) if d.get('image_embedding') else None
        d['desc_embedding'] = json.loads(d['desc_embedding']) if d.get('desc_embedding') else None
        results.append(d)
    return results

def update_found_item_status(item_id, status):
    conn = get_db_connection()
    conn.execute("UPDATE found_items SET status = ? WHERE id = ?", (status, item_id))
    conn.commit()
    conn.close()

def delete_found_item(item_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM found_items WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()

# Matches Helpers
def create_match(lost_item_id, found_item_id, similarity_score):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO matches (lost_item_id, found_item_id, similarity_score, status)
            VALUES (?, ?, ?, 'pending')
        ''', (lost_item_id, found_item_id, similarity_score))
        conn.commit()
        match_id = cursor.lastrowid
        return match_id
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def get_matches_for_lost_item(lost_item_id):
    conn = get_db_connection()
    sql = '''
        SELECT m.id as match_id, m.similarity_score, m.status as match_status, f.*
        FROM matches m
        JOIN found_items f ON m.found_item_id = f.id
        WHERE m.lost_item_id = ? AND f.is_flagged_fake = 0
        ORDER BY m.similarity_score DESC
    '''
    matches = conn.execute(sql, (lost_item_id,)).fetchall()
    conn.close()
    return [dict(m) for m in matches]

def get_matches_for_found_item(found_item_id):
    conn = get_db_connection()
    sql = '''
        SELECT m.id as match_id, m.similarity_score, m.status as match_status, l.*
        FROM matches m
        JOIN lost_items l ON m.lost_item_id = l.id
        WHERE m.found_item_id = ? AND l.is_flagged_fake = 0
        ORDER BY m.similarity_score DESC
    '''
    matches = conn.execute(sql, (found_item_id,)).fetchall()
    conn.close()
    return [dict(m) for m in matches]

def get_all_matches():
    conn = get_db_connection()
    sql = '''
        SELECT m.id as match_id, m.similarity_score, m.status as match_status, m.created_at as match_created_at,
               l.item_name as lost_item_name, l.id as lost_item_id, l.owner_name,
               f.item_name as found_item_name, f.id as found_item_id, f.finder_name
        FROM matches m
        JOIN lost_items l ON m.lost_item_id = l.id
        JOIN found_items f ON m.found_item_id = f.id
        ORDER BY m.similarity_score DESC
    '''
    matches = conn.execute(sql).fetchall()
    conn.close()
    return [dict(m) for m in matches]

def update_match_status(match_id, status):
    conn = get_db_connection()
    conn.execute("UPDATE matches SET status = ? WHERE id = ?", (status, match_id))
    conn.commit()
    conn.close()

def delete_match(match_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM matches WHERE id = ?", (match_id,))
    conn.commit()
    conn.close()

def get_dashboard_stats():
    conn = get_db_connection()
    stats = {}
    
    # Simple counting stats
    stats['total_users'] = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    stats['total_lost'] = conn.execute("SELECT COUNT(*) FROM lost_items").fetchone()[0]
    stats['total_found'] = conn.execute("SELECT COUNT(*) FROM found_items").fetchone()[0]
    stats['total_matches'] = conn.execute("SELECT COUNT(*) FROM matches WHERE similarity_score >= 50.0").fetchone()[0]
    stats['resolved_matches'] = conn.execute("SELECT COUNT(*) FROM matches WHERE status = 'approved'").fetchone()[0]
    
    # Lost by Category
    categories = conn.execute("SELECT category, COUNT(*) as count FROM lost_items GROUP BY category").fetchall()
    stats['lost_categories'] = {c['category']: c['count'] for c in categories}
    
    # Found by Category
    categories_f = conn.execute("SELECT category, COUNT(*) as count FROM found_items GROUP BY category").fetchall()
    stats['found_categories'] = {c['category']: c['count'] for c in categories_f}
    
    # Recent items
    stats['recent_lost'] = [dict(r) for r in conn.execute("SELECT * FROM lost_items ORDER BY created_at DESC LIMIT 6").fetchall()]
    stats['recent_found'] = [dict(r) for r in conn.execute("SELECT * FROM found_items ORDER BY created_at DESC LIMIT 6").fetchall()]
    
    # User stats (active, blocked, verified)
    stats['blocked_users'] = conn.execute("SELECT COUNT(*) FROM users WHERE is_blocked = 1").fetchone()[0]
    stats['verified_users'] = conn.execute("SELECT COUNT(*) FROM users WHERE is_verified = 1").fetchone()[0]
    
    # Monthly reports stats (for charts)
    monthly_lost = conn.execute("SELECT strftime('%Y-%m', created_at) as month, COUNT(*) as count FROM lost_items GROUP BY month ORDER BY month DESC LIMIT 6").fetchall()
    stats['monthly_lost'] = {m['month']: m['count'] for m in monthly_lost}
    
    monthly_found = conn.execute("SELECT strftime('%Y-%m', created_at) as month, COUNT(*) as count FROM found_items GROUP BY month ORDER BY month DESC LIMIT 6").fetchall()
    stats['monthly_found'] = {m['month']: m['count'] for m in monthly_found}
    
    conn.close()
    return stats
