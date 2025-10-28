from flask import render_template, jsonify
from flask import redirect, url_for, flash, render_template_string, current_app
from persistence import PersistenceLayer
from models import User
from uml_utils import nlp, NLPEngine, DiagramGenerator
import os, time, logging

logger = logging.getLogger(__name__)

def create_project(request, current_user, is_json=False):
    """Create a new project. 
    Args:
        request: Flask request object
        current_user: Current user object
        is_json: If True, return dict for JSON response. If False, use form data.
    Returns:
        dict with project_id for JSON requests, or redirect response for form requests
    """
    project_id = None
    try:
        # Get project name from JSON or form
        if is_json:
            data = request.get_json() or {}
            project_name = data.get('project_name', '').strip()
        else:
            project_name = request.form.get('project_name', '').strip()
        
        logger.info(f"[create_project] project_name='{project_name}', is_json={is_json}")
        
        if not project_name:
            if is_json:
                return {'success': False, 'message': 'Project name is required.'}
            flash('Project name is required.', 'error')
            return redirect(url_for('index'))
        
        # Get user ID
        user_id = None
        if hasattr(current_user, 'id'):
            user_id = current_user.id
            logger.info(f"[create_project] current_user.id={user_id}")
        elif hasattr(current_user, 'get_id'):
            user_id = current_user.get_id()
            logger.info(f"[create_project] current_user.get_id()={user_id}")
        else:
            logger.warning(f"[create_project] current_user has no id attribute: {dir(current_user)}")
        
        logger.info(f"[create_project] Creating project: {project_name}, user_id={user_id}")
        
        with PersistenceLayer() as persistence:
            project_id = persistence.create_project(project_name, user_id)
            logger.info(f"[create_project] persistence.create_project returned: {project_id}")
        
        if project_id:
            logger.info(f"[create_project] SUCCESS: Project created: {project_name}, ID: {project_id}")
            if is_json:
                return {'success': True, 'message': f'Project "{project_name}" created successfully', 'project_id': project_id}
            flash(f'Project "{project_name}" created with ID {project_id}.', 'success')
            return redirect(url_for('project.view_project', project_id=project_id))
        else:
            logger.error(f"[create_project] FAILED: Project creation returned None/0")
            msg = 'Error creating project. Please try again.'
            if is_json:
                return {'success': False, 'message': msg}
            flash(msg, 'error')
            return redirect(url_for('index'))
    
    except Exception as e:
        logger.error(f"[create_project] EXCEPTION: {type(e).__name__}: {e}", exc_info=True)
        if is_json:
            return {'success': False, 'message': f'Error: {type(e).__name__}: {str(e)[:100]}'}
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('index'))

def get_project(request, current_user, project_id, is_json=False):
    """Get project details.
    Args:
        request: Flask request object
        current_user: Current user object
        project_id: Project ID (should already be validated as int in routes)
        is_json: If True, return JSON response
    Returns:
        Rendered template or JSON response
    """
    try:
        with PersistenceLayer() as persistence:
            project = persistence.get_project(project_id)
            if not project:
                msg = f"Project {project_id} not found."
                logger.warning(msg)
                if is_json:
                    return {'success': False, 'message': msg}
                flash("Project not found.")
                return redirect(url_for('index'))
            
            stories_text = persistence.get_stories_as_text(project_id)
            is_owner = current_user.is_authenticated and project.get('UserID') == current_user.id
        
        diagram_type = request.args.get('diagram_type', 'class')
        logger.info(f"[get_project] diagram_type from URL: '{diagram_type}'")
        diagram_path = os.path.join(current_app.config['STATIC_DIR'], f"{diagram_type}_{project_id}.png")
        diagram_url = url_for('static', filename=f"{diagram_type}_{project_id}.png") + f"?t={time.time()}" if os.path.exists(diagram_path) else None
        
        # Always return JSON for API requests
        return jsonify({
            'success': True,
            'ProjectID': project['ProjectID'],
            'ProjectName': project['ProjectName'],
            'UserID': project.get('UserID'),
            'stories_text': stories_text,
            'diagram_url': diagram_url,
            'is_owner': is_owner,
            'diagram_type': diagram_type
        }), 200
    
    except Exception as e:
        logger.error(f"Exception getting project {project_id}: {e}")
        if is_json:
            return {'success': False, 'message': f'Error retrieving project: {str(e)}'}
        flash(f'Error retrieving project: {str(e)}', 'error')
        return redirect(url_for('index'))

def update_project_logic(request, current_user, project_id, is_json=False):
    """Update project with new stories and regenerate diagrams.
    Args:
        request: Flask request object
        current_user: Current user object
        project_id: Project ID (should already be validated as int in routes)
        is_json: If True, return JSON response
    Returns:
        Rendered template or JSON response
    """
    try:
        with PersistenceLayer() as persistence:
            project = persistence.get_project(project_id)
            if not project:
                msg = f"Project {project_id} not found."
                logger.warning(msg)
                if is_json:
                    return {'success': False, 'message': msg}
                flash("Project not found.")
                return redirect(url_for('project.view_project', project_id=project_id))
            
            # Check permission
            if project.get('UserID') and project.get('UserID') != current_user.id:
                msg = "You don't have permission to update this project."
                logger.warning(f"{msg} User: {current_user.id}, Project owner: {project.get('UserID')}")
                if is_json:
                    return {'success': False, 'message': msg}
                flash(msg, 'warning')
                return redirect(url_for('project.view_project', project_id=project_id))
            
            # Get stories and diagram type
            if is_json:
                data = request.get_json() or {}
                stories_text = data.get('user_stories', '').strip()
                diagram_type = data.get('diagram_type', 'class')
                logger.info(f"[update_project_logic] JSON - diagram_type from request: '{diagram_type}'")
            else:
                stories_text = request.form.get('user_stories', '').strip()
                diagram_type = request.form.get('diagram_type', 'class')
                logger.info(f"[update_project_logic] FORM - diagram_type from request: '{diagram_type}'")
                logger.debug(f"[update_project_logic] Form data: {request.form}")
            
            logger.info(f"[update_project_logic] Processing with diagram_type='{diagram_type}'")
            
            if not stories_text:
                msg = "No stories provided. Add some to generate diagram."
                logger.warning(msg)
                if is_json:
                    return {'success': False, 'message': msg}
                flash(msg)
                return redirect(url_for('project.view_project', project_id=project_id))
            
            # Delete model elements FIRST (they reference stories via foreign key)
            logger.info(f"[update_project_logic] Deleting old model elements")
            persistence.delete_model_elements(project_id)
            
            # Now safe to save new stories (this deletes old stories first)
            user_id = current_user.id if hasattr(current_user, 'id') else (current_user.get_id() if hasattr(current_user, 'get_id') else None)
            logger.info(f"[update_project_logic] Saving stories for project {project_id}")
            persistence.save_stories_from_text(project_id, stories_text, user_id)
            
            logger.info(f"[update_project_logic] Retrieving saved stories")
            stories_list = persistence.get_stories_list(project_id)
            logger.info(f"[update_project_logic] Retrieved {len(stories_list)} stories")
            
            if not stories_list:
                msg = "Failed to retrieve stories. Check input and try again."
                logger.warning(msg)
                if is_json:
                    return {'success': False, 'message': msg}
                flash(msg)
                return redirect(url_for('project.view_project', project_id=project_id))
            
            # Log first story for debugging
            if stories_list:
                logger.debug(f"[update_project_logic] First story: {stories_list[0]}")
            
            # Generate diagram
            logger.info(f"[update_project_logic] Creating NLP engine and generator")
            nlp_engine = NLPEngine(nlp)
            generator = DiagramGenerator()
            
            logger.info(f"[update_project_logic] Extracting diagram model with type '{diagram_type}'")
            new_model_elements = nlp_engine.extract_diagram_model(stories_list, diagram_type)
            logger.info(f"[update_project_logic] Extracted {len(new_model_elements)} model elements")
            
            logger.info(f"[update_project_logic] Saving model elements")
            persistence.save_model_elements(project_id, new_model_elements)
            
            logger.info(f"[update_project_logic] Generating diagram")
            generator.generate_diagram(project_id, diagram_type, new_model_elements)
            logger.info(f"[update_project_logic] Diagram generation complete")
        
        msg = "Diagram updated successfully!"
        logger.info(f"{msg} Project: {project_id}, Diagram type: {diagram_type}")
        
        if is_json:
            return {'success': True, 'message': msg}
        
        flash(msg, 'success')
        redirect_url = url_for('project.view_project', project_id=project_id, diagram_type=diagram_type)
        logger.info(f"[update_project_logic] Redirecting to: {redirect_url}")
        return redirect(redirect_url)
    
    except Exception as e:
        logger.error(f"Exception updating project {project_id}: {e}")
        if is_json:
            return {'success': False, 'message': f'Error updating project: {str(e)}'}
        flash(f'Error updating project: {str(e)}', 'error')
        return redirect(url_for('project.view_project', project_id=project_id))
