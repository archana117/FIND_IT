from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort
from database import (
    get_all_users, get_all_lost_items, get_all_found_items, get_all_matches, get_dashboard_stats,
    delete_user, delete_lost_item, delete_found_item, delete_match, get_db_connection
)
from utils.security import admin_required, login_required, verify_csrf_token
from services.fraud_detector import block_user, unblock_user, get_flagged_items

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin')
@login_required
@admin_required
def dashboard():
    users = get_all_users()
    lost_items = get_all_lost_items()
    found_items = get_all_found_items()
    matches = get_all_matches()
    stats = get_dashboard_stats()
    flagged = get_flagged_items()
    
    return render_template(
        'admin.html', 
        users=users, 
        lost_items=lost_items, 
        found_items=found_items, 
        matches=matches, 
        stats=stats,
        flagged_items=flagged
    )

@admin_bp.route('/admin/delete-user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user_route(user_id):
    verify_csrf_token()
    delete_user(user_id)
    flash('User account deleted successfully.', 'success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/admin/block-user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def block_user_route(user_id):
    verify_csrf_token()
    if block_user(user_id):
        flash('User account blocked successfully.', 'success')
    else:
        flash('Failed to block user.', 'error')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/admin/unblock-user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def unblock_user_route(user_id):
    verify_csrf_token()
    if unblock_user(user_id):
        flash('User account unblocked successfully.', 'success')
    else:
        flash('Failed to unblock user.', 'error')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/admin/delete-item/<string:item_type>/<int:item_id>', methods=['POST'])
@login_required
@admin_required
def delete_item_route(item_type, item_id):
    verify_csrf_token()
    if item_type == 'lost':
        delete_lost_item(item_id)
    elif item_type == 'found':
        delete_found_item(item_id)
        
    flash(f'{item_type.capitalize()} item report deleted successfully.', 'success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/admin/delete-match/<int:match_id>', methods=['POST'])
@login_required
@admin_required
def delete_match_route(match_id):
    verify_csrf_token()
    delete_match(match_id)
    flash('Match link deleted successfully.', 'success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/admin/dismiss-report/<string:item_type>/<int:item_id>', methods=['POST'])
@login_required
@admin_required
def dismiss_report(item_type, item_id):
    verify_csrf_token()
    if item_type not in ['lost', 'found']:
        abort(400)
        
    table = "lost_items" if item_type == 'lost' else "found_items"
    
    conn = get_db_connection()
    try:
        conn.execute(f'''
            UPDATE {table} 
            SET report_count = 0, is_flagged_fake = 0 
            WHERE id = ?
        ''', (item_id,))
        conn.commit()
        flash('Reports dismissed and listing approved.', 'success')
    except Exception as e:
        print(f"Error dismissing report: {e}")
        flash('Failed to dismiss reports.', 'error')
    finally:
        conn.close()
        
    return redirect(url_for('admin.dashboard'))
