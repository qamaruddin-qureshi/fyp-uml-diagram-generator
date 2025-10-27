import spacy
import re
import json
import subprocess
import logging
from PIL import Image, ImageDraw
import os

# Configure logging
logger = logging.getLogger(__name__)

# Directories and Model
PUML_DIR = "generated_puml"
STATIC_DIR = "static"
MODEL_PATH = "./my_uml_model/model-best"

# Load spaCy model
if not os.path.exists(MODEL_PATH):
    logger.warning(f"Model not found at {MODEL_PATH}. Using blank model.")
    nlp = spacy.blank("en")
else:
    try:
        nlp = spacy.load(MODEL_PATH)
        logger.info("Model loaded successfully.")
    except Exception as e:
        logger.error(f"Model load error: {e}. Using blank model as fallback.")
        nlp = spacy.blank("en")

# Create directories if they don't exist
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)
if not os.path.exists(PUML_DIR):
    os.makedirs(PUML_DIR)


class NLPEngine:
    """Natural Language Processing Engine for extracting UML elements from user stories"""
    
    def __init__(self, nlp_model):
        self.nlp = nlp_model
        self.model_elements = []
        self.found_classes = {}
        self.found_relationships = set()
        self.attribute_patterns = [
            "name", "address", "date", "id", "email", "type", "status", "number", "code", 
            "password", "username", "price", "description", "quantity", "totalamount", 
            "orderdate", "shippingaddress"
        ]

    def _normalize_name(self, name):
        """Normalize class names to PascalCase"""
        return re.sub(r'([a-z])([A-Z])', r'\1 \2', name).title().replace(" ", "")

    def _add_class(self, name, stereotype=None, source_id=None):
        """Add a class to the model"""
        name = self._normalize_name(name)
        if name not in self.found_classes:
            self.found_classes[name] = {'attributes': [], 'methods': [], 'stereotype': stereotype}
            self.model_elements.append({
                'type': 'Class',
                'data': {'name': name, 'attributes': [], 'methods': [], 'stereotype': stereotype},
                'source_id': source_id
            })

    def _add_attribute(self, class_name, attr_name, source_id):
        """Add an attribute to a class"""
        class_name = self._normalize_name(class_name)
        attr_name = attr_name.lower()
        if class_name in self.found_classes and attr_name not in self.found_classes[class_name]['attributes']:
            self.found_classes[class_name]['attributes'].append(attr_name)
            for el in self.model_elements:
                if el['type'] == 'Class' and el['data']['name'] == class_name:
                    el['data']['attributes'] = self.found_classes[class_name]['attributes']

    def _add_method(self, class_name, method_name, source_id):
        """Add a method to a class"""
        class_name = self._normalize_name(class_name)
        method_name = method_name.lower()
        if class_name in self.found_classes and method_name not in self.found_classes[class_name]['methods']:
            self.found_classes[class_name]['methods'].append(method_name)
            for el in self.model_elements:
                if el['type'] == 'Class' and el['data']['name'] == class_name:
                    el['data']['methods'] = self.found_classes[class_name]['methods']

    def _add_relationship(self, class_a, class_b, rel_type='-->', card_a=None, card_b=None, source_id=None):
        """Add a relationship between two classes"""
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

    def _run_pass_1_scaffold(self, story_id, text):
        """Pass 1: Extract basic class scaffolds"""
        try:
            logger.info(f"NLP (Pass 1): Processing story {story_id}")
            data = {}
            if text and isinstance(text, str):
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    pass
            
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
            logger.error(f"Pass 1 error for story {story_id}: {e}")

    def _run_pass_2_entity_linker(self, story_id, text):
        """Pass 2: Link entities and extract relationships"""
        try:
            logger.info(f"NLP (Pass 2): Processing story {story_id}")
            data = {}
            if text and isinstance(text, str):
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    pass
            
            actor_name = data.get('groq_output', {}).get('actor')
            class_name = data.get('groq_output', {}).get('class')

            if actor_name:
                actor_name = self._normalize_name(actor_name)
                self._add_class(actor_name, stereotype="actor", source_id=story_id)
                
                if class_name:
                    class_name = self._normalize_name(class_name)
                    self._add_class(class_name, source_id=story_id)

                for method in data.get('groq_output', {}).get('methods', []):
                    self._add_method(actor_name, method, story_id)
                    if class_name:
                        self._add_relationship(actor_name, class_name, "-->", source_id=story_id)

                for attr in data.get('groq_output', {}).get('attributes', []):
                    recent_class = class_name or actor_name
                    self._add_attribute(recent_class, attr, story_id)

            if not data.get('groq_output') or not actor_name:
                doc = self.nlp(text)
                for i, ent in enumerate(doc.ents):
                    ent_text = ent.text.lower()
                    if ent.label_ == "METHOD":
                        self._add_method(actor_name or "Actor", ent_text, story_id)
                    elif ent.label_ == "ATTRIBUTE" or any(pat in ent_text for pat in self.attribute_patterns):
                        recent_class = actor_name or "Class"
                        self._add_attribute(recent_class, ent_text, story_id)
                    elif ent.label_ == "CLASS":
                        class_name = ent.text
                        self._add_class(class_name, source_id=story_id)
        except Exception as e:
            logger.error(f"Pass 2 error for story {story_id}: {e}")

    def _extract_use_cases(self, story_id, text):
        """Extract use case diagram elements"""
        try:
            logger.info(f"Extracting use cases for story {story_id}")
            data = {}
            if text and isinstance(text, str):
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    pass
            
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

    def _extract_sequences(self, story_id, text):
        """Extract sequence diagram elements"""
        try:
            logger.info(f"Extracting sequences for story {story_id}")
            data = {}
            if text and isinstance(text, str):
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    pass
            
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

    def _extract_activities(self, story_id, text):
        """Extract activity diagram elements"""
        try:
            logger.info(f"Extracting activities for story {story_id}")
            data = {}
            if text and isinstance(text, str):
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    pass
            
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
        """Extract diagram model from stories"""
        self.model_elements = []
        self.found_classes = {}
        self.found_relationships = set()

        for story in stories_list:
            try:
                text = story.get('storytext', '')
                story_id = story.get('storyid', 0)
                logger.info(f"Processing story {story_id}: {text[:50]}...")
                
                if diagram_type == "use_case":
                    self._extract_use_cases(story_id, text)
                elif diagram_type == "sequence":
                    self._extract_sequences(story_id, text)
                elif diagram_type == "activity":
                    self._extract_activities(story_id, text)
                else:  # class diagram
                    self._run_pass_1_scaffold(story_id, text)
                    self._run_pass_2_entity_linker(story_id, text)
            
            except Exception as e:
                logger.error(f"NLP process error for story {story_id}: {e}")
                continue
        
        logger.info(f"Extracted {len(self.model_elements)} elements for {diagram_type}")
        return self.model_elements


class DiagramGenerator:
    """Generate UML diagrams from extracted model elements"""
    
    def _format_class_name(self, name):
        """Format class name for PlantUML"""
        return re.sub(r'[^a-zA-Z0-9_]', '_', name)

    def _create_placeholder(self, filename, error_msg):
        """Create a placeholder image when diagram generation fails"""
        try:
            img = Image.new('RGB', (800, 600), color=(255, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.text((10, 10), error_msg, fill=(255, 255, 255))
            img.save(filename)
            logger.info(f"Created placeholder {filename}")
        except Exception as e:
            logger.error(f"Placeholder creation error: {e}")

    def generate_class_diagram(self, project_id, elements):
        """Generate class diagram"""
        logger.info("Starting class diagram generation...")
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
            for attr in data.get('attributes', []):
                puml_code.append(f"  -{attr}: String")
            for method in data.get('methods', []):
                puml_code.append(f"  +{method}()")
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
            plantuml_jar = os.path.abspath("plantuml.jar")
            if not os.path.exists(plantuml_jar):
                raise FileNotFoundError(f"plantuml.jar not found at {plantuml_jar}")
            
            subprocess.run(
                ["java", "-jar", plantuml_jar, puml_filename, "-tpng", "-o", os.path.abspath(STATIC_DIR)],
                check=True,
                capture_output=True
            )
            logger.info(f"Successfully created class_{project_id}.png")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.error(f"PlantUML error: {e}")
            self._create_placeholder(os.path.join(STATIC_DIR, f"class_{project_id}.png"), "PlantUML Render Error")

    def generate_use_case_diagram(self, project_id, elements):
        """Generate use case diagram"""
        logger.info("Starting use case diagram generation...")
        if not elements:
            self._create_placeholder(os.path.join(STATIC_DIR, f"use_case_{project_id}.png"), "No elements extracted.")
            return

        puml_code = ["@startuml"]
        
        use_cases = [el for el in elements if el['type'] == 'UseCase']
        actors = set()
        for el in elements:
            if el['type'] == 'Relationship':
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
            plantuml_jar = os.path.abspath("plantuml.jar")
            if not os.path.exists(plantuml_jar):
                raise FileNotFoundError(f"plantuml.jar not found at {plantuml_jar}")
            
            subprocess.run(
                ["java", "-jar", plantuml_jar, puml_filename, "-tpng", "-o", os.path.abspath(STATIC_DIR)],
                check=True,
                capture_output=True
            )
            logger.info(f"Successfully created use_case_{project_id}.png")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.error(f"PlantUML error: {e}")
            self._create_placeholder(os.path.join(STATIC_DIR, f"use_case_{project_id}.png"), "PlantUML Render Error")

    def generate_sequence_diagram(self, project_id, elements):
        """Generate sequence diagram"""
        logger.info("Starting sequence diagram generation...")
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
            plantuml_jar = os.path.abspath("plantuml.jar")
            if not os.path.exists(plantuml_jar):
                raise FileNotFoundError(f"plantuml.jar not found at {plantuml_jar}")
            
            subprocess.run(
                ["java", "-jar", plantuml_jar, puml_filename, "-tpng", "-o", os.path.abspath(STATIC_DIR)],
                check=True,
                capture_output=True
            )
            logger.info(f"Successfully created sequence_{project_id}.png")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.error(f"PlantUML error: {e}")
            self._create_placeholder(os.path.join(STATIC_DIR, f"sequence_{project_id}.png"), "PlantUML Render Error")

    def generate_activity_diagram(self, project_id, elements):
        """Generate activity diagram"""
        logger.info("Starting activity diagram generation...")
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
            plantuml_jar = os.path.abspath("plantuml.jar")
            if not os.path.exists(plantuml_jar):
                raise FileNotFoundError(f"plantuml.jar not found at {plantuml_jar}")
            
            subprocess.run(
                ["java", "-jar", plantuml_jar, puml_filename, "-tpng", "-o", os.path.abspath(STATIC_DIR)],
                check=True,
                capture_output=True
            )
            logger.info(f"Successfully created activity_{project_id}.png")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.error(f"PlantUML error: {e}")
            self._create_placeholder(os.path.join(STATIC_DIR, f"activity_{project_id}.png"), "PlantUML Render Error")

    def generate_diagram(self, project_id, diagram_type, elements):
        """Generate diagram based on type"""
        try:
            output_path = os.path.join(STATIC_DIR, f"{diagram_type}_{project_id}.png")
            if not elements and os.path.exists(output_path):
                logger.info(f"Preserving existing {diagram_type}_{project_id}.png")
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
            logger.error(f"Diagram generation error for {diagram_type}: {e}")
            self._create_placeholder(os.path.join(STATIC_DIR, f"{diagram_type}_{project_id}.png"), "Generation Error")
