from flask import Blueprint, request, redirect, url_for, flash, render_template_string, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from .authcontroller import register_user, login_user_controller
import logging

# Configure logging
logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/register', methods=['POST'])
def register():
    logger.info(f"Register request received. Content-Type: {request.content_type}")
    
    if request.is_json:
        data = request.get_json()
        logger.info(f"JSON payload received: {data}")
        username = data.get('username', '').strip()
        password = data.get('password', '')
        confirm_password = data.get('confirm_password', '')
    else:
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        logger.info(f"Form payload received - Username: {username}")

    logger.info(f"Validation: username='{username}', password_len={len(password)}, confirm={password == confirm_password}")
    
    if not username or not password or password != confirm_password or len(password) < 6:
        msg = 'Invalid registration details. Ensure passwords match and are at least 6 characters.'
        logger.warning(f"Registration validation failed: {msg}")
        if request.is_json:
            return jsonify({'success': False, 'message': msg}), 400
        flash(msg, 'error')
        return redirect(url_for('index'))

    logger.info(f"Attempting to register user: {username}")
    result = register_user(username, password)
    logger.info(f"Registration result: success={result['success']}, message={result['message']}")
    
    if result['success']:
        logger.info(f"User registered successfully: {username}, user_id={result['user'].get_id()}")
        login_user(result['user'])
        logger.info(f"User logged in after registration: {username}")
        msg = 'Registration successful! You are now logged in.'
        if request.is_json:
            return jsonify({'success': True, 'message': msg, 'user_id': result['user'].get_id()}), 201
        flash(msg, 'success')
    else:
        logger.warning(f"Registration failed: {result['message']}")
        if request.is_json:
            return jsonify({'success': False, 'message': result['message']}), 400
        flash(result['message'], 'error')
    return redirect(url_for('index')) if not request.is_json else None

@auth_bp.route('/login', methods=['POST'])
def login():
    logger.info(f"Login request received. Content-Type: {request.content_type}")
    logger.info(f"Request data: {request.data}")
    
    if request.is_json:
        data = request.get_json()
        logger.info(f"JSON payload received: {data}")
        username = data.get('username', '').strip()
        password = data.get('password', '')
    else:
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        logger.info(f"Form payload received - Username: {username}")
    
    logger.info(f"Login attempt for username: '{username}', password_len: {len(password)}")
    
    if not username or not password:
        msg = 'Please enter both username and password.'
        logger.warning(f"Login validation failed: {msg}")
        if request.is_json:
            return jsonify({'success': False, 'message': msg}), 400
        flash(msg, 'error')
        return redirect(url_for('index'))
    
    logger.info(f"Authenticating user: {username}")
    result = login_user_controller(username, password)
    logger.info(f"Authentication result: success={result['success']}, message={result['message']}")
    
    if result['success']:
        login_user(result['user'])
        logger.info(f"User logged in successfully: {username}, user_id={result['user'].get_id()}")
        msg = 'Login successful!'
        if request.is_json:
            return jsonify({'success': True, 'message': msg, 'user_id': result['user'].get_id()}), 200
        flash(msg, 'success')
    else:
        logger.warning(f"Login failed for {username}: {result['message']}")
        if request.is_json:
            return jsonify({'success': False, 'message': result['message']}), 401
        flash(result['message'], 'error')
    return redirect(url_for('index')) if not request.is_json else None

@auth_bp.route('/logout')
@login_required
def logout():
    logger.info(f"Logout request from user: {current_user.username}")
    logout_user()
    logger.info("User logged out successfully")
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))
