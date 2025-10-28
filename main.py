from PIL import Image, ImageDraw
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, LoginManager
from flask import send_from_directory
import os
import subprocess
import json
import spacy
import re
import time
import logging
from flask import Flask, request, redirect, url_for, flash, render_template_string, jsonify
from flask_cors import CORS
from flask_login import current_user
from sqlalchemy import text, create_engine
from models import Base, User, Project
from auth.authroutes import auth_bp
from project.projectroutes import project_bp
from persistence import PersistenceLayer, logger, engine



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

# Sync models with database
Base.metadata.create_all(engine)


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

from flask import render_template

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