# uml_extractors.py
"""
Contains all diagram extractor classes for UML model extraction from user stories.
"""
import re
import json
import logging

logger = logging.getLogger(__name__)

class BaseDiagramExtractor:
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

class ClassDiagramExtractor(BaseDiagramExtractor):
    def extract(self, stories_list):
        self.model_elements = []
        self.found_classes = {}
        self.found_relationships = set()
        actor_set = set()
        class_set = set()
        # Contextual attribute/method/relationship inference
        for story in stories_list:
            try:
                text = story.get('storytext', '')
                story_id = story.get('storyid', 0)
                logger.info(f"Processing story {story_id}: {text[:50]}...")
                data = {}
                if text and isinstance(text, str):
                    try:
                        data = json.loads(text)
                    except json.JSONDecodeError:
                        pass
                # Extract actor and class
                actor_name = data.get('groq_output', {}).get('actor')
                class_name = data.get('groq_output', {}).get('class')
                # Add actor as stereotype only, not as class
                if actor_name:
                    actor_name = self._normalize_name(actor_name)
                    if actor_name not in actor_set:
                        actor_set.add(actor_name)
                        self.model_elements.append({
                            'type': 'Actor',
                            'data': {'name': actor_name},
                            'source_id': story_id
                        })
                # Add class
                if class_name:
                    class_name = self._normalize_name(class_name)
                    if class_name not in class_set:
                        class_set.add(class_name)
                        self._add_class(class_name, source_id=story_id)
                # Add attributes and methods to class only
                if class_name:
                    # Use all available attributes/methods
                    for attr in data.get('groq_output', {}).get('attributes', []):
                        self._add_attribute(class_name, attr, story_id)
                    for method in data.get('groq_output', {}).get('methods', []):
                        self._add_method(class_name, method, story_id)
                    # Contextual extraction from story text
                    # Use regex and NLP to find likely attributes/methods
                    # Attributes: look for 'with', 'including', 'such as', 'containing', etc.
                    attr_matches = re.findall(r'with ([\w, ]+)', text)
                    for match in attr_matches:
                        for attr in re.split(r',| and ', match):
                            attr = attr.strip()
                            if attr:
                                self._add_attribute(class_name, attr, story_id)
                    # Methods: look for 'want to (\w+)', 'can (\w+)', etc.
                    method_matches = re.findall(r'want to ([\w]+)', text)
                    for method in method_matches:
                        self._add_method(class_name, method, story_id)
                # Add relationship (actor interacts with class)
                if actor_name and class_name:
                    # Infer relationship type and multiplicity from story context
                    rel_type = '-->'
                    card_a = '1'
                    card_b = '*'
                    # If story suggests ownership or singular, adjust multiplicity
                    if re.search(r'has|own|register|create', text, re.IGNORECASE):
                        card_b = '1'
                    self._add_relationship(actor_name, class_name, rel_type, card_a, card_b, source_id=story_id)
                # If no groq_output, fallback to NLP
                if not data.get('groq_output'):
                    doc = self.nlp(text)
                    actors = []
                    classes = []
                    methods = []
                    attributes = []
                    for ent in doc.ents:
                        if ent.label_ == "ACTOR":
                            actors.append(ent.text)
                        elif ent.label_ == "CLASS":
                            classes.append(ent.text)
                        elif ent.label_ == "METHOD":
                            methods.append(ent.text)
                        elif ent.label_ == "ATTRIBUTE":
                            attributes.append(ent.text)
                    # Add actors
                    for actor in actors:
                        actor_n = self._normalize_name(actor)
                        if actor_n not in actor_set:
                            actor_set.add(actor_n)
                            self.model_elements.append({
                                'type': 'Actor',
                                'data': {'name': actor_n},
                                'source_id': story_id
                            })
                    # Add classes
                    for cls in classes:
                        cls_n = self._normalize_name(cls)
                        if cls_n not in class_set:
                            class_set.add(cls_n)
                            self._add_class(cls_n, source_id=story_id)
                    # Add attributes/methods to first class
                    if classes:
                        target_class = self._normalize_name(classes[0])
                        for attr in attributes:
                            self._add_attribute(target_class, attr, story_id)
                        for method in methods:
                            self._add_method(target_class, method, story_id)
                        # Contextual extraction from text
                        attr_matches = re.findall(r'with ([\w, ]+)', text)
                        for match in attr_matches:
                            for attr in re.split(r',| and ', match):
                                attr = attr.strip()
                                if attr:
                                    self._add_attribute(target_class, attr, story_id)
                        method_matches = re.findall(r'want to ([\w]+)', text)
                        for method in method_matches:
                            self._add_method(target_class, method, story_id)
                    # Add relationships
                    if actors and classes:
                        rel_type = '-->'
                        card_a = '1'
                        card_b = '*'
                        if re.search(r'has|own|register|create', text, re.IGNORECASE):
                            card_b = '1'
                        self._add_relationship(self._normalize_name(actors[0]), self._normalize_name(classes[0]), rel_type, card_a, card_b, source_id=story_id)
            except Exception as e:
                logger.error(f"Class diagram extraction error for story {story_id}: {e}")
                continue
        logger.info(f"Extracted {len(self.model_elements)} elements for class diagram")
        return self.model_elements

class UseCaseDiagramExtractor(BaseDiagramExtractor):
    def extract(self, stories_list):
        self.model_elements = []
        self.found_classes = {}
        self.found_relationships = set()
        for story in stories_list:
            try:
                text = story.get('storytext', '')
                story_id = story.get('storyid', 0)
                logger.info(f"Processing story {story_id}: {text[:50]}...")
                self._extract_use_cases(story_id, text)
            except Exception as e:
                logger.error(f"Use case diagram extraction error for story {story_id}: {e}")
                continue
        logger.info(f"Extracted {len(self.model_elements)} elements for use case diagram")
        return self.model_elements

    def _extract_use_cases(self, story_id, text):
        try:
            logger.info(f"Extracting use cases for story {story_id}")
            data = {}
            if text and isinstance(text, str):
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    pass
            if 'groq_output' in data and 'use_case' in data['groq_output']:
                if 'actor' in data['groq_output']:
                    self._add_class(data['groq_output']['actor'], stereotype="actor", source_id=story_id)
                self.model_elements.append({
                    'type': 'UseCase',
                    'data': {'name': data['groq_output']['use_case']},
                    'source_id': story_id
                })
                if 'actor' in data['groq_output']:
                    self._add_relationship(data['groq_output']['actor'], data['groq_output']['use_case'], "-->", source_id=story_id)
            else:
                doc = self.nlp(text)
                actors = []
                for ent in doc.ents:
                    if ent.label_ == "ACTOR":
                        actors.append(ent.text)
                        self._add_class(ent.text, stereotype="actor", source_id=story_id)
                match = re.search(r"I want to (\w+\s*\w*)", text)
                if match:
                    use_case_name = match.group(1).replace(" ", "")
                    self.model_elements.append({
                        'type': 'UseCase',
                        'data': {'name': use_case_name},
                        'source_id': story_id
                    })
                    for actor in actors:
                        self._add_relationship(actor, use_case_name, "-->", source_id=story_id)
        except Exception as e:
            logger.error(f"Use case extraction error for story {story_id}: {e}")

class SequenceDiagramExtractor(BaseDiagramExtractor):
    def extract(self, stories_list):
        self.model_elements = []
        self.found_classes = {}
        self.found_relationships = set()
        for story in stories_list:
            try:
                text = story.get('storytext', '')
                story_id = story.get('storyid', 0)
                logger.info(f"Processing story {story_id}: {text[:50]}...")
                self._extract_sequences(story_id, text)
            except Exception as e:
                logger.error(f"Sequence diagram extraction error for story {story_id}: {e}")
                continue
        logger.info(f"Extracted {len(self.model_elements)} elements for sequence diagram")
        return self.model_elements

    def _extract_sequences(self, story_id, text):
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

class ActivityDiagramExtractor(BaseDiagramExtractor):
    def extract(self, stories_list):
        self.model_elements = []
        self.found_classes = {}
        self.found_relationships = set()
        for story in stories_list:
            try:
                text = story.get('storytext', '')
                story_id = story.get('storyid', 0)
                logger.info(f"Processing story {story_id}: {text[:50]}...")
                self._extract_activities(story_id, text)
            except Exception as e:
                logger.error(f"Activity diagram extraction error for story {story_id}: {e}")
                continue
        logger.info(f"Extracted {len(self.model_elements)} elements for activity diagram")
        return self.model_elements

    def _extract_activities(self, story_id, text):
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
