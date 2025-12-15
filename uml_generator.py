# uml_generator.py
"""
Contains the DiagramGenerator class for PlantUML code and image generation.
"""
import os
import logging
import re
from PIL import Image, ImageDraw
import subprocess

logger = logging.getLogger(__name__)

class DiagramGenerator:
    def generate_diagram(self, project_id, diagram_type, elements, static_dir="static", puml_dir="generated_puml"):
        """
        Generate a diagram based on type. Dispatches to the correct method.
        Args:
            project_id: Project identifier
            diagram_type: 'class', 'use_case', 'sequence', or 'activity'
            elements: Extracted model elements
            static_dir: Directory for output images
            puml_dir: Directory for output .puml files
        """
        if diagram_type == "class":
            self.generate_class_diagram(project_id, elements, static_dir, puml_dir)
        elif diagram_type == "use_case":
            self.generate_use_case_diagram(project_id, elements, static_dir, puml_dir)
        elif diagram_type == "sequence":
            self.generate_sequence_diagram(project_id, elements, static_dir, puml_dir)
        elif diagram_type == "activity":
            self.generate_activity_diagram(project_id, elements, static_dir, puml_dir)
        else:
            logger.warning(f"Unknown diagram type: {diagram_type}. Defaulting to class.")
            self.generate_class_diagram(project_id, elements, static_dir, puml_dir)


    def generate_use_case_diagram(self, project_id, elements, static_dir, puml_dir):
        logger.info("Starting use case diagram generation...")
        if not elements:
            self._create_placeholder(os.path.join(static_dir, f"use_case_{project_id}.png"), "No elements extracted.")
            return

        puml_code = ["@startuml", "left to right direction"]
        
        # 1. Collect unique Actors and Use Cases
        # Using a robust lookup map to connect unique actors and use cases: { "normalized_key": "SafeID" }
        id_lookup = {}
        
        # Store the display definitions to write to the file
        actor_definitions = {} # SafeID -> Display Name
        usecase_definitions = {} # SafeID -> Display Name
        relationships = []

        # Helper to normalize keys for lookup (lowercase, no spaces)
        def normalize_key(text):
            return re.sub(r'[^a-zA-Z0-9]', '', text).lower()

        # Helper to make safe IDs for PlantUML (alphanumeric only)
        def make_id(text):
            clean = re.sub(r'[^a-zA-Z0-9]', '', text)
            if not clean:
                return "Unknown" + str(hash(text))
            return clean

        for el in elements:
            if el['type'] == 'Class' and el['data'].get('stereotype') == 'actor':
                name = el['data']['name']
                safe_id = make_id(name)
                # Store for lookup
                id_lookup[normalize_key(name)] = safe_id
                # Store for definition
                actor_definitions[safe_id] = name
            
            if el['type'] == 'UseCase':
                name = el['data']['name']
                safe_id = make_id(name)
                # Store for lookup
                id_lookup[normalize_key(name)] = safe_id
                # Store for definition
                usecase_definitions[safe_id] = name
            
            if el['type'] == 'Relationship':
                relationships.append(el['data'])

        # 2. Define Actors with Aliases
        for safe_id, display_name in actor_definitions.items():
            puml_code.append(f'actor "{display_name}" as {safe_id}')

        # 3. Define Use Cases with Aliases (inside rectangle)
        puml_code.append("rectangle System {")
        for safe_id, display_name in usecase_definitions.items(): # Python 3.7+ preserves insertion order. Elements come from list. Should be stable. But sorting is safer?
            # Keeping insertion order usually matches story order which is nice.
            # But let's leave it unless it proves unstable. Use Case passed most tests.
            # Actually, Use Case passed? "Original_Inspector_System" Use Case PASS.
            # So Use Case is likely stable.
            puml_code.append(f'usecase "{display_name}" as {safe_id}')
        puml_code.append("}")

        # 4. Draw Relationships using Safe IDs
        for rel in relationships:
            class_a = rel['class_a']
            class_b = rel['class_b']
            
            # Lookup using the normalized key
            id_a = id_lookup.get(normalize_key(class_a))
            id_b = id_lookup.get(normalize_key(class_b))

            if id_a and id_b:
                puml_code.append(f"{id_a} --> {id_b}")
            else:
                logger.warning(f"Could not connect {class_a} to {class_b}. IDs found: {id_a} -> {id_b}")

        puml_code.append("@enduml")
        
        # Write file and execute PlantUML
        final_puml_code = "\n".join(puml_code)
        puml_filename = os.path.join(puml_dir, f"use_case_{project_id}.puml")
        with open(puml_filename, 'w') as f:
            f.write(final_puml_code)
            
        try:
            plantuml_jar = os.path.abspath("plantuml.jar")
            subprocess.run(
                ["java", "-jar", plantuml_jar, puml_filename, "-tpng", "-o", os.path.abspath(static_dir)],
                check=True,
                capture_output=True
            )
            logger.info(f"Successfully created use_case_{project_id}.png")
        except Exception as e:
            logger.error(f"PlantUML error: {e}")
            self._create_placeholder(os.path.join(static_dir, f"use_case_{project_id}.png"), "PlantUML Render Error")


    def generate_sequence_diagram(self, project_id, elements, static_dir, puml_dir):
        logger.info("Starting sequence diagram generation...")
        if not elements:
            self._create_placeholder(os.path.join(static_dir, f"sequence_{project_id}.png"), "No elements extracted.")
            return

        puml_code = ["@startuml"]
        participants = set()
        
        # Collect all unique names
        for el in [el for el in elements if el['type'] == 'SequenceMessage']:
            participants.add(el['data']['sender'])
            participants.add(el['data']['receiver'])

        # Define participants with quotes to handle spaces
        for participant in sorted(list(participants)):
            puml_code.append(f'participant "{participant}" as {self._format_class_name(participant)}')

        # Generate messages using the aliases
        for el in [el for el in elements if el['type'] == 'SequenceMessage']:
            data = el['data']
            sender_alias = self._format_class_name(data['sender'])
            receiver_alias = self._format_class_name(data['receiver'])
            # Escape quotes in message
            clean_message = data['message'].replace('"', "'")
            puml_code.append(f'{sender_alias} -> {receiver_alias}: {clean_message}')

        puml_code.append("@enduml")
        final_puml_code = "\n".join(puml_code)
        puml_filename = os.path.join(puml_dir, f"sequence_{project_id}.puml")
        with open(puml_filename, 'w') as f:
            f.write(final_puml_code)
        try:
            plantuml_jar = os.path.abspath("plantuml.jar")
            if not os.path.exists(plantuml_jar):
                raise FileNotFoundError(f"plantuml.jar not found at {plantuml_jar}")
            subprocess.run(
                ["java", "-jar", plantuml_jar, puml_filename, "-tpng", "-o", os.path.abspath(static_dir)],
                check=True,
                capture_output=True
            )
            logger.info(f"Successfully created sequence_{project_id}.png")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.error(f"PlantUML error: {e}")
            self._create_placeholder(os.path.join(static_dir, f"sequence_{project_id}.png"), "PlantUML Render Error")


    def generate_activity_diagram(self, project_id, elements, static_dir, puml_dir):
        logger.info("Starting activity diagram generation...")
        if not elements:
            self._create_placeholder(os.path.join(static_dir, f"activity_{project_id}.png"), "No elements extracted.")
            return

        puml_code = ["@startuml"]
        lanes = set()
        for el in [el for el in elements if el['type'] == 'ActivityStep']:
            lanes.add(el['data']['lane'])
        for lane in sorted(list(lanes)):
            puml_code.append(f"partition {lane} {{")
            for el in [el for el in elements if el['type'] == 'ActivityStep' and el['data']['lane'] == lane]:
                puml_code.append(f":{el['data']['step']};")
            puml_code.append("}")
        puml_code.append("@enduml")
        final_puml_code = "\n".join(puml_code)
        puml_filename = os.path.join(puml_dir, f"activity_{project_id}.puml")
        with open(puml_filename, 'w') as f:
            f.write(final_puml_code)
        try:
            plantuml_jar = os.path.abspath("plantuml.jar")
            if not os.path.exists(plantuml_jar):
                raise FileNotFoundError(f"plantuml.jar not found at {plantuml_jar}")
            subprocess.run(
                ["java", "-jar", plantuml_jar, puml_filename, "-tpng", "-o", os.path.abspath(static_dir)],
                check=True,
                capture_output=True
            )
            logger.info(f"Successfully created activity_{project_id}.png")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.error(f"PlantUML error: {e}")
            self._create_placeholder(os.path.join(static_dir, f"activity_{project_id}.png"), "PlantUML Render Error")
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
            logger.error(f"Placeholder creation error: {e}")

    def generate_class_diagram(self, project_id, elements, static_dir, puml_dir):
        logger.info("Starting class diagram generation...")
        if not elements:
            self._create_placeholder(os.path.join(static_dir, f"class_{project_id}.png"), "No elements extracted.")
            return

        puml_code = ["@startuml", "skinparam classAttributeIconSize 0"]
        
        # Helper to infer data types from names
        def guess_type(text):
            text = str(text).lower()
            if any(x in text for x in ['id', 'count', 'num', 'quantity']): return 'int'
            if any(x in text for x in ['is', 'has', 'active', 'valid']): return 'boolean'
            if any(x in text for x in ['date', 'time', 'created']): return 'Date'
            if any(x in text for x in ['price', 'cost', 'amount']): return 'float'
            return 'String'

        # Filter for Classes and Actors
        class_elements = [el for el in elements if el['type'] == 'Class']
        
        for el in class_elements:
            data = el['data']
            name = data['name']
            alias = self._format_class_name(name)
            stereotype = f"<<{data.get('stereotype')}>>" if data.get('stereotype') else ""
            
            puml_code.append(f'class "{name}" as {alias} {stereotype} {{')
            
            # 1. Attributes
            for attr in data.get('attributes', []):
                # Check if attr is dict (new format) or string (old format)
                if isinstance(attr, dict):
                    attr_name = attr.get('name', 'unknown')
                    vis = attr.get('visibility', '-')
                    dtype = attr.get('type', guess_type(attr_name))
                else:
                    attr_name = str(attr).strip()
                    vis = "-"
                    dtype = guess_type(attr_name)
                
                puml_code.append(f'  {vis}{attr_name} : {dtype}')
            
            puml_code.append("  ..")
            
            # 2. Methods
            methods = data.get('methods', [])
            # In new logic, methods is already detailed list of dicts. 
            # In old logic, it was strings, and there was methods_detailed.
            # My new extractor puts detailed dicts into 'methods'.
            
            for method in methods:
                if isinstance(method, dict):
                    m_name = method.get('name', 'func')
                    vis = method.get('visibility', '+')
                    ret_type = method.get('return_type', 'void')
                    params = method.get('params', [])
                else:
                    m_name = str(method)
                    vis = "+"
                    ret_type = "void"
                    params = []

                param_str = ""
                if params:
                    clean_params = []
                    for p in params:
                        if isinstance(p, dict):
                            p_name = p.get('name', '')
                            p_type = p.get('type', 'String')
                            p_dir = p.get('direction', 'in')
                            clean_params.append(f'{p_dir} "{p_name}" : {p_type}')
                        else:
                            # Fallback for old style strings
                            p_clean = re.sub(r'\b(my|the|a|an)\b', '', str(p), flags=re.IGNORECASE).strip()
                            if p_clean:
                                p_type = guess_type(p_clean)
                                clean_params.append(f'in "{p_clean}" : {p_type}')
                    param_str = ", ".join(clean_params)
                
                puml_code.append(f'  {vis}{m_name}({param_str}) : {ret_type}')
                
            puml_code.append("}")

        # 3. Relationships
        # Map internal types to PlantUML arrows
        rel_map = {
            'Association': '-->',
            'Inheritance': '--|>', 
            'Realization': '..|>',
            'Dependency': '..>',
            'Aggregation': 'o--',
            'Composition': '*--',
            '-->': '-->',   # Fallback for raw types
            '--|>': '--|>',
            '..|>': '..|>',
            '..>': '..>',
            'o--': 'o--',
            '*--': '*--'
        }

        for el in [x for x in elements if x['type'] == 'Relationship']:
            data = el['data']
            class_a = self._format_class_name(data['class_a'])
            class_b = self._format_class_name(data['class_b'])
            
            # get type from data, default to Association
            rel_type_raw = data.get('type', '-->')
            arrow = rel_map.get(rel_type_raw, '-->')
            
            puml_code.append(f"{class_a} {arrow} {class_b}")

        puml_code.append("@enduml")
        
        # Standard file writing...
        final_puml_code = "\n".join(puml_code)
        puml_filename = os.path.join(puml_dir, f"class_{project_id}.puml")
        with open(puml_filename, 'w') as f:
            f.write(final_puml_code)
            
        try:
            plantuml_jar = os.path.abspath("plantuml.jar")
            subprocess.run(
                ["java", "-jar", plantuml_jar, puml_filename, "-tpng", "-o", os.path.abspath(static_dir)],
                check=True,
                capture_output=True
            )
            logger.info(f"Successfully created class_{project_id}.png")
        except Exception as e:
            logger.error(f"PlantUML error: {e}")
            self._create_placeholder(os.path.join(static_dir, f"class_{project_id}.png"), "PlantUML Render Error")

    # Similar methods for use_case, sequence, activity diagrams can be added here following the same pattern.
