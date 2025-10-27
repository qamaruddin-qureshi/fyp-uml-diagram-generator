import os
import subprocess
import json
import pyodbc
import spacy
import re
import time
import logging
from flask import Flask, render_template_string, request, redirect, url_for, flash, send_from_directory
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image, ImageDraw  # For placeholder images

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.urandom(24)  # Secure random key for sessions

# Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, user_id):
        self.id = user_id

@login_manager.user_loader
def load_user(user_id):
    with PersistenceLayer() as persistence:
        cursor = persistence.cursor
        cursor.execute("SELECT UserID FROM Users WHERE UserID = ?", (user_id,))
        user = cursor.fetchone()
        return User(user[0]) if user else None

# Configuration
DB_CONFIG = {
    'driver': '{ODBC Driver 17 for SQL Server}',
    'server': 'DESKTOP-56AJ0CQ',
    'database': 'UML_Project_DB',
    'trusted_connection': 'yes'
}

DB_CONN_STR = (
    f"DRIVER={DB_CONFIG['driver']};"
    f"SERVER={DB_CONFIG['server']};"
    f"DATABASE={DB_CONFIG['database']};"
    f"Trusted_Connection={DB_CONFIG['trusted_connection']};"
)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Directories and Model
PUML_DIR = "generated_puml"
STATIC_DIR = "static"
MODEL_PATH = "./my_uml_model/model-best"

if not os.path.exists(MODEL_PATH):
    logger.warning(f"Model not found at {MODEL_PATH}. Run train_model.py first. Using blank model.")
    nlp = spacy.blank("en")
else:
    try:
        nlp = spacy.load(MODEL_PATH)
        logger.info("Model loaded successfully.")
    except Exception as e:
        logger.error(f"Model load error: {e}. Using blank model as fallback.")
        nlp = spacy.blank("en")

if not os.path.exists(STATIC_DIR): os.makedirs(STATIC_DIR)
if not os.path.exists(PUML_DIR): os.makedirs(PUML_DIR)

# Templates
HTML_DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Project Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
    <div class="container mt-5">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h1>Project Dashboard</h1>
            <div>
                {% if current_user.is_authenticated %}
                    <span class="badge bg-success me-2">Logged in as: {{ current_user.id }}</span>
                    <a href="{{ url_for('logout') }}" class="btn btn-outline-danger btn-sm">Logout</a>
                {% else %}
                    <button class="btn btn-primary btn-sm" data-bs-toggle="modal" data-bs-target="#loginModal">Login</button>
                    <button class="btn btn-success btn-sm" data-bs-toggle="modal" data-bs-target="#registerModal">Register</button>
                {% endif %}
            </div>
        </div>
        
        {% with messages = get_flashed_messages() %}
            {% if messages %}
                {% for message in messages %}
                    <div class="alert alert-warning alert-dismissible fade show" role="alert">
                        {{ message }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        {% if not current_user.is_authenticated %}
        <div class="alert alert-info">
            <strong>Guest Mode:</strong> You can create new projects, but login to update or view owned projects.
        </div>
        {% endif %}
        
        <div class="card mb-4">
            <div class="card-body">
                <h2>Your Projects</h2>
                {% if projects %}
                    <ul class="list-group">
                        {% for project in projects %}
                            {% if not project['UserID'] or current_user.is_authenticated %}
                            <li class="list-group-item">
                                <a href="{{ url_for('view_project', project_id=project['ProjectID']) }}">
                                    {{ project['ProjectName'] }} (ID: {{ project['ProjectID'] }}) {% if not current_user.is_authenticated and project['UserID'] %} (Owned by another user){% endif %}
                                </a>
                            </li>
                            {% endif %}
                        {% endfor %}
                    </ul>
                {% else %}
                    <p>No projects found. Create one below.</p>
                {% endif %}
            </div>
        </div>
        <div class="card">
            <div class="card-body">
                <h2>Create New Project</h2>
                <form method="POST" action="{{ url_for('add_project') }}">
                    <div class="mb-3">
                        <input type="text" class="form-control" name="project_name" placeholder="Enter new project name" required>
                    </div>
                    <button type="submit" class="btn btn-primary">Create Project</button>
                </form>
            </div>
        </div>
    </div>
    
    <div class="modal fade" id="loginModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Login</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <form method="POST" action="{{ url_for('login') }}">
                        <div class="mb-3">
                            <label class="form-label">Username</label>
                            <input type="text" class="form-control" name="username" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Password</label>
                            <input type="password" class="form-control" name="password" required>
                        </div>
                        <button type="submit" class="btn btn-primary">Login</button>
                    </form>
                </div>
            </div>
        </div>
    </div>
    
    <div class="modal fade" id="registerModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Register</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <form method="POST" action="{{ url_for('register') }}">
                        <div class="mb-3">
                            <label class="form-label">Username</label>
                            <input type="text" class="form-control" name="username" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Password</label>
                            <input type="password" class="form-control" name="password" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Confirm Password</label>
                            <input type="password" class="form-control" name="confirm_password" required>
                        </div>
                        <button type="submit" class="btn btn-success">Register</button>
                    </form>
                </div>
            </div>
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>UML Generator</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
    <div class="container mt-5">
        <a href="{{ url_for('index') }}" class="btn btn-secondary mb-3">&laquo; Back to Dashboard</a>
        <h1>Automated UML Generator</h1>
        <h2>Project: {{ project['ProjectName'] }} (ID: {{ project['ProjectID'] }})</h2>
        
        {% with messages = get_flashed_messages() %}
            {% if messages %}
                <div class="alert alert-danger">
                    {{ messages[0] }}
                </div>
            {% endif %}
        {% endwith %}
        
        {% if not current_user.is_authenticated and is_owner %}
        <div class="alert alert-warning">
            <strong>⚠️ Guest User Restriction:</strong> Login to update this project. Guests can only view or create new projects.
        </div>
        {% endif %}
        
        <div class="row">
            <div class="col-md-6">
                <div class="card">
                    <div class="card-body">
                        <h3>User Stories</h3>
                        {% if current_user.is_authenticated or not is_owner %}
                        <form method="POST" action="{{ url_for('update_project', project_id=project['ProjectID']) }}">
                            <textarea name="user_stories" class="form-control" rows="10" placeholder="Enter user stories, one per line..." {{ 'disabled' if (not current_user.is_authenticated and is_owner) else '' }}>{{ stories_text }}</textarea>
                            <select name="diagram_type" class="form-select mt-3" {{ 'disabled' if (not current_user.is_authenticated and is_owner) else '' }}>
                                <option value="class">Class Diagram</option>
                                <option value="use_case">Use Case Diagram</option>
                                <option value="sequence">Sequence Diagram</option>
                                <option value="activity">Activity Diagram</option>
                            </select>
                            <button type="submit" class="btn btn-primary mt-3" {{ 'disabled' if (not current_user.is_authenticated and is_owner) else '' }}>Generate / Update Diagram</button>
                        </form>
                        {% else %}
                        <p class="text-warning">Login required to update this project.</p>
                        <textarea class="form-control" rows="10" readonly>{{ stories_text }}</textarea>
                        {% endif %}
                    </div>
                </div>
            </div>
            
            <div class="col-md-6">
                <div class="card">
                    <div class="card-body">
                        <h3>Generated Diagram</h3>
                        {% if diagram_url %}
                            <img src="{{ diagram_url }}" class="img-fluid border" alt="Generated UML Diagram">
                        {% else %}
                            <p class="text-muted">No diagram generated yet. Enter stories and click 'Generate'.</p>
                        {% endif %}
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

# Persistence Layer
class PersistenceLayer:
    def __init__(self):
        self.conn = pyodbc.connect(DB_CONN_STR)
        self.cursor = self.conn.cursor()
        logger.info("DB connection successful.")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def close(self):
        try:
            self.cursor.close()
            self.conn.close()
        except Exception as e:
            logger.warning(f"DB close error: {e}. Ignoring.")

    def get_all_projects(self):
        try:
            self.cursor.execute("SELECT ProjectID, ProjectName, UserID FROM Projects")
            columns = [col[0] for col in self.cursor.description]
            return [dict(zip(columns, row)) for row in self.cursor.fetchall()]
        except pyodbc.Error as e:
            logger.error(f"Get projects error: {e}")
            return []

    def get_project(self, project_id):
        try:
            self.cursor.execute("SELECT ProjectID, ProjectName, UserID FROM Projects WHERE ProjectID = ?", project_id)
            columns = [col[0] for col in self.cursor.description]
            row = self.cursor.fetchone()
            return dict(zip(columns, row)) if row else None
        except pyodbc.Error as e:
            logger.error(f"Get project error: {e}")
            return None

    def create_project(self, project_name, user_id=None):
        try:
            self.cursor.execute("INSERT INTO Projects (ProjectName, UserID) OUTPUT INSERTED.ProjectID VALUES (?, ?)", (project_name, user_id))
            project_id = self.cursor.fetchone()[0]
            self.conn.commit()
            return project_id
        except pyodbc.Error as e:
            self.conn.rollback()
            logger.error(f"Create project error: {e}")
            return None

    def get_stories_as_text(self, project_id):
        try:
            self.cursor.execute("SELECT StoryText FROM UserStories WHERE ProjectID = ? ORDER BY StoryID", project_id)
            return "\n".join(row[0] for row in self.cursor.fetchall())
        except pyodbc.Error as e:
            logger.error(f"Get stories text error: {e}")
            return ""

    def get_stories_list(self, project_id):
        try:
            self.cursor.execute("SELECT StoryID, ProjectID, StoryText FROM UserStories WHERE ProjectID = ? ORDER BY StoryID", project_id)
            columns = [col[0] for col in self.cursor.description]
            return [dict(zip(columns, row)) for row in self.cursor.fetchall()]
        except pyodbc.Error as e:
            logger.error(f"Get stories list error: {e}")
            return []

    def save_stories_from_text(self, project_id, stories_text):
        try:
            self.cursor.execute("DELETE FROM UserStories WHERE ProjectID = ?", project_id)
            stories = [story.strip() for story in stories_text.split("\n") if story.strip()]
            for story_text in stories:
                self.cursor.execute("INSERT INTO UserStories (ProjectID, StoryText) VALUES (?, ?)", (project_id, story_text))
            self.conn.commit()
        except pyodbc.Error as e:
            self.conn.rollback()
            logger.error(f"Save stories error: {e}")

    def delete_model_elements(self, project_id):
        try:
            self.cursor.execute("DELETE FROM ModelElements WHERE ProjectID = ?", project_id)
            self.conn.commit()
        except pyodbc.Error as e:
            self.conn.rollback()
            logger.error(f"Delete elements error: {e}")

    def save_model_elements(self, project_id, elements):
        try:
            for el in elements:
                source_id = el.get('source_id')
                self.cursor.execute(
                    "INSERT INTO ModelElements (ProjectID, ElementType, ElementData, SourceStoryID) VALUES (?, ?, ?, ?)",
                    project_id, el['type'], json.dumps(el['data']), source_id
                )
            self.conn.commit()
        except pyodbc.Error as e:
            self.conn.rollback()
            logger.error(f"Save elements error: {e}")

    def get_model_elements(self, project_id):
        try:
            self.cursor.execute("SELECT ElementType, ElementData, SourceStoryID FROM ModelElements WHERE ProjectID = ?", project_id)
            return [{'ElementType': row[0], 'ElementData': json.loads(row[1]), 'SourceStoryID': row[2]} for row in self.cursor.fetchall()]
        except pyodbc.Error as e:
            logger.error(f"Get elements error: {e}")
            return []

    def create_user(self, username, password_hash):
        try:
            self.cursor.execute("SELECT UserID FROM Users WHERE Username = ?", username)
            if self.cursor.fetchone():
                return None
            self.cursor.execute("INSERT INTO Users (Username, PasswordHash) VALUES (?, ?)", username, password_hash)
            self.conn.commit()
            self.cursor.execute("SELECT UserID FROM Users WHERE Username = ?", username)
            user_id = self.cursor.fetchone()[0]
            return user_id
        except pyodbc.Error as e:
            self.conn.rollback()
            logger.error(f"Create user error: {e}")
            return None

    def get_user_by_username(self, username):
        try:
            self.cursor.execute("SELECT UserID, Username, PasswordHash FROM Users WHERE Username = ?", username)
            row = self.cursor.fetchone()
            return {'UserID': row[0], 'Username': row[1], 'PasswordHash': row[2]} if row else None
        except pyodbc.Error as e:
            logger.error(f"Get user error: {e}")
            return None

# NLP Engine
class NLPEngine:
    def __init__(self, nlp_model):
        self.nlp = nlp_model
        self.model_elements = []
        self.found_classes = {}
        self.found_relationships = set()
        self.attribute_patterns = ["name", "address", "date", "id", "email", "type", "status", "number", "code", "password", "username", "price", "description", "quantity", "totalamount", "orderdate", "shippingaddress"]

    def _normalize_name(self, name):
        return re.sub(r'([a-z])([A-Z])', r'\1 \2', name).title().replace(" ", "")

    def _add_class(self, name, stereotype=None, source_id=None):
        name = self._normalize_name(name)
        if name not in self.found_classes:
            self.found_classes[name] = {'attributes': [], 'methods': [], 'stereotype': stereotype}
            self.model_elements.append({
                'type': 'Class',
                'data': {'name': name, 'attributes': [], 'methods': [], 'stereotype': stereotype},
                'source_id': source_id
            })

    def _add_attribute(self, class_name, attr_name, source_id):
        class_name = self._normalize_name(class_name)
        attr_name = attr_name.lower()
        if class_name in self.found_classes and attr_name not in self.found_classes[class_name]['attributes']:
            self.found_classes[class_name]['attributes'].append(attr_name)
            for el in self.model_elements:
                if el['type'] == 'Class' and el['data']['name'] == class_name:
                    el['data']['attributes'] = self.found_classes[class_name]['attributes']

    def _add_method(self, class_name, method_name, source_id):
        class_name = self._normalize_name(class_name)
        method_name = method_name.lower()
        if class_name in self.found_classes and method_name not in self.found_classes[class_name]['methods']:
            self.found_classes[class_name]['methods'].append(method_name)
            for el in self.model_elements:
                if el['type'] == 'Class' and el['data']['name'] == class_name:
                    el['data']['methods'] = self.found_classes[class_name]['methods']

    def _add_relationship(self, class_a, class_b, rel_type='-->', card_a=None, card_b=None, source_id=None):
        class_a = self._normalize_name(class_a)
        class_b = self._normalize_name(class_b)
        rel_key = (class_a, class_b, rel_type)
        if rel_key not in self.found_relationships:
            self.found_relationships.add(rel_key)
            self.model_elements.append({
                'type': 'Relationship',
                'data': {'class_a': class_a, 'class_b': class_b, 'type': rel_type, 'card_a': card_a, 'card_b': card_b},
                'source_id': source_id
            })

    def _run_pass_1_scaffold(self, story_id, doc):
        try:
            text = doc.get('text', '')
            print(f"NLP (Pass 1 - ML): Processing '{text[:50]}...'")
            import json
            data = {}
            if text and isinstance(text, str):
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    print(f"Warning: Invalid JSON for story {story_id}, treating as raw text: '{text[:50]}...'")
                    data = {"groq_output": {}}
            print(f"Parsed data: {data}")
            if 'groq_output' in data and 'actor' in data['groq_output']:
                self._add_class(data['groq_output']['actor'], stereotype="actor", source_id=story_id)
            if 'groq_output' in data and 'class' in data['groq_output']:
                self._add_class(data['groq_output']['class'], source_id=story_id)
            if not data.get('groq_output'):
                doc = self.nlp(text)
                for ent in doc.ents:
                    if ent.label_ == "ACTOR":
                        self._add_class(ent.text, stereotype="actor", source_id=story_id)
                    elif ent.label_ == "CLASS":
                        self._add_class(ent.text, source_id=story_id)
        except Exception as e:
            logger.error(f"Scaffold pass error for story {story_id}: {e}")

    def _run_pass_2_entity_linker(self, story_id, doc):
        try:
            text = doc.get('text', '')
            print(f"NLP (Pass 2 - Enhanced): Processing '{text[:50]}...'")
            import json
            data = {}
            if text and isinstance(text, str):
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    print(f"Warning: Invalid JSON for story {story_id}, treating as raw text: '{text[:50]}...'")
                    data = {"groq_output": {}}
            actor_name = data['groq_output'].get('actor')
            class_name = data['groq_output'].get('class')

            if not actor_name:
                print("  -> No ACTOR found, attempting raw text extraction")
                doc = self.nlp(text)
                for ent in doc.ents:
                    if ent.label_ == "ACTOR":
                        actor_name = self._normalize_name(ent.text)
                        self._add_class(actor_name, stereotype="actor", source_id=story_id)
                        break

            if actor_name:
                actor_name = self._normalize_name(actor_name)
                self._add_class(actor_name, stereotype="actor", source_id=story_id)
                if class_name:
                    class_name = self._normalize_name(class_name)
                    self._add_class(class_name, source_id=story_id)

                for method in data['groq_output'].get('methods', []):
                    print(f"  -> Linking METHOD '{method}' to ACTOR '{actor_name}'")
                    self._add_method(actor_name, method, story_id)
                    if class_name:
                        print(f"  -> RELATION: '{actor_name}' --> '{class_name}'")
                        self._add_relationship(actor_name, class_name, "-->", source_id=story_id)

                for attr in data['groq_output'].get('attributes', []):
                    recent_class = class_name or actor_name
                    print(f"  -> ✅ ATTRIBUTE '{attr}' → CLASS '{recent_class}'")
                    self._add_attribute(recent_class, attr, story_id)

                for rel in data['groq_output'].get('relationship', []):
                    if actor_name and class_name:
                        rel_type = "-->" if rel.lower() == "has" else "--"
                        print(f"  -> RELATION: '{actor_name}' {rel_type} '{class_name}'")
                        self._add_relationship(actor_name, class_name, rel_type, source_id=story_id)

            if not data.get('groq_output') or not actor_name:
                doc = self.nlp(text)
                for i, ent in enumerate(doc.ents):
                    ent_text = ent.text.lower()
                    if ent.label_ == "METHOD":
                        print(f"  -> Linking METHOD '{ent_text}' to ACTOR '{actor_name or 'default'}'")
                        self._add_method(actor_name or "Actor", ent_text, story_id)
                        if i + 1 < len(doc.ents) and doc.ents[i + 1].label_ == "CLASS":
                            print(f"  -> RELATION: '{actor_name or 'Actor'}' --> '{doc.ents[i + 1].text}'")
                            self._add_relationship(actor_name or "Actor", doc.ents[i + 1].text, "-->", source_id=story_id)
                    elif ent.label_ == "ATTRIBUTE" or any(pat in ent_text for pat in self.attribute_patterns):
                        recent_class = actor_name or "Class"
                        print(f"  -> ✅ ATTRIBUTE '{ent_text}' → CLASS '{recent_class}'")
                        self._add_attribute(recent_class, ent_text, story_id)
                    elif ent.label_ == "CLASS":
                        class_name = ent.text
                        self._add_class(class_name, source_id=story_id)

        except Exception as e:
            logger.error(f"Linker pass error for story {story_id}: {e}")

    def _extract_use_cases(self, story_id, doc):
        try:
            text = doc.get('text', '')
            print(f"Extracting use cases for '{text[:50]}...'")
            import json
            data = {}
            if text and isinstance(text, str):
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    print(f"Warning: Invalid JSON for story {story_id}, treating as raw text")
                    data = {"groq_output": {}}
            if 'groq_output' in data and 'use_case' in data['groq_output']:
                self.model_elements.append({
                    'type': 'UseCase',
                    'data': {'name': data['groq_output']['use_case']},
                    'source_id': story_id
                })
                if 'actor' in data['groq_output']:
                    self._add_relationship(data['groq_output']['actor'], data['groq_output']['use_case'], "-->", source_id=story_id)
            else:
                doc = self.nlp(text)
                print(f"Entities found: {[ (ent.text, ent.label_) for ent in doc.ents ]}")
                match = re.search(r"I want to (\w+\s*\w*)", text)
                if match:
                    use_case_name = match.group(1).replace(" ", "")
                    self.model_elements.append({
                        'type': 'UseCase',
                        'data': {'name': use_case_name},
                        'source_id': story_id
                    })
                    for ent in doc.ents:
                        if ent.label_ == "ACTOR":
                            self._add_relationship(ent.text, use_case_name, "-->", source_id=story_id)
        except Exception as e:
            logger.error(f"Use case extraction error for story {story_id}: {e}")

    def _extract_sequences(self, story_id, doc):
        try:
            text = doc.get('text', '')
            print(f"Extracting sequences for '{text[:50]}...'")
            import json
            data = {}
            if text and isinstance(text, str):
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    print(f"Warning: Invalid JSON for story {story_id}, treating as raw text")
                    data = {"groq_output": {}}
            if 'groq_output' in data and 'interaction' in data['groq_output']:
                actor = data['groq_output'].get('actor', 'User')
                class_name = data['groq_output'].get('class', 'System')
                for inter in data['groq_output']['interaction']:
                    self.model_elements.append({
                        'type': 'SequenceMessage',
                        'data': {'sender': actor, 'receiver': class_name, 'message': inter},
                        'source_id': story_id
                    })
            else:
                doc = self.nlp(text)
                print(f"Entities found: {[ (ent.text, ent.label_) for ent in doc.ents ]}")
                participants = [ent.text for ent in doc.ents if ent.label_ in ["ACTOR", "CLASS"]]
                if not participants:
                    participants = ["Customer", "System"]
                if "want to" in text.lower():
                    sender = participants[0]
                    receiver = participants[-1] if len(participants) > 1 else "System"
                    message = text.split("want to")[-1].split(".")[0].strip()
                    self.model_elements.append({
                        'type': 'SequenceMessage',
                        'data': {'sender': sender, 'receiver': receiver, 'message': message},
                        'source_id': story_id
                    })
        except Exception as e:
            logger.error(f"Sequence extraction error for story {story_id}: {e}")

    def _extract_activities(self, story_id, doc):
        try:
            text = doc.get('text', '')
            print(f"Extracting activities for '{text[:50]}...'")
            import json
            data = {}
            if text and isinstance(text, str):
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    print(f"Warning: Invalid JSON for story {story_id}, treating as raw text")
                    data = {"groq_output": {}}
            if 'groq_output' in data and 'flow_steps' in data['groq_output']:
                lanes = data['groq_output'].get('actor', ["Customer"])
                for step in data['groq_output']['flow_steps']:
                    self.model_elements.append({
                        'type': 'ActivityStep',
                        'data': {'lane': lanes[0], 'step': step},
                        'source_id': story_id
                    })
            else:
                doc = self.nlp(text)
                print(f"Entities found: {[ (ent.text, ent.label_) for ent in doc.ents ]}")
                lanes = [ent.text for ent in doc.ents if ent.label_ == "ACTOR"]
                if not lanes:
                    lanes = ["Customer"]
                current_lane = lanes[0]
                steps = re.findall(r"I want to (\w+\s*\w*)", text)
                for step in steps:
                    self.model_elements.append({
                        'type': 'ActivityStep',
                        'data': {'lane': current_lane, 'step': step},
                        'source_id': story_id
                    })
        except Exception as e:
            logger.error(f"Activity extraction error for story {story_id}: {e}")

    def extract_diagram_model(self, stories_list, diagram_type):
        self.model_elements = []
        self.found_classes = {}
        self.found_relationships = set()

        for story in stories_list:
            try:
                text = story.get('StoryText', '')
                print(f"Processing story {story.get('StoryID', 'Unknown')} with text: '{text[:50]}...'")
                story_id = story.get('StoryID', 0)
                
                if diagram_type == "use_case":
                    self._extract_use_cases(story_id, {"text": text})
                elif diagram_type == "sequence":
                    self._extract_sequences(story_id, {"text": text})
                elif diagram_type == "activity":
                    self._extract_activities(story_id, {"text": text})
                else:  # class diagram
                    self._run_pass_1_scaffold(story_id, {"text": text})
                    self._run_pass_2_entity_linker(story_id, {"text": text})
            
            except Exception as e:
                logger.error(f"NLP process error for story {story_id}: {e}. Input: '{text[:50]}...'")
                continue
        
        print(f"✅ Extracted {len(self.model_elements)} elements for {diagram_type}")
        return self.model_elements

# Diagram Generator
class DiagramGenerator:
    def _format_class_name(self, name):
        return re.sub(r'[^a-zA-Z0-9_]', '_', name)

    def _create_placeholder(self, filename, error_msg):
        try:
            img = Image.new('RGB', (800, 600), color=(255, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.text((10, 10), error_msg, fill=(255, 255, 255))
            img.save(filename)
            logger.info(f"Created placeholder {filename}")
        except Exception as e:
            logger.error(f"Placeholder creation error: {e}. Procedure: Install Pillow correctly (pip install pillow).")

    def generate_class_diagram(self, project_id, elements):
        print("Generator: Starting class diagram generation...")
        if not elements:
            self._create_placeholder(os.path.join(STATIC_DIR, f"class_{project_id}.png"), "No elements extracted.")
            return

        puml_code = ["@startuml", "skinparam classAttributeIconSize 0"]
        
        class_elements = [el for el in elements if el['type'] == 'Class']
        rel_elements = [el for el in elements if el['type'] == 'Relationship']

        for el in class_elements:
            data = el['data']
            name = data['name']
            alias = self._format_class_name(name)
            stereotype = f"<<{data.get('stereotype')}>>" if data.get('stereotype') else ""
            puml_code.append(f"class \"{name}\" as {alias} {stereotype} {{")
            for attr in data.get('attributes', []): puml_code.append(f"  -{attr}: String")
            for method in data.get('methods', []): puml_code.append(f"  +{method}()")
            puml_code.append("}")

        for el in rel_elements:
            data = el['data']
            class_a_alias = self._format_class_name(data['class_a'])
            class_b_alias = self._format_class_name(data['class_b'])
            card_a = f"\"{data.get('card_a', '')}\"" if data.get('card_a') else ""
            card_b = f"\"{data.get('card_b', '')}\"" if data.get('card_b') else ""
            puml_code.append(f"{class_a_alias} {card_a} {data['type']} {card_b} {class_b_alias}")
        
        puml_code.append("@enduml")
        final_puml_code = "\n".join(puml_code)
        
        puml_filename = os.path.join(PUML_DIR, f"class_{project_id}.puml")
        with open(puml_filename, 'w') as f:
            f.write(final_puml_code)
        
        try:
            subprocess.run(
                ["java", "-jar", "plantuml.jar", puml_filename, "-tpng", "-o", os.path.abspath(STATIC_DIR)],
                check=True,
                capture_output=True
            )
            print(f"Successfully created class_{project_id}.png")
        except subprocess.CalledProcessError as e:
            logger.error(f"PlantUML error: {e.stderr.decode()}. Procedure: Ensure java and plantuml.jar are in path, check puml syntax.")
            self._create_placeholder(os.path.join(STATIC_DIR, f"class_{project_id}.png"), "PlantUML Render Error")

    def generate_use_case_diagram(self, project_id, elements):
        print("Generator: Starting use case diagram generation...")
        if not elements:
            self._create_placeholder(os.path.join(STATIC_DIR, f"use_case_{project_id}.png"), "No elements extracted.")
            return

        puml_code = ["@startuml"]
        
        use_cases = [el for el in elements if el['type'] == 'UseCase']
        actors = set()
        for el in elements:
            if el['type'] == 'Relationship' and el['data']['class_a'] and 'actor' in el['data'].get('stereotype', ''):
                actors.add(el['data']['class_a'])

        for actor in actors:
            puml_code.append(f"actor {actor}")

        for uc in use_cases:
            name = uc['data']['name']
            alias = self._format_class_name(name)
            puml_code.append(f"usecase \"{name}\" as {alias}")

        for el in [el for el in elements if el['type'] == 'Relationship']:
            data = el['data']
            class_a_alias = self._format_class_name(data['class_a'])
            class_b_alias = self._format_class_name(data['class_b'])
            puml_code.append(f"{class_a_alias} --> {class_b_alias}")

        puml_code.append("@enduml")
        final_puml_code = "\n".join(puml_code)
        
        puml_filename = os.path.join(PUML_DIR, f"use_case_{project_id}.puml")
        with open(puml_filename, 'w') as f:
            f.write(final_puml_code)
        
        try:
            subprocess.run(
                ["java", "-jar", "plantuml.jar", puml_filename, "-tpng", "-o", os.path.abspath(STATIC_DIR)],
                check=True,
                capture_output=True
            )
            print(f"Successfully created use_case_{project_id}.png")
        except subprocess.CalledProcessError as e:
            logger.error(f"PlantUML error: {e.stderr.decode()}.")
            self._create_placeholder(os.path.join(STATIC_DIR, f"use_case_{project_id}.png"), "PlantUML Render Error")

    def generate_sequence_diagram(self, project_id, elements):
        print("Generator: Starting sequence diagram generation...")
        if not elements:
            self._create_placeholder(os.path.join(STATIC_DIR, f"sequence_{project_id}.png"), "No elements extracted.")
            return

        puml_code = ["@startuml"]
        
        participants = set()
        for el in [el for el in elements if el['type'] == 'SequenceMessage']:
            participants.add(el['data']['sender'])
            participants.add(el['data']['receiver'])

        for participant in participants:
            puml_code.append(f"participant {participant}")

        for el in [el for el in elements if el['type'] == 'SequenceMessage']:
            data = el['data']
            puml_code.append(f"{data['sender']} -> {data['receiver']}: {data['message']}")

        puml_code.append("@enduml")
        final_puml_code = "\n".join(puml_code)
        
        puml_filename = os.path.join(PUML_DIR, f"sequence_{project_id}.puml")
        with open(puml_filename, 'w') as f:
            f.write(final_puml_code)
        
        try:
            subprocess.run(
                ["java", "-jar", "plantuml.jar", puml_filename, "-tpng", "-o", os.path.abspath(STATIC_DIR)],
                check=True,
                capture_output=True
            )
            print(f"Successfully created sequence_{project_id}.png")
        except subprocess.CalledProcessError as e:
            logger.error(f"PlantUML error: {e.stderr.decode()}.")
            self._create_placeholder(os.path.join(STATIC_DIR, f"sequence_{project_id}.png"), "PlantUML Render Error")

    def generate_activity_diagram(self, project_id, elements):
        print("Generator: Starting activity diagram generation...")
        if not elements:
            self._create_placeholder(os.path.join(STATIC_DIR, f"activity_{project_id}.png"), "No elements extracted.")
            return

        puml_code = ["@startuml"]
        
        lanes = set()
        for el in [el for el in elements if el['type'] == 'ActivityStep']:
            lanes.add(el['data']['lane'])

        for lane in lanes:
            puml_code.append(f"partition {lane} {{")
            for el in [el for el in elements if el['type'] == 'ActivityStep' and el['data']['lane'] == lane]:
                puml_code.append(f":{el['data']['step']};")
            puml_code.append("}")

        puml_code.append("@enduml")
        final_puml_code = "\n".join(puml_code)
        
        puml_filename = os.path.join(PUML_DIR, f"activity_{project_id}.puml")
        with open(puml_filename, 'w') as f:
            f.write(final_puml_code)
        
        try:
            subprocess.run(
                ["java", "-jar", "plantuml.jar", puml_filename, "-tpng", "-o", os.path.abspath(STATIC_DIR)],
                check=True,
                capture_output=True
            )
            print(f"Successfully created activity_{project_id}.png")
        except subprocess.CalledProcessError as e:
            logger.error(f"PlantUML error: {e.stderr.decode()}.")
            self._create_placeholder(os.path.join(STATIC_DIR, f"activity_{project_id}.png"), "PlantUML Render Error")

    def generate_diagram(self, project_id, diagram_type, elements):
        try:
            output_path = os.path.join(STATIC_DIR, f"{diagram_type}_{project_id}.png")
            if not elements and os.path.exists(output_path):
                print(f"Preserving existing {diagram_type}_{project_id}.png as no new elements extracted")
                return
            elif diagram_type == "class":
                self.generate_class_diagram(project_id, elements)
            elif diagram_type == "use_case":
                self.generate_use_case_diagram(project_id, elements)
            elif diagram_type == "sequence":
                self.generate_sequence_diagram(project_id, elements)
            elif diagram_type == "activity":
                self.generate_activity_diagram(project_id, elements)
            else:
                logger.warning(f"Unknown diagram type: {diagram_type}. Defaulting to class.")
                self.generate_class_diagram(project_id, elements)
        except Exception as e:
            logger.error(f"Diagram generation error for {diagram_type}: {e}. Procedure: Check elements list, PlantUML setup.")
            self._create_placeholder(os.path.join(STATIC_DIR, f"{diagram_type}_{project_id}.png"), "Generation Error")

# Routes
@app.route("/")
def index():
    with PersistenceLayer() as persistence:
        projects = [p for p in persistence.get_all_projects() if not p['UserID'] or current_user.is_authenticated]
    return render_template_string(HTML_DASHBOARD_TEMPLATE, projects=projects, current_user=current_user)

@app.route("/register", methods=["POST"])
def register():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    confirm_password = request.form.get('confirm_password', '')
    
    if not username or not password or password != confirm_password or len(password) < 6:
        flash('Invalid registration details. Ensure passwords match and are at least 6 characters.', 'error')
        return redirect(url_for('index'))
    
    with PersistenceLayer() as persistence:
        password_hash = generate_password_hash(password)
        user_id = persistence.create_user(username, password_hash)
        if user_id:
            user = User(user_id)
            login_user(user)
            flash('Registration successful! You are now logged in.', 'success')
        else:
            flash('Username already exists. Please choose a different username.', 'error')
    
    return redirect(url_for('index'))

@app.route("/login", methods=["POST"])
def login():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    
    if not username or not password:
        flash('Please enter both username and password.', 'error')
        return redirect(url_for('index'))
    
    with PersistenceLayer() as persistence:
        user = persistence.get_user_by_username(username)
        if user and check_password_hash(user['PasswordHash'], password):
            login_user(User(user['UserID']))
            flash('Login successful!', 'success')
        else:
            flash('Invalid username or password.', 'error')
    
    return redirect(url_for('index'))

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route("/project/new", methods=["POST"])
def add_project():
    project_name = request.form.get('project_name')
    if not project_name:
        flash('Project name is required.', 'error')
        return redirect(url_for('index'))
    
    with PersistenceLayer() as persistence:
        user_id = current_user.id if current_user.is_authenticated else None
        project_id = persistence.create_project(project_name, user_id)
        if project_id:
            flash(f'Project "{project_name}" created with ID {project_id}.', 'success')
        else:
            flash('Error creating project. Please try again.', 'error')
    
    return redirect(url_for('view_project', project_id=project_id if project_id else 0))

@app.route("/project/<int:project_id>")
def view_project(project_id):
    with PersistenceLayer() as persistence:
        project = persistence.get_project(project_id)
        if not project:
            flash("Project not found.")
            return redirect(url_for('index'))
        
        stories_text = persistence.get_stories_as_text(project_id)
        is_owner = current_user.is_authenticated and project.get('UserID') == current_user.id
    
    diagram_type = request.args.get('diagram_type', 'class')
    diagram_path = os.path.join(STATIC_DIR, f"{diagram_type}_{project_id}.png")
    diagram_url = url_for('static', filename=f"{diagram_type}_{project_id}.png") + f"?t={time.time()}" if os.path.exists(diagram_path) else None
    
    return render_template_string(HTML_TEMPLATE, project=project, stories_text=stories_text, diagram_url=diagram_url, current_user=current_user, is_owner=is_owner)

@app.route("/project/<int:project_id>/update", methods=["POST"])
@login_required
def update_project(project_id):
    with PersistenceLayer() as persistence:
        project = persistence.get_project(project_id)
        if not project or (project.get('UserID') and project.get('UserID') != current_user.id):
            flash("You don't have permission to update this project.", 'warning')
            return redirect(url_for('view_project', project_id=project_id))
        
        stories_text = request.form.get('user_stories', '').strip()
        if not stories_text:
            flash("No stories provided. Add some to generate diagram.")
            return redirect(url_for('view_project', project_id=project_id))
        
        diagram_type = request.form.get('diagram_type', 'class')
        
        persistence.save_stories_from_text(project_id, stories_text)
        persistence.delete_model_elements(project_id)
        
        stories_list = persistence.get_stories_list(project_id)
        if not stories_list:
            flash("Failed to retrieve stories. Check input and try again.")
            return redirect(url_for('view_project', project_id=project_id))
        
        nlp_engine = NLPEngine(nlp)
        generator = DiagramGenerator()
        new_model_elements = nlp_engine.extract_diagram_model(stories_list, diagram_type)
        persistence.save_model_elements(project_id, new_model_elements)
        generator.generate_diagram(project_id, diagram_type, new_model_elements)
    
    flash("Diagram updated successfully!", 'success')
    return redirect(url_for('view_project', project_id=project_id, diagram_type=diagram_type))

@app.route('/static/<path:filename>')
def send_static_file(filename):
    return send_from_directory(STATIC_DIR, filename)

# Main
if __name__ == "__main__":
    from waitress import serve
    print(f"Starting Production Server (Waitress) on http://127.0.0.1:5000...")
    print(f"Connecting to DB with driver: {DB_CONFIG['driver']}")
    serve(app, host='127.0.0.1', port=5000)