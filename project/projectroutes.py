from flask import Blueprint, request, redirect, url_for, flash, render_template_string, send_from_directory, current_app, jsonify
from flask_login import login_required, current_user
from .projectcontroller import (
    create_project,
    get_project,
    update_project_logic,
)
import logging

# Configure logging
logger = logging.getLogger(__name__)

project_bp = Blueprint('project', __name__)

@project_bp.route('/projects', methods=['GET'])
@login_required
def get_all_projects():
    """Retrieve all projects for the current user."""
    logger.info(f"Fetching all projects for user: {current_user.id}")
    
    try:
        from persistence import PersistenceLayer
        with PersistenceLayer() as persistence:
            projects = persistence.get_all_projects()
            # Filter projects for the current user
            user_projects = [p for p in projects if p['UserID'] == current_user.id]
            logger.info(f"Retrieved {len(user_projects)} projects for user {current_user.id}")
            return jsonify({'success': True, 'data': user_projects}), 200
    except Exception as e:
        logger.error(f"Error retrieving projects: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'Error retrieving projects: {str(e)}'}), 500

@project_bp.route('/project/new', methods=['POST'])
@login_required
def add_project():
    """Create a new project. Supports both JSON and form data."""
    logger.info(f"Project creation request received. Content-Type: {request.content_type}")
    
    try:
        if request.is_json:
            data = request.get_json()
            logger.info(f"JSON payload received: {data}")
            project_name = data.get('project_name', '').strip()
        else:
            project_name = request.form.get('project_name', '').strip()
            logger.info(f"Form payload received - Project name: {project_name}")
        
        if not project_name:
            msg = 'Project name is required.'
            logger.warning(f"Project creation validation failed: {msg}")
            if request.is_json:
                return jsonify({'success': False, 'message': msg}), 400
            flash(msg, 'error')
            return redirect(url_for('index'))
        
        logger.info(f"Attempting to create project: {project_name}")
        result = create_project(request, current_user, is_json=request.is_json)
        
        if request.is_json:
            if isinstance(result, dict):
                if result.get('success'):
                    logger.info(f"Project created successfully via JSON: {result}")
                    return jsonify({'success': True, 'message': result.get('message'), 'project_id': result.get('project_id')}), 201
                else:
                    logger.warning(f"Project creation failed: {result}")
                    return jsonify({'success': False, 'message': result.get('message', 'Error creating project')}), 400
            else:
                logger.error(f"Unexpected return type from create_project: {type(result)}")
                return jsonify({'success': False, 'message': 'Error creating project'}), 500
        return result
    
    except Exception as e:
        logger.error(f"Exception in add_project route: {e}", exc_info=True)
        if request.is_json:
            return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('index'))

@project_bp.route('/project/<project_id>')
@login_required
def view_project(project_id):
    """Retrieve and display a project."""
    logger.info(f"Project view request received for project_id: {project_id}")
    
    # Validate UUID format (must be valid UUID v4 format)
    import re
    uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
    if not project_id or not re.match(uuid_pattern, project_id, re.IGNORECASE):
        msg = 'Invalid project ID format.'
        logger.warning(f"Invalid project ID: {project_id}")
        return jsonify({'success': False, 'message': msg}), 400
    
    logger.info(f"Retrieving project with ID: {project_id}")
    result = get_project(request, current_user, project_id, is_json=True)
    
    # Result is already a tuple (response, status_code) from the controller
    return result

@project_bp.route('/project/<project_id>/update', methods=['POST'])
@login_required
def update_project(project_id):
    """Update an existing project with new stories and regenerate diagrams."""
    logger.info(f"Project update request received for project_id: {project_id}")
    logger.info(f"Content-Type: {request.content_type}")
    
    # Validate UUID format (must be valid UUID v4 format)
    import re
    uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
    if not project_id or not re.match(uuid_pattern, project_id, re.IGNORECASE):
        msg = 'Invalid project ID format.'
        logger.warning(f"Invalid project ID: {project_id}")
        if request.is_json:
            return jsonify({'success': False, 'message': msg}), 400
        flash(msg, 'error')
        return redirect(url_for('project.view_project', project_id=project_id))
    
    if request.is_json:
        data = request.get_json()
        logger.info(f"JSON payload received: {data}")
    else:
        logger.info(f"Form payload received")
    
    logger.info(f"Attempting to update project {project_id}")
    result = update_project_logic(request, current_user, project_id, is_json=request.is_json)
    
    if request.is_json:
        if isinstance(result, dict):
            if result.get('success'):
                return jsonify({'success': True, 'message': result.get('message')}), 200
            else:
                return jsonify({'success': False, 'message': result.get('message')}), 400
        return jsonify({'success': False, 'message': 'Error updating project'}), 500
    return result

@project_bp.route('/static/<path:filename>')
def send_static_file(filename):
    """Serve static files (CSS, images, etc.)."""
    logger.debug(f"Serving static file: {filename}")
    return send_from_directory(current_app.config['STATIC_DIR'], filename)
