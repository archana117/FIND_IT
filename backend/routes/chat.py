from flask import Blueprint, render_template, redirect, url_for, session, flash, abort
from utils.security import login_required
from database import get_user_by_id
from services.chat_service import get_chat_history, get_active_chat_partners, mark_messages_as_read

chat_bp = Blueprint('chat', __name__)

@chat_bp.route('/chat')
@login_required
def lobby():
    partners = get_active_chat_partners(session['user_id'])
    
    # If there are partners, automatically redirect to the first one
    if partners:
        return redirect(url_for('chat.conversation', partner_id=partners[0]['partner_id']))
        
    return render_template('chat.html', partners=partners, active_partner=None, messages=[])

@chat_bp.route('/chat/<int:partner_id>')
@login_required
def conversation(partner_id):
    if partner_id == session['user_id']:
        flash("You cannot chat with yourself.", "error")
        return redirect(url_for('chat.lobby'))
        
    partner = get_user_by_id(partner_id)
    if not partner:
        abort(404, description="Chat partner not found.")
        
    partners = get_active_chat_partners(session['user_id'])
    
    # Add partner to the partners list if not already present
    partner_ids = [p['partner_id'] for p in partners]
    if partner_id not in partner_ids:
        # Check if they are online
        from services.chat_service import online_users
        partners.insert(0, {
            'partner_id': partner['id'],
            'username': partner['username'],
            'role': partner['role'],
            'online': partner['id'] in online_users,
            'unread_count': 0
        })
        
    # Mark messages from this partner as read
    mark_messages_as_read(sender_id=partner_id, receiver_id=session['user_id'])
    
    messages = get_chat_history(session['user_id'], partner_id)
    
    return render_template(
        'chat.html', 
        partners=partners, 
        active_partner=partner, 
        messages=messages
    )
