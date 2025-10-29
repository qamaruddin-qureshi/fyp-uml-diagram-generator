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

        puml_code = ["@startuml"]
        # Add system boundary
        puml_code.append("rectangle System {")
        # Dynamically extract actors and use cases
        actors = set()
        use_cases = set()
        relationships = []
        for el in elements:
            if el['type'] == 'Class' and el['data'].get('stereotype') == 'actor':
                actors.add(el['data']['name'])
            if el['type'] == 'UseCase':
                # Use PascalCase or verb-noun phrase
                uc_name = el['data']['name']
                uc_name_fmt = re.sub(r'[^a-zA-Z0-9 ]', '', uc_name).title().replace(' ', '')
                use_cases.add(uc_name_fmt)
            if el['type'] == 'Relationship':
                relationships.append(el['data'])
        # Add actors (outside system boundary)
        for actor in sorted(actors):
            puml_code.append(f"actor {actor}")
        # Add use cases (inside system boundary)
        for uc in sorted(use_cases):
            puml_code.append(f'usecase "{uc}" as {uc}')
        # Connect actor to use cases
        for rel in relationships:
            class_a = rel['class_a']
            class_b = rel['class_b']
            class_a_fmt = re.sub(r'[^a-zA-Z0-9 ]', '', class_a).title().replace(' ', '')
            class_b_fmt = re.sub(r'[^a-zA-Z0-9 ]', '', class_b).title().replace(' ', '')
            # Only connect actor to use case
            if class_a_fmt in actors and class_b_fmt in use_cases:
                puml_code.append(f"{class_a_fmt} --> {class_b_fmt}")
        # Optionally infer include/extend relationships contextually
        # Example: if 'login' and 'register' both present, add include
        if 'Login' in use_cases and 'RegisterAccount' in use_cases:
            puml_code.append('Login ..> RegisterAccount : <<include>>')
        puml_code.append("}")
        puml_code.append("@enduml")
        final_puml_code = "\n".join(puml_code)
        puml_filename = os.path.join(puml_dir, f"use_case_{project_id}.puml")
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
            logger.info(f"Successfully created use_case_{project_id}.png")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.error(f"PlantUML error: {e}")
            self._create_placeholder(os.path.join(static_dir, f"use_case_{project_id}.png"), "PlantUML Render Error")


    def generate_sequence_diagram(self, project_id, elements, static_dir, puml_dir):
        logger.info("Starting sequence diagram generation...")
        if not elements:
            self._create_placeholder(os.path.join(static_dir, f"sequence_{project_id}.png"), "No elements extracted.")
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
        for lane in lanes:
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
        class_elements = [el for el in elements if el['type'] == 'Class']
        rel_elements = [el for el in elements if el['type'] == 'Relationship']
        # Add support for AuthenticationService/AccountManager abstraction if present
        service_classes = [el for el in class_elements if el['data']['name'].lower() in ['authenticationservice', 'accountmanager']]
        # Improved attribute/method formatting and naming
        for el in class_elements:
            data = el['data']
            name = data['name']
            alias = self._format_class_name(name)
            stereotype = f"<<{data.get('stereotype')}>>" if data.get('stereotype') else ""
            puml_code.append(f"class \"{name}\" as {alias} {stereotype} {{")
            # Use CamelCase for attributes, consistent visibility
            for attr in data.get('attributes', []):
                attr_fmt = self._format_class_name(attr)
                puml_code.append(f"  -{attr_fmt}: String")
            for method in data.get('methods', []):
                method_fmt = self._format_class_name(method)
                puml_code.append(f"  +{method_fmt}()")
            puml_code.append("}")
        # Add relationships with clear multiplicity and direction
        for el in rel_elements:
            data = el['data']
            class_a_alias = self._format_class_name(data['class_a'])
            class_b_alias = self._format_class_name(data['class_b'])
            card_a = f'"{data.get('card_a', '')}"' if data.get('card_a') else ""
            card_b = f'"{data.get('card_b', '')}"' if data.get('card_b') else ""
            # Add relationship label if present
            label = data.get('label', '')
            rel_line = f"{class_a_alias} {card_a} {data['type']} {card_b} {class_b_alias}"
            if label:
                rel_line += f" : {label}"
            puml_code.append(rel_line)
        puml_code.append("@enduml")
        final_puml_code = "\n".join(puml_code)
        puml_filename = os.path.join(puml_dir, f"class_{project_id}.puml")
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
            logger.info(f"Successfully created class_{project_id}.png")
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.error(f"PlantUML error: {e}")
            self._create_placeholder(os.path.join(static_dir, f"class_{project_id}.png"), "PlantUML Render Error")

    # Similar methods for use_case, sequence, activity diagrams can be added here following the same pattern.
