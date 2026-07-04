import os
import sqlite3
from flask import session, request
from database import get_db_connection

# SocketIO reference that will be initialized in app.py
socketio = None
# Keep track of active users online: user_id -> set of sid (socket session ids)
online_users = {}

def init_socketio(socketio_instance):
    global socketio
    socketio = socketio_instance
    setup_event_handlers()

def setup_event_handlers():
    if socketio is None:
        return

    @socketio.on('connect')
    def handle_connect():
        user_id = session.get('user_id')
        if not user_id:
            return False  # Refuse connection if not logged in
            
        sid = request.sid
        if user_id not in online_users:
            online_users[user_id] = set()
            # Broadcast online status
            socketio.emit('status_change', {'user_id': user_id, 'status': 'online'})
            
        online_users[user_id].add(sid)
        # Join a private room named user_<id>
        from flask_socketio import join_room
        join_room(f"user_{user_id}")
        print(f"User {user_id} connected on socket {sid}")

    @socketio.on('disconnect')
    def handle_disconnect():
        user_id = session.get('user_id')
        if not user_id:
            return
            
        sid = request.sid
        if user_id in online_users:
            online_users[user_id].discard(sid)
            if not online_users[user_id]:
                del online_users[user_id]
                # Broadcast offline status
                socketio.emit('status_change', {'user_id': user_id, 'status': 'offline'})
        print(f"User {user_id} disconnected on socket {sid}")

    @socketio.on('send_msg')
    def handle_send_message(data):
        sender_id = session.get('user_id')
        recipient_id = data.get('recipient_id')
        message = data.get('message', '').strip()
        image_data = data.get('image', None)  # Base64 image or file stream
        
        if not sender_id or not recipient_id:
            return
            
        image_path = None
        # Handle Base64 image upload if provided in chat
        if image_data:
            try:
                import base64
                from io import BytesIO
                from werkzeug.datastructures import FileStorage
                from services.cloudinary_service import upload_image
                
                # Check format
                header, encoded = image_data.split(",", 1)
                file_ext = header.split(";")[0].split("/")[1]
                img_bytes = base64.b64decode(encoded)
                
                file_like = BytesIO(img_bytes)
                file_storage = FileStorage(file_like, filename=f"chat_{uuid_file_name()}.{file_ext}", content_type=f"image/{file_ext}")
                
                image_path = upload_image(file_storage, prefix="chat")
            except Exception as e:
                print(f"Error saving chat image: {e}")

        # Save to database
        msg_id = save_chat_message(sender_id, recipient_id, message, image_path)
        
        if msg_id:
            payload = {
                'id': msg_id,
                'sender_id': sender_id,
                'receiver_id': int(recipient_id),
                'message': message,
                'image_path': image_path,
                'is_read': 0,
                'created_at': 'Just now'
            }
            
            # Send to recipient room and sender room
            socketio.emit('new_msg', payload, room=f"user_{recipient_id}")
            socketio.emit('new_msg', payload, room=f"user_{sender_id}")

    @socketio.on('mark_read')
    def handle_mark_read(data):
        user_id = session.get('user_id')
        sender_id = data.get('sender_id')  # The one who sent the messages being read
        if not user_id or not sender_id:
            return
            
        mark_messages_as_read(sender_id, user_id)
        # Notify sender that their messages have been read
        socketio.emit('messages_read', {'reader_id': user_id, 'sender_id': sender_id}, room=f"user_{sender_id}")

def uuid_file_name():
    import uuid
    return uuid.uuid4().hex

# Database helpers for chat
def save_chat_message(sender_id, receiver_id, message, image_path=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO chat_messages (sender_id, receiver_id, message, image_path, is_read)
            VALUES (?, ?, ?, ?, 0)
        ''', (sender_id, receiver_id, message, image_path))
        conn.commit()
        return cursor.lastrowid
    except sqlite3.Error as e:
        print(f"Error saving chat message: {e}")
        return None
    finally:
        conn.close()

def get_chat_history(user1_id, user2_id):
    conn = get_db_connection()
    try:
        sql = '''
            SELECT * FROM chat_messages 
            WHERE (sender_id = ? AND receiver_id = ?) 
               OR (sender_id = ? AND receiver_id = ?)
            ORDER BY created_at ASC
        '''
        rows = conn.execute(sql, (user1_id, user2_id, user2_id, user1_id)).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.Error as e:
        print(f"Error loading chat history: {e}")
        return []
    finally:
        conn.close()

def mark_messages_as_read(sender_id, receiver_id):
    conn = get_db_connection()
    try:
        conn.execute('''
            UPDATE chat_messages 
            SET is_read = 1 
            WHERE sender_id = ? AND receiver_id = ? AND is_read = 0
        ''', (sender_id, receiver_id))
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Error marking messages as read: {e}")
        return False
    finally:
        conn.close()

def get_active_chat_partners(user_id):
    """
    Returns list of users that the current user has chatted with.
    """
    conn = get_db_connection()
    try:
        # Fetch distinct users from messages
        sql = '''
            SELECT DISTINCT partner_id, u.username, u.role
            FROM (
                SELECT receiver_id AS partner_id FROM chat_messages WHERE sender_id = ?
                UNION
                SELECT sender_id AS partner_id FROM chat_messages WHERE receiver_id = ?
            )
            JOIN users u ON partner_id = u.id
        '''
        rows = conn.execute(sql, (user_id, user_id)).fetchall()
        partners = []
        for r in rows:
            p_dict = dict(r)
            p_dict['online'] = r['partner_id'] in online_users
            # Count unread messages from this partner
            unread_count = conn.execute('''
                SELECT COUNT(*) FROM chat_messages 
                WHERE sender_id = ? AND receiver_id = ? AND is_read = 0
            ''', (r['partner_id'], user_id)).fetchone()[0]
            p_dict['unread_count'] = unread_count
            partners.append(p_dict)
        return partners
    except sqlite3.Error as e:
        print(f"Error getting active chat partners: {e}")
        return []
    finally:
        conn.close()
