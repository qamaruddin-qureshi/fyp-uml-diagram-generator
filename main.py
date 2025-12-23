from flask import Flask, request, jsonify, send_from_directory, render_template
from flask_cors import CORS
from flask_login import LoginManager, current_user, login_user, logout_user, login_required
from sqlalchemy import text, create_engine
from sqlalchemy.exc import OperationalError
import os
import logging
import spacy
from models import Base, User, Project
from auth.authroutes import auth_bp
from project.projectroutes import project_bp
from persistence import PersistenceLayer, logger, engine
from uml_extractors import (
    ClassDiagramExtractor,
    UseCaseDiagramExtractor,
    SequenceDiagramExtractor,
    ActivityDiagramExtractor,
    ComponentDiagramExtractor,
    DeploymentDiagramExtractor
)
from uml_generator import DiagramGenerator



app = Flask(__name__)
app.secret_key = "your-very-secret-key-12345"
CORS(app, 
     resources={r"/*": {
         "origins": ["http://localhost:3000"],
         "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
         "allow_headers": ["Content-Type", "Authorization"],
         "supports_credentials": True,
         "max_age": 3600
     }}
)

# Configure static directory
app.config['STATIC_DIR'] = os.path.join(os.path.dirname(__file__), 'static')
os.makedirs(app.config['STATIC_DIR'], exist_ok=True)

# Configure logging - this must be done EARLY
import sys
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout,
    force=True
)
logger.setLevel(logging.DEBUG)
logging.getLogger('werkzeug').setLevel(logging.DEBUG)
logging.getLogger('flask_login').setLevel(logging.DEBUG)
login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    from models import User
    with PersistenceLayer() as persistence:
        result = persistence.connection.execute(
            text("SELECT userid, username, passwordhash FROM users WHERE userid = :uid"), {"uid": user_id}
        ).mappings().first()
        if result:
            return User(result['userid'], result['username'], result['passwordhash'])
        return None

app.register_blueprint(auth_bp)
app.register_blueprint(project_bp)

# Sync models with database (don't hard-crash if DB isn't reachable)
try:
    Base.metadata.create_all(engine)
except OperationalError as e:
    safe_url = str(engine.url).replace(engine.url.password or "", "***") if engine.url.password else str(engine.url)
    logger.error(
        "Database connection failed during startup; skipping Base.metadata.create_all(). "
        f"Check DB_* env vars and Postgres container. url={safe_url}. error={e}"
    )


# Directories and Model
PUML_DIR = "generated_puml"
STATIC_DIR = "static"
BEHAVIORAL_MODEL_PATH = "./behavioral_uml_model/model-best"
ARCHITECTURE_MODEL_PATH = "./architecture_uml_model/model-best"

# Load Standard Model (Syntax/Parsing)
try:
    nlp_standard = spacy.load("en_core_web_lg")
    logger.info("Loaded en_core_web_lg.")
except Exception as e:
    logger.warning(f"Failed to load en_core_web_lg: {e}. Using blank 'en' model.")
    nlp_standard = spacy.blank("en")

# Load Behavioral NER Model (for Class, UseCase, Sequence, Activity diagrams)
nlp_behavioral = None
if not os.path.exists(BEHAVIORAL_MODEL_PATH):
    logger.warning(f"Behavioral model not found at {BEHAVIORAL_MODEL_PATH}. Run train_behavioral_model.py first.")
else:
    try:
        nlp_behavioral = spacy.load(BEHAVIORAL_MODEL_PATH)
        logger.info("Behavioral NER model loaded successfully.")
    except Exception as e:
        logger.error(f"Behavioral model load error: {e}.")

# Load Architecture NER Model (for Component, Deployment diagrams)
nlp_architecture = None
if not os.path.exists(ARCHITECTURE_MODEL_PATH):
    logger.warning(f"Architecture model not found at {ARCHITECTURE_MODEL_PATH}. Will skip architectural diagram generation until trained.")
else:
    try:
        nlp_architecture = spacy.load(ARCHITECTURE_MODEL_PATH)
        logger.info("Architecture NER model loaded successfully.")
    except Exception as e:
        logger.error(f"Architecture model load error: {e}.")

if not os.path.exists(STATIC_DIR): os.makedirs(STATIC_DIR)
if not os.path.exists(PUML_DIR): os.makedirs(PUML_DIR)

from flask import render_template


# --- Extractor Instances ---
# Behavioral pipeline: Pass standard NLP for syntax and behavioral NER for entities
class_diagram_extractor = ClassDiagramExtractor(nlp_standard, ner_model=nlp_behavioral)
use_case_extractor = UseCaseDiagramExtractor(nlp_standard, ner_model=nlp_behavioral)
sequence_extractor = SequenceDiagramExtractor(nlp_standard, ner_model=nlp_behavioral)
activity_extractor = ActivityDiagramExtractor(nlp_standard, ner_model=nlp_behavioral)

# Architecture pipeline: Initialize with architecture NER model
if nlp_architecture:
    component_diagram_extractor = ComponentDiagramExtractor(nlp_standard, ner_model=nlp_architecture)
    deployment_diagram_extractor = DeploymentDiagramExtractor(nlp_standard, ner_model=nlp_architecture)
    logger.info("Architecture extractors initialized with trained NER model")
else:
    # Fallback: Use pattern-based extraction only (no NER model)
    component_diagram_extractor = ComponentDiagramExtractor(nlp_standard, ner_model=None)
    deployment_diagram_extractor = DeploymentDiagramExtractor(nlp_standard, ner_model=None)
    logger.warning("Architecture extractors initialized WITHOUT NER model (pattern-based only)")

diagram_generator = DiagramGenerator()


# Routes
@app.route("/")
def index():
    """API health check endpoint"""
    return jsonify({
        'success': True,
        'message': 'UML Diagram Generator API',
        'version': '1.0',
        'endpoints': {
            'auth': '/auth/register, /auth/login, /auth/logout',
            'projects': '/projects, /project/new, /project/<id>, /project/<id>/update',
            'static': '/static/<filename>'
        }
    }), 200

@app.route("/static/<path:filename>")
def serve_static(filename):
    """Serve static files (generated diagrams)."""
    logger.debug(f"Serving static file: {filename}")
    return send_from_directory(app.config['STATIC_DIR'], filename)

# Main
if __name__ == "__main__":
    from waitress import serve
    print(f"Starting Production Server (Waitress) on http://localhost:5000...")
    serve(app, host='localhost', port=5000)