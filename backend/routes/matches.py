from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort
from database import (
    get_lost_item, get_found_item, get_matches_for_lost_item, update_match_status
)
from utils.security import login_required, verify_csrf_token
from services.secure_contact import (
    create_contact_request, approve_contact_request, reject_contact_request,
    check_contact_permission, get_contact_request_state, get_user_contact_requests
)

matches_bp = Blueprint('matches', __name__)

@matches_bp.route('/matches/<int:lost_id>')
@login_required
def match_results(lost_id):
    lost_item = get_lost_item(lost_id)
    if not lost_item:
        flash('Lost item not found.', 'error')
        return redirect(url_for('search'))
        
    # Verify owner of lost item OR admin
    if lost_item['user_id'] != session['user_id'] and session['role'] != 'admin':
        flash('Unauthorized access.', 'error')
        return redirect(url_for('search'))
        
    raw_matches = get_matches_for_lost_item(lost_id)
    
    # Process permissions and breakdown details
    matches = []
    for m in raw_matches:
        # Determine if we have permission to view contact info
        has_perm = check_contact_permission(
            requester_id=session['user_id'],
            owner_id=m['user_id'],
            item_type='found',
            item_id=m['id']
        )
        
        # Get contact request state
        req_state = get_contact_request_state(
            item_type='found',
            item_id=m['id'],
            requester_id=session['user_id'],
            owner_id=m['user_id']
        )
        
        m_dict = dict(m)
        m_dict['has_permission'] = has_perm
        m_dict['request_status'] = req_state['status'] if req_state else None
        m_dict['request_id'] = req_state['id'] if req_state else None
        
        # We can also compute match breakdown details dynamically or load them
        from matching import compute_overall_match
        breakdown = compute_overall_match(lost_item, m)
        m_dict['breakdown'] = breakdown
        
        matches.append(m_dict)
        
    return render_template('matches.html', lost_item=lost_item, matches=matches)

@matches_bp.route('/matches/request-contact/<string:item_type>/<int:item_id>/<int:owner_id>', methods=['POST'])
@login_required
def request_contact(item_type, item_id, owner_id):
    verify_csrf_token()
    
    # Create request
    req_id = create_contact_request(
        item_type=item_type,
        item_id=item_id,
        requester_id=session['user_id'],
        owner_id=owner_id
    )
    
    if req_id:
        flash('Contact disclosure request submitted. The other party has been notified.', 'success')
    else:
        flash('Failed to submit request. You cannot request contact with yourself.', 'error')
        
    if item_type == 'lost':
        return redirect(url_for('search'))
    else:
        # Go back to matches page for this lost item if we came from it
        lost_id = request.form.get('lost_id')
        if lost_id:
            return redirect(url_for('matches.match_results', lost_id=lost_id))
        return redirect(url_for('search'))

@matches_bp.route('/matches/approve-contact/<int:request_id>', methods=['POST'])
@login_required
def approve_contact(request_id):
    verify_csrf_token()
    
    if approve_contact_request(request_id, session['user_id']):
        flash('Contact request approved. Your contact details are now shared.', 'success')
    else:
        flash('Failed to approve request. Unauthorized.', 'error')
        
    return redirect(url_for('matches.dashboard_requests'))

@matches_bp.route('/matches/reject-contact/<int:request_id>', methods=['POST'])
@login_required
def reject_contact(request_id):
    verify_csrf_token()
    
    if reject_contact_request(request_id, session['user_id']):
        flash('Contact request declined.', 'info')
    else:
        flash('Failed to decline request. Unauthorized.', 'error')
        
    return redirect(url_for('matches.dashboard_requests'))

@matches_bp.route('/dashboard/requests')
@login_required
def dashboard_requests():
    """
    Renders incoming and outgoing contact approval requests for the user.
    """
    requests = get_user_contact_requests(session['user_id'])
    
    # Enrich requests with item names
    conn = None
    try:
        from database import get_db_connection
        conn = get_db_connection()
        
        enriched_incoming = []
        for r in requests['incoming']:
            table = "lost_items" if r['item_type'] == 'lost' else "found_items"
            item = conn.execute(f"SELECT item_name FROM {table} WHERE id = ?", (r['item_id'],)).fetchone()
            r['item_name'] = item['item_name'] if item else 'Unknown Item'
            enriched_incoming.append(r)
            
        enriched_outgoing = []
        for r in requests['outgoing']:
            table = "lost_items" if r['item_type'] == 'lost' else "found_items"
            item = conn.execute(f"SELECT item_name FROM {table} WHERE id = ?", (r['item_id'],)).fetchone()
            r['item_name'] = item['item_name'] if item else 'Unknown Item'
            enriched_outgoing.append(r)
            
        requests['incoming'] = enriched_incoming
        requests['outgoing'] = enriched_outgoing
    except Exception as e:
        print(f"Error enriching requests: {e}")
    finally:
        if conn:
            conn.close()
            
    return render_template('matches.html', show_requests_only=True, requests=requests)
