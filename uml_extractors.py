# uml_extractors.py
"""
Contains all diagram extractor classes for UML model extraction from user stories.
"""
import re
import json
import logging
from scripts.normalize_components import (
    normalize_component_name, 
    normalize_node_name,
    normalize_device_name,
    normalize_environment_name,
    normalize_interface,
    normalize_external_system
)

logger = logging.getLogger(__name__)




class BaseDiagramExtractor:
    def __init__(self, nlp_model, ner_model=None):
        self.nlp = nlp_model
        # Ensure sentencizer is present for sentence segmentation
        if self.nlp and "sentencizer" not in self.nlp.pipe_names:
            try:
                self.nlp.add_pipe("sentencizer")
            except Exception:
                pass

        self.ner_model = ner_model
        self.model_elements = []
        self.found_classes = {}
        self.found_relationships = set()
        self.attribute_patterns = [
            "name", "address", "date", "id", "email", "type", "status", "number", "code",
            "password", "username", "price", "description", "quantity", "totalamount",
            "orderdate", "shippingaddress", "picture", "image", "version"
        ]
        # Common stop words/concepts that shouldn't be classes
        self.class_stop_list = [
            "work", "talks", "articles", "information", "time", "future", "immediate",
            "teammates", "me", "dataset", "version", "versions", "it", "them", "data", "storage",
            "access", "content", "history", "system", "%", "space", "mistake", "mistakes", "interface", 
            "organization", "capacity", "drag-and-drop", "performance", "revenue", "forecast", "value", 
            "pipeline", "interaction", "stage", "potential"
        ]

    def _process_text(self, text):
        """
        Process text. Splitting "so that" to reduce noise in class extraction.
        Returns: (doc_full, doc_core)
        """
        # Split "so that" for core analysis
        core_text = text
        if "so that" in text.lower():
            core_text = text.lower().split("so that")[0]
        elif "to" in text.lower():
            # sometimes "to" acts like "so that" if it's late in sentence? 
            # Risk of cutting "want to". Use rigid "so that" for now.
            pass
            
        doc = self.nlp(text)
        
        # Overlay NER
        if self.ner_model:
            doc_ner = self.ner_model(text)
            new_ents = []
            for ent in doc_ner.ents:
                span = doc.char_span(ent.start_char, ent.end_char, label=ent.label_)
                if span:
                    new_ents.append(span)
            if new_ents:
                try:
                    doc.ents = new_ents
                except:
                    pass # Overlap conflicts
        
        return doc


    def _normalize_name(self, name):
        name = name.strip()
        if name.lower() == "addresses":
             return "Address"
        if name.lower().endswith("esses"): # generalizations
             return name[:-2].capitalize()
        return re.sub(r'([a-z])([A-Z])', r'\1 \2', name).title().replace(" ", "")

    def _add_class(self, name, stereotype=None, source_id=None):
        name = self._normalize_name(name)
        # print(f"DEBUG: Adding class {name}")
        if name not in self.found_classes:

            self.found_classes[name] = {'attributes': [], 'methods': [], 'stereotype': stereotype}
            self.model_elements.append({
                'type': 'Class',
                'data': {'name': name, 'attributes': [], 'methods': [], 'stereotype': stereotype},
                'source_id': source_id
            })

    def _add_attribute(self, class_name, attr_name, source_id, visibility="-", type_hint="String"):
        class_name = self._normalize_name(class_name)
        attr_name = attr_name.lower()
        if class_name in self.found_classes:
            # Check if exists
            existing = [a['name'] for a in self.found_classes[class_name]['attributes']]
            if attr_name not in existing:
                attr_data = {'name': attr_name, 'visibility': visibility, 'type': type_hint}
                self.found_classes[class_name]['attributes'].append(attr_data)
                
                # Update model elements
                for el in self.model_elements:
                    if el['type'] == 'Class' and el['data']['name'] == class_name:
                        el['data']['attributes'] = self.found_classes[class_name]['attributes']

    def _add_method(self, class_name, method_name, source_id, params=None, visibility="+", return_type="void"):
        class_name = self._normalize_name(class_name)
        # method_name = method_name.lower() # Allow camelCase
        if class_name in self.found_classes:
            existing = [m['name'].lower() for m in self.found_classes[class_name]['methods']]
            if method_name.lower() not in existing:
                method_data = {
                    'name': method_name, 
                    'params': params if params else [], 
                    'visibility': visibility, 
                    'return_type': return_type
                }
                self.found_classes[class_name]['methods'].append(method_data)
                
                # Update model elements
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
        actor_set = set()
        class_set = set()
        
        for story in stories_list:
            try:
                text = story.get('storytext', '')
                story_id = story.get('storyid', 0)
                
                # 1. Process text
                doc = self._process_text(text)
                
                # Context split: "As a X, I want to Y [so that Z]"
                # We mainly extract Classes from X and Y. Z is context (unless it mentions known actors).
                parts = re.split(r'so that', text, flags=re.IGNORECASE)
                main_part = parts[0]
                context_part = parts[1] if len(parts) > 1 else ""


                # 2. Identify Actors and Classes (Prioritize NER)
                
                # Get all entities from doc (which has NER overlaid)
                all_ents = [(ent.text, ent.label_) for ent in doc.ents]
                
                current_actors = []
                current_classes = []
                
                # Identify Actors from ANYWHERE in text (including "so that")
                for txt, label in all_ents:
                    norm = self._normalize_name(txt)
                    if label == "ACTOR":
                        current_actors.append(norm)

                # ALWAYS check for "As a X" pattern to capture Administrator even if Model found false positives
                # Allow optional "a/an" for cases like "As Administrator"
                match = re.search(r"As (?:an? )?(.*?)(?:,|$)", text, re.IGNORECASE)
                if match:
                    role = match.group(1).strip()
                    # Clean up role
                    role_clean = self._normalize_name(role)
                    if role_clean not in current_actors:
                        current_actors.append(role_clean)
                        # print(f"DEBUG: Found Actor via Regex: {role_clean}")
                    
                    # Also ensure it's in the model
                    # But we usually add actors at line 249.
                    # We'll just append to current_actors here.

                
                # Identify Classes mainly from MAIN part, but also check NER in context
                # If NER says CLASS in context, it might be valid (e.g. "ReportVersion"?)
                # But be careful of "Talks"
                for txt, label in all_ents:
                    norm = self._normalize_name(txt)
                    if label == "CLASS":
                        if txt.lower() not in self.class_stop_list:
                            # If it's in main part, valid
                            if txt in main_part:
                                current_classes.append(norm)
                            # If it's capitalized in context part, valid?
                            elif txt[0].isupper():
                                current_classes.append(norm)

                # Fallback: Noun chunks from Main Part Only
                main_doc = self.nlp(main_part)
                for token in main_doc:
                    # Candidates for classes: Direct Objects of 'want', 'manage', 'assign', 'view', 'download'
                    if token.dep_ in ["dobj"] and token.head.pos_ == "VERB":
                        # Check redundancy
                        if token.text.lower() in self.attribute_patterns: continue
                        if token.text.lower() in self.class_stop_list: continue
                        
                        # Singularize for Name using NLP Lemma
                        c_name_raw = token.lemma_
                        
                        c_name = self._normalize_name(c_name_raw)

                        # Logic check: "Inspections" -> Class "Inspection"
                        # If the word implies a task/document, it's a class.
                        
                        if c_name not in current_classes and c_name not in current_actors:
                            current_classes.append(c_name)
                    
                    # Check for "Inspector" specifically in main part (if not found by NER)
                    if token.text.lower() == "inspector":
                        if "Inspector" not in current_actors: current_actors.append("Inspector")

                # Check Context Part for "Inspector" fallback
                if context_part:
                    ctx_doc = self.nlp(context_part)
                    for token in ctx_doc:
                        if token.text.lower() == "inspector":
                             if "Inspector" not in current_actors: current_actors.append("Inspector")

                # Deduplicate/Merge Logic

                # "Supervisor" might be "InspectionStaffSupervisor"
                # If we have "InspectionStaffSupervisor" in actors, and "Supervisor" in classes, drop "Supervisor"
                final_classes = []
                for c in current_classes:
                    is_duplicate = False
                    for a in current_actors:
                        if c.lower() in a.lower() and len(a) > len(c):
                            is_duplicate = True # "Supervisor" is inside "InspectionStaffSupervisor"
                    if not is_duplicate:
                        final_classes.append(c)
                current_classes = final_classes

                # Add Actors
                for actor in current_actors:
                    if actor not in self.found_classes:


                        # New Actor
                        self.model_elements.append({
                            'type': 'Class',
                            'data': {'name': actor, 'stereotype': 'actor', 'attributes': [], 'methods': []},
                            'source_id': story_id
                        })
                        self.found_classes[actor] = {'attributes': [], 'methods': [], 'stereotype': 'actor'}
                    else:
                        # Existing Actor, just ensure stereotype is set/updated if needed
                        pass

                # Add Classes
                for cls in current_classes:
                    if cls not in actor_set: # Don't double add functionality
                         self._add_class(cls, source_id=story_id)

                # 3. Attributes/Methods from Main Part
                subject_entity = current_actors[0] if current_actors else None
                
                # Resolve subject "I"
                subject_entity = None
                if "I" in [t.text for t in doc] or "i" in [t.text for t in doc]:
                    if current_actors:
                        subject_entity = current_actors[0]
                
                # Check explicit nsubj
                if not subject_entity:
                    for token in main_doc:
                        if token.dep_ == "nsubj" and token.head.pos_ == "VERB":
                             if token.text in current_actors:
                                 subject_entity = token.text
                                 break
                
                # Analyze verbs in main doc
                for token in main_doc:
                    if token.pos_ == "VERB" and token.lemma_ not in ["want", "be", "have", "can", "use", "make"]:
                        method_name = token.text
                        
                        if not subject_entity: continue
                        
                        # Find objects (dobj + conj)
                        objects = []
                        for child in token.children:
                            if child.dep_ in ["dobj", "attr"]:
                                objects.append(child)
                                # Traverse conjunctions
                                cur = child
                                while True:
                                    found_conj = None
                                    for gc in cur.children:
                                        if gc.dep_ == "conj":
                                            objects.append(gc)
                                            found_conj = gc
                                            break
                                    if found_conj:
                                        cur = found_conj
                                    else:
                                        break
                        
                        if not objects: continue

                        params = []
                        final_method_name = method_name

                        for obj_token in objects:
                            # Construct name from compound + head
                            # e.g. "profile picture" -> "picture" head, "profile" compound
                            # We want "ProfilePicture"
                            
                            sub_compounds = [c.text for c in obj_token.children if c.dep_ == "compound"]
                            full_name_list = sub_compounds + [obj_token.lemma_] # Use lemma for head (e.g. Interactions -> Interaction)
                            sub_obj = " ".join(full_name_list) # "profile picture"
                            
                            # Original text for attributes (with adjs etc)
                            obj_text_subtree = "".join([c.text_with_ws for c in obj_token.subtree]).strip()

                            # Refine Method Name based on Object
                            low_sub = sub_obj.lower()
                            if method_name.lower() == "set" and "reminder" in low_sub:
                                final_method_name = "setReminder"
                            elif method_name.lower() == "assign" and "ownership" in low_sub:
                                final_method_name = "assignOwnership"
                            elif method_name.lower() == "send" and "email" in low_sub:
                                final_method_name = "sendEmail"
                            elif method_name.lower() == "export" and ("lead" in low_sub or "lead" in obj_text_subtree.lower()):
                                final_method_name = "exportLeads"


                                
                            # Check if it is an attribute
                            is_attr = False
                            for attr in self.attribute_patterns:
                                # "profile picture" contains "picture"
                                if attr in sub_obj.lower() and sub_obj.lower() not in ["contact", "structure", "communication", "account", "ownership", "reminder", "opportunity", "lead"]:
                                    # Special check for "track version" -> this is a relationship, not attribute
                                    if "version" in attr and method_name.lower() == "track":
                                        is_attr = False
                                        break
                                    
                                    # Special check for "send email" -> method, not attribute
                                    if "email" in attr and "send" in method_name.lower():
                                        is_attr = False
                                        break

                                    # Special check for "versions of report"
                                    if "version" in attr and "report" in obj_text_subtree.lower():
                                        # This is likely ReportVersion class reference
                                        is_attr = False 
                                        # We want to treat this as a link to ReportVersion
                                        found_match = "ReportVersion"
                                        # Ensure ReportVersion class exists
                                        if "ReportVersion" not in self.found_classes:
                                            self._add_class("ReportVersion", source_id=story_id)
                                        
                                        # Relationship: Report *-- ReportVersion (Composition)
                                        # But the text says "I want to view versions...".
                                        # So Patron ..> ReportVersion (Dependency/Usage, "view" -> Dependency)
                                        
                                        params.append({'name': sub_obj, 'type': "ReportVersion", 'direction': 'in'})
                                        self._add_relationship(subject_entity, "ReportVersion", 'Dependency', source_id=story_id)
                                        
                                        # Implicit Composition: Report composed of Version
                                        if "Report" in self.found_classes:
                                            self._add_relationship("Report", "ReportVersion", "Composition", source_id=story_id)

                                        break
                                    
                                    is_attr = True
                                    # Clean up "my"
                                    clean_attr = re.sub(r'\b(my|the|a|an)\b', '', sub_obj, flags=re.IGNORECASE).strip()
                                    self._add_attribute(subject_entity, clean_attr, story_id, visibility="-", type_hint="String")
                                    break
                            
                            if not is_attr:

                                # It might be a Class Reference!
                                # Logic to determine Relationship Type
                                rel_type = "Dependency" # Default weak
                                
                                # Check subtree for "associated with" (Run for ALL verbs)
                                # Check subtree for "associated with" (Run for ALL verbs)
                                # "contacts associated with a specific company"
                                for t in obj_token.subtree:
                                    if (t.lemma_ == "associate" or t.text == "associated"):
                                         # Check for 'with' in children of 'associate' token
                                         for gchild in t.children:
                                             if gchild.dep_ == "prep" and gchild.text == "with":
                                                 for gg in gchild.children:
                                                     if gg.dep_ == "pobj":
                                                         # Reconstruct target name (Company / Account)
                                                         assoc_compounds = [c.text for c in gg.children if c.dep_ == "compound"]
                                                         assoc_full = assoc_compounds + [gg.lemma_]
                                                         assoc_target = self._normalize_name(" ".join(assoc_full))
                                                         
                                                         # If (Account) is present as appos?
                                                         # check children of gg for appos
                                                         for ggg in gg.children:
                                                             if ggg.dep_ == "appos":
                                                                 assoc_target = self._normalize_name(ggg.lemma_)
                                                         
                                                         # Link Object (Contact) --> Target (Account)
                                                         src_cls = self._normalize_name(sub_obj) # "Contact"
                                                         self._add_relationship(src_cls, assoc_target, "Association", source_id=story_id)
                                                         if assoc_target not in self.found_classes:
                                                             self._add_class(assoc_target, source_id=story_id)

                                # "Assign", "Manage", "Has", "Upload", "Share", "Send" -> Association

                                if method_name.lower() in ["assign", "manage", "create", "have", "owns", "upload", "share", "send"]:
                                    rel_type = "Association"
                                    
                                    # Special Check: Assign/Share/Send TO WHO?
                                    # Look for 'dative' or 'prep' (to) children of the verb
                                    for child in token.children:
                                        if method_name.lower() == "assign":
                                             pass
                                        if child.dep_ == "dative" or (child.dep_ == "prep" and child.text == "to"):
                                             # Found target
                                             target_text = ""
                                             if child.dep_ == "dative":
                                                 target_text = child.text
                                             else:
                                                 # Get pobj
                                                 for p in child.children:
                                                     # print(f"DEBUG: Prep Child: {p.text} ({p.dep_})")
                                                     if p.dep_ == "pobj":
                                                         target_text = p.lemma_ # Use lemma e.g. "Sales Rep"
                                             
                                             if target_text:
                                                 # Normalize
                                                 target_norm = self._normalize_name(target_text)
                                                 self._add_relationship(subject_entity, target_norm, "Association", source_id=story_id)
                                                 if target_norm not in self.found_classes: self._add_class(target_norm, source_id=story_id)

                                    # Check children of OBJECT for 'to' (e.g. assign ownership TO Rep) - RECURSIVE
                                    if method_name.lower() in ["assign", "send"]:
                                        # BFS/DFS for 'prep' 'to' in subtree
                                        to_target_token = None
                                        q = [obj_token]
                                        visited = {obj_token}
                                        while q:
                                            curr = q.pop(0)
                                            if curr.dep_ == "prep" and curr.text == "to":
                                                 for p in curr.children:
                                                     if p.dep_ == "pobj":
                                                         to_target_token = p
                                                 if to_target_token: break
                                            
                                            for c in curr.children:
                                                if c not in visited:
                                                    visited.add(c)
                                                    q.append(c)
                                        
                                        if to_target_token:
                                             # Reconstruct full name (Sales Rep)
                                             t_compounds = [c.text for c in to_target_token.children if c.dep_ == "compound"]
                                             t_full = t_compounds + [to_target_token.lemma_]
                                             target_text = self._normalize_name(" ".join(t_full))
                                             
                                             self._add_relationship(subject_entity, target_text, "Association", source_id=story_id)
                                             if target_text not in self.found_classes: self._add_class(target_text, source_id=story_id)

                                    # Fallback: specific mentions of "User" or Actors (Existing logic)
                                    # Restore Logic: Link distinct actors mentioned in sentence if not already linked
                                    for actor in current_actors:
                                        if actor != subject_entity and actor != "User": 
                                             # Ensure we don't duplicate logic if "To" search found it
                                             # But duplicates are handled by _add_relationship usually
                                             self._add_relationship(subject_entity, actor, "Association", source_id=story_id)
                                             if actor not in self.found_classes:
                                                 self._add_class(actor, source_id=story_id)

                                
                                # Check for spatial prepositions => Folder containment
                                # "upload files INTO folder", "create folder WITHIN storage"
                                # Look at children of the verb (method_name)
                                # Find 'prep' children
                                for child in doc:
                                    if child.head.text == method_name and child.dep_ == "prep":
                                        if child.text in ["into", "within", "inside", "in"]:
                                             # Get pobj
                                             for grandchild in child.children:
                                                 if grandchild.dep_ == "pobj":
                                                     container_name = self._normalize_name(grandchild.lemma_)
                                                     # If container is a class, link sub_obj to container
                                                     # e.g. upload File into Folder => Folder o-- File (Aggregation/Composition)
                                                     # But we have subject_entity (User) doing action. 
                                                     # Relationship: Container contains Item.
                                                     # We have 'sub_obj' (File) and 'container_name' (Folder).
                                                     
                                                     # Add the container class if distinct
                                                     if container_name != subject_entity and container_name.lower() not in self.class_stop_list:
                                                         self._add_class(container_name, source_id=story_id)
                                                         # Folder o-- File
                                                         # Singularize sub_obj for better diagram
                                                         singular_sub = self._normalize_name(sub_obj)

                                                         
                                                         self._add_relationship(container_name, singular_sub, "Aggregation", source_id=story_id)

                                
                                # Check for Composition/Aggregation keywords in obj_text
                                # "list of", "collection of" -> Aggregation
                                if "list of" in obj_text_subtree.lower() or "collection of" in obj_text_subtree.lower():
                                    rel_type = "Aggregation"
                                
                                # Try to find matching class
                                found_match = None
                                singular_obj = self._normalize_name(sub_obj)

                                
                                for c in current_classes:
                                    if c.lower() in sub_obj.lower() or c.lower() == singular_obj.lower():
                                        found_match = c
                                        break
                                        
                                if found_match:
                                    # It's a relationship
                                    params.append({'name': sub_obj, 'type': found_match, 'direction': 'in'})
                                    self._add_relationship(subject_entity, found_match, rel_type, source_id=story_id)
                                else:
                                    # Check if we should create a Class on the fly
                                    # Heuristic: Uppercase or Plural of a Noun
                                    # "Inspections" -> Inspection
                                    is_potential_class = False
                                    potential_name = self._normalize_name(singular_obj)

                                    
                                    # If capitalized or endswith 's' and length > 2 avoiding trivial words
                                    if (singular_obj[0].isupper() or len(singular_obj) > 2) and singular_obj.lower() not in self.attribute_patterns and singular_obj.lower() not in self.class_stop_list:
                                        # Special case: "Inspections"
                                        if method_name.lower() in ["assign", "manage", "create", "upload", "download", "share", "view"]:
                                             is_potential_class = True

                                        rel_type = "Association" # Stronger
                                        
                                        if method_name.lower() in ["view", "download"]:
                                            rel_type = "Dependency"
                                    
                                    if is_potential_class:
                                        # Create new Class
                                        potential_name = self._normalize_name(potential_name)
                                        if potential_name not in self.found_classes:
                                            self._add_class(potential_name, source_id=story_id)
                                        
                                        params.append({'name': sub_obj, 'type': potential_name, 'direction': 'in'})
                                        self._add_relationship(subject_entity, potential_name, rel_type, source_id=story_id)
                                    else:
                                        # Just a param
                                        params.append({'name': sub_obj, 'type': 'String', 'direction': 'in'})

                        # Update method name if refined
                        method_name = final_method_name

                        # Check for "mark as..." pattern
                        if method_name.lower() == "mark":
                             for child in token.children:
                                 if child.dep_ == "prep" and child.text == "as":
                                     for gchild in child.children:
                                         if gchild.dep_ == "pobj":
                                             status_val = self._normalize_name(gchild.text)
                                             method_name = f"markAs{status_val}"

                        # --- ADVANCED LOGIC: Search, Permissions, Versioning ---
                        
                        # 1. Search Logic: "search for files by name"
                        if method_name.lower() in ["search", "locate", "find"]:
                             # Return type is the object being searched (dobj)
                             # "search for files" -> files
                             return_type = "List<String>"
                             # Try to find the object
                             for child in token.children:
                                 if child.dep_ == "prep" and child.text == "for":
                                     for gchild in child.children:
                                         if gchild.dep_ == "pobj":
                                              found_type = self._normalize_name(gchild.text)
                                              return_type = f"List<{found_type}>"
                             
                             # Parameters: "by name or content"
                             # Usually attached as prep "by"
                             search_params = []
                             for child in token.children:
                                 if child.dep_ == "prep" and child.text == "by":
                                     # Get children of 'by' (pobj + conj)
                                     for gchild in child.children:
                                         if gchild.dep_ in ["pobj", "conj", "dobj"]:
                                              # Recurse for conj
                                              search_params.append({'name': gchild.text, 'type': 'String', 'direction': 'in'})
                                              for ggchild in gchild.children:
                                                  if ggchild.dep_ == "conj":
                                                      search_params.append({'name': ggchild.text, 'type': 'String', 'direction': 'in'})
                             
                             if search_params:
                                 params = search_params
                             
                             # Add method
                             self._add_method(subject_entity, method_name, story_id, params, visibility="+", return_type=return_type)

                             # NLP RELATIONSHIP: User depends on the object they are searching for
                             # If we found a type (e.g. Files), add dependency
                             if "List<" in return_type:
                                 target_type = return_type.replace("List<", "").replace(">", "")
                                 if target_type not in ["String", "int", "void"]:
                                     self._add_relationship(subject_entity, target_type, "Dependency", source_id=story_id)

                             continue # Skip default add
                        
                        # 2. Permissions Logic: "set permissions (Read-Only or Edit)"
                        if "permission" in obj_text_subtree.lower() or method_name.lower() == "control":
                             # Check for parenthetical values in text
                             perm_match = re.search(r'\((.*?)\)', text)
                             if perm_match:
                                 # (Read-Only or Edit)
                                 values = perm_match.group(1)
                                 # Add as a comment or note (PlantUML usually requires a Note, but here we can add a constrained param)
                                 params.append({'name': 'permissions', 'type': f"Enum{{{values}}}", 'direction': 'in'})
                        
                        # Add method to Actor
                        self._add_method(subject_entity, method_name, story_id, params, visibility="+", return_type="void") 
                        
                        # 3. Versioning Logic: "track version history"
                        # "track" verb. object "history". attribute "version"
                        if method_name.lower() == "track" and "history" in obj_text_subtree.lower():
                            # Implies File *-- Version
                            # Add "Version" class
                            self._add_class("Version", source_id=story_id)
                            self._add_attribute("Version", "timestamp", story_id)
                            self._add_attribute("Version", "author", story_id)
                            self._add_attribute("Version", "changeLog", story_id)
                            
                            # Ensure File exists (should be found from "for files")
                            # "history for files"
                            for child in token.children: # track
                                for gchild in child.children: # history -> prep -> files
                                     if gchild.dep_ == "pobj" and gchild.head.text == "for":
                                          file_class = self._normalize_name(gchild.text)
                                          self._add_class(file_class, source_id=story_id)
                                          # File *-- Version
                                          self._add_relationship(file_class, "Version", "Composition", source_id=story_id)
                                          # NLP RELATIONSHIP: User -> File (Dependency - tracking history OF file)
                                          self._add_relationship(subject_entity, file_class, "Dependency", source_id=story_id)

                            # Add default Version operations
                            self._add_method("Version", "getDetails", story_id, [], visibility="+", return_type="String")
                            self._add_method("Version", "restore", story_id, [], visibility="+", return_type="void")

                            # NLP RELATIONSHIP: User -> Version (Association - User tracks Version)
                            self._add_relationship(subject_entity, "Version", "Association", source_id=story_id)
                            
                            # Add 'revert' operation if context implies
                            if "revert" in text.lower():
                                self._add_method(subject_entity, "revert", story_id, [{'name': 'toVersion', 'type': 'Version'}], visibility="+")

                        # 4. Storage Management Logic: "Trash", "Recycle Bin", "Move"
                        if "trash" in text.lower() or "recycle bin" in text.lower():
                            # Extract Trash/Recycle Bin as a class
                            trash_name = "RecycleBin" if "recycle bin" in text.lower() else "Trash"
                            self._add_class(trash_name, source_id=story_id)
                            # User uses Trash (to recover/delete)
                            self._add_relationship(subject_entity, trash_name, "Dependency", source_id=story_id)
                            
                            if "recover" in method_name.lower():
                                self._add_method(subject_entity, "recover", story_id, [{'name': 'files', 'type': 'File'}, {'name': 'from', 'type': trash_name}], visibility="+")
                                # Trash has 'restore' potentially
                                self._add_method(trash_name, "restore", story_id, [{'name': 'file', 'type': 'File'}], visibility="+")
                        
                        if method_name.lower() == "move":
                             # "move file from folder to folder"
                             # Dependency on Folder
                             self._add_relationship(subject_entity, "Folder", "Dependency", source_id=story_id)
                             # Ensure Folder class exists
                             if "Folder" not in self.found_classes:
                                 self._add_class("Folder", source_id=story_id)

                        # Alert Logic: "alert user when..."
                        if method_name.lower() == "alert":
                            # System alerts User
                            if subject_entity == "System": # Should be System
                                 for actor in current_actors:
                                     if actor != "System":
                                         self._add_relationship("System", actor, "Dependency", source_id=story_id)
                                         params.append({'name': 'user', 'type': actor, 'direction': 'in'})
                                         # Add condition param if found
                                         if "capacity" in text.lower():
                                              params.append({'name': 'condition', 'type': 'String', 'direction': 'in'})

                        # Generic "Manage" Logic
                        if method_name.lower() == "manage":
                             # "manage my Addresses", "manage a Product"
                             # Extract object from NLP dobj
                             for token in doc:
                                 if token.text.lower() == "manage":
                                     for child in token.children:
                                         if child.dep_ == "dobj":
                                             target_cls = self._normalize_name(child.text)
                                             if target_cls.lower() not in self.class_stop_list:
                                                  self._add_class(target_cls, source_id=story_id)
                                                  self._add_relationship(subject_entity, target_cls, "Dependency", source_id=story_id)
                                                  # Add CRUD methods to the target class?
                                                  self._add_method(target_cls, "create", story_id, visibility="+")
                                                  self._add_method(target_cls, "update", story_id, visibility="+")
                                                  self._add_method(target_cls, "delete", story_id, visibility="+")

                        # 5. CRM Logic
                        # Activity
                        if "activity" in text.lower() or method_name.lower() == "log":
                             # "log an activity (call, email)"
                             self._add_class("Activity", source_id=story_id)
                             # User -> Activity (Association/Creation)
                             self._add_relationship(subject_entity, "Activity", "Association", source_id=story_id)
                             # Subtypes? (call, email) - treat as attributes context for now or just generic Activity

                             # Check for "against" relationship (log activity against contact)
                             for token in doc:
                                 if token.text.lower() in ["log", "activity"]:
                                     for child in token.children:
                                         if child.dep_ == "prep" and child.text == "against":
                                             for gchild in child.children:
                                                 if gchild.dep_ in ["pobj", "dobj"]: # "against contact"
                                                      targets = [gchild]
                                                      # Check conjunctions (contact OR account)
                                                      for ggchild in gchild.children:
                                                          if ggchild.dep_ == "conj":
                                                              targets.append(ggchild)
                                                      
                                                      for target in targets:
                                                          target_obj = self._normalize_name(target.text)
                                                          # Activity -> Target
                                                          self._add_relationship("Activity", target_obj, "Association", source_id=story_id)
                                                          # Ensure target class exists if reasonable
                                                          if target_obj.lower() not in self.class_stop_list:
                                                              self._add_class(target_obj, source_id=story_id)
                             
                        # Dashboard
                        if "dashboard" in text.lower() and method_name.lower() == "view":
                             self._add_class("Dashboard", source_id=story_id)
                             self._add_relationship(subject_entity, "Dashboard", "Dependency", source_id=story_id)
                             # dashboard of what?
                             for token in doc:
                                 if token.text.lower() == "dashboard":
                                     for child in token.children:
                                         if child.dep_ == "prep" and child.text == "of":
                                             for gchild in child.children:
                                                 if gchild.dep_ == "pobj":
                                                      # dashboard of sales pipeline?
                                                      # if pipeline is stopped, we won't find it as a class, but we can note it?
                                                      # Actually, just Dashboard is fine for now. 
                                                      pass

                # 4. Relationships & Inheritance
                # Actor uses Class
                if subject_entity and current_classes:
                    for cls in current_classes:
                        if cls != subject_entity:
                             # Base generic connection? We might have added specific ones above.
                             pass

                # Explicit Inheritance REMOVED from per-story loop.
                # Moved to Post-Processing to only apply if "User" actor actually exists in the stories.


            except Exception as e:
                logger.error(f"Class extraction error: {e}")
                continue

                
        # Post-Processing: Connect specific classes
        
        # Dynamic Inheritance: If "User" actor was found in ANY story, make all other actors inherit from it.
        # If "User" was NOT found (e.g. CRM/Ecommerce), do NOT force it.
        if "User" in self.found_classes:
            for cls_name, cls_data in self.found_classes.items():
                if cls_data.get('stereotype') == 'actor' and cls_name != "User" and cls_name != "System":
                    # Check if relationship already exists? _add_relationship handles duplication check but we need source_id?
                    # We can use 0 or the first source_id of the class.
                    # We don't store source_id in found_classes directly, but we can assume generic 0 or find it.
                    # Actually _add_relationship appends to model_elements.
                    # Check if already linked? (Likely not, since we removed the per-story logic).
                    self._add_relationship(cls_name, "User", "Inheritance", source_id=0) # source_id 0 for system-inferred

        
        # New Post-Processing: Add default attributes to Actors if missing
        for cls_name, cls_data in self.found_classes.items():
            # Check if it is an actor (inheritance to User or stereotype)
            is_actor = cls_data.get('stereotype') == 'actor'
            
            if not cls_data['attributes']:
                if is_actor:
                     # Inject defaults for Actors
                     defaults = ["id", "name", "email"]
                     for d in defaults:
                         self._add_attribute(cls_name, d, source_id=0, visibility="-", type_hint="String")
                     
                     # Check if Actor has methods. If not, add actor-specific defaults?
                     if not cls_data['methods']:
                         if "inspector" in cls_name.lower():
                             self._add_method(cls_name, "receiveWork", 0, params=[{'name':'assignment', 'type':'Inspection', 'direction':'in'}], visibility="+", return_type="void")
                             self._add_method(cls_name, "updateStatus", 0, visibility="+", return_type="void")
                         elif "researcher" in cls_name.lower():
                             self._add_method(cls_name, "login", 0, visibility="+", return_type="void")
                         elif cls_name == "User":
                             self._add_method(cls_name, "login", 0, visibility="+", return_type="void")
                             self._add_method(cls_name, "logout", 0, visibility="+", return_type="void")

                elif not is_actor:
                    # Passive Classes / Objects
                    # Domain Heuristics
                    defaults = []
                    cn_lower = cls_name.lower()
                    
                    if "version" in cn_lower:
                        defaults = ["versionNumber", "changeLog", "releaseDate"]
                    elif "report" in cn_lower or "article" in cn_lower:
                        defaults = ["title", "content", "publishedDate", "author"]
                    elif "inspection" in cn_lower:
                        defaults = ["status", "scheduledDate", "result", "location"]
                    elif "file" in cn_lower:
                        defaults = ["name", "size", "type", "path"]
                    elif "folder" in cn_lower:
                        defaults = ["name", "path", "itemCount"]
                    elif "link" in cn_lower:
                        defaults = ["url", "expiryDate", "permissions"]
                    elif "contact" in cn_lower:
                        defaults = ["name", "phone", "email", "company"]
                    elif "opportunity" in cn_lower or "lead" in cn_lower:
                        defaults = ["stage", "value", "closeDate", "probability"]
                    elif "account" in cn_lower:
                        # Context Check: CRM vs Generic
                        has_crm = any("lead" in c.lower() or "opportunity" in c.lower() for c in self.found_classes)
                        if has_crm:
                             defaults = ["name", "industry", "location"]
                        else:
                             defaults = ["username", "password", "email"]
                    elif "activity" in cn_lower:
                        defaults = ["type", "date", "notes", "duration"]
                    elif "reminder" in cn_lower:
                        defaults = ["date", "time", "note", "status"]
                    elif "campaign" in cn_lower:
                        defaults = ["name", "budget", "startDate", "endDate", "type"]
                    elif "email" in cn_lower:
                        defaults = ["subject", "body", "recipient", "sender", "date"]
                    else:
                        defaults = ["id", "description"]
                    
                    for d in defaults:
                        self._add_attribute(cls_name, d, source_id=0, visibility="-", type_hint="String")
                    
                    # Add refined operations for Entities
                    ops = []
                    if "version" in cn_lower:
                        ops = ["download", "restore", "diff"]
                    elif "inspection" in cn_lower:
                        ops = ["complete", "cancel", "updateResult"]
                    elif "report" in cn_lower:
                         ops = ["publish", "archive", "export", "save", "delete"]
                    elif "file" in cn_lower:
                         ops = ["open", "edit", "share", "download"]
                    elif "folder" in cn_lower:
                         ops = ["addFile", "removeFile", "listContents"]
                    else:
                        ops = ["save", "delete"]

                    for op in ops:
                        self._add_method(cls_name, op, 0, visibility="+", return_type="void")
        
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

    def _clean_use_case_name(self, text):
        """
        Clean use case names:
        1. Remove parenthetical content entirely FIRST (handles e.g. correctly).
        2. Remove 'so that', 'so', 'in order to', etc. (Truncate)
        3. Split on punctuation (.,) to handle clauses.
        """
        # 1. Parenthesis Removal: Remove ( ... )
        # Using a loop to handle nested/multiple parens if needed, but regex is fine for simple levels.
        # Note: This removes (e.g. ...) so the '.' inside is gone.
        text = re.sub(r'\s*\(.*?\)', '', text)

        # 2. Truncation Keywords
        stops = [" so that ", " in order to ", " so ", " when ", " using ", " to get ", " because "]
        lower_text = text.lower()
        
        min_idx = len(text)
        found_stop = False
        for stop in stops:
            idx = lower_text.find(stop)
            if idx != -1 and idx < min_idx:
                min_idx = idx
                found_stop = True
        
        if found_stop:
            text = text[:min_idx]

        # 3. Split on punctuation (.,) after parens/stops are gone
        # This handles "Process match. Then..." or "Process match, and..."
        # But be careful of "Process X, Y, and Z". Use case names shouldn't usually be lists?
        # If we split on comma, "Process X, Y" becomes "Process X".
        # User stories: "want to X, so that..." -> Comma handled by 'so that' usually?
        # If "want to X, Y, Z". Splitting on comma is aggressive.
        # But for "Log an activity (e.g. ...)", we want "Log an activity".
        # Current issue was splitting on '.' inside parens.
        # Now parens are gone.
        # Leaving comma might be safer, unless it separates clauses?
        # Let's strip trailing punctuation only, and let 'stops' handle clauses.
        # If "want to log activity. Then I..." -> "log activity."
        
        # New approach: Don't split on comma inside list? Hard.
        # Let's relying on 'stops'. If no stop, keep text?
        # But "want to X. Then Y." -> "X. Then Y."
        # We should split on '.' for sure.
        if '.' in text:
            text = text.split('.')[0]
            
        return text.strip(" ,;:").capitalize()

    def _extract_use_cases(self, story_id, text):
        try:
            logger.info(f"Extracting use cases for story {story_id}")
            data = {}
            if text and isinstance(text, str):
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    pass
            
            use_case_name = None
            primary_actors = []

            # 1. Try to get data from the Model Output (Primary)
            # We will gather candidates from Model AND Regex, then dedupe.
            found_primary_candidates = set()
            
            if 'groq_output' in data and 'use_case' in data['groq_output']:
                raw_name = data['groq_output']['use_case']
                use_case_name = self._clean_use_case_name(raw_name)
                
                actor_name = data['groq_output'].get('actor')
                if actor_name:
                    found_primary_candidates.add(actor_name)
            
            # 2. Always run Regex/NER to ensure we don't miss obvious actors (like 'Customer' in E-commerce)
            # even if Model output was present but incomplete.
            
            # NER
            doc = self._process_text(text)
            for ent in doc.ents:
                if ent.label_ == "ACTOR":
                    found_primary_candidates.add(ent.text)
            
            # "As a X" Regex (High Confidence)
            actor_match = re.search(r"As (?:an? )?(.*?)(?:,|$)", text, re.IGNORECASE)
            if actor_match:
                actor_clean = actor_match.group(1).strip()
                if actor_clean:
                    found_primary_candidates.add(actor_clean)

            # Use Case Name Regex (Backup if Model failed)
            if not use_case_name:
                match = re.search(r"want to\s+(.*)", text, re.IGNORECASE)
                if match:
                    raw_name = match.group(1)
                    use_case_name = self._clean_use_case_name(raw_name)

            if use_case_name:
                self.model_elements.append({
                    'type': 'UseCase',
                    'data': {'name': use_case_name},
                    'source_id': story_id
                })
                
                # Add/Link Primary Actors
                for actor in found_primary_candidates:
                    actor = actor.strip()
                    if not actor: continue
                    
                    # Suppress 'System' as a primary user actor (usually redundant or internal)
                    if actor.lower() == 'system':
                        continue

                    self._add_class(actor, stereotype="actor", source_id=story_id)
                    primary_actors.append(actor)
                    
                    self._add_relationship(actor, use_case_name, "-->", source_id=story_id)
                    # logger.info(f"DEBUG: Linked Primary {actor} -> {use_case_name}")

                # Secondary Actor Detection (Target Detection)
                # Re-scan for OTHER actors
                all_found_actors = set()
                # (Re-using doc from above)
                for ent in doc.ents:
                    if ent.label_ == "ACTOR":
                        all_found_actors.add(ent.text)
                
                common_actors = ["User", "System", "Administrator", "Manager", "Customer", "Sales Rep", "SalesRep", "Staff", "Supervisor", "Researcher", "Patron", "Contact"]
                for ca in common_actors:
                    if re.search(r'\b' + re.escape(ca) + r'\b', text, re.IGNORECASE):
                        all_found_actors.add(ca)

                # Filter secondary actors
                for actor in all_found_actors:
                    actor = actor.strip()
                    if not actor: continue 
                    
                    # Suppress System in secondary too?
                    if actor.lower() == 'system':
                        continue

                    # 1. Self-Check: Don't link if it IS the primary actor
                    # Use Case-Insensitive check
                    is_primary = False
                    for p in primary_actors:
                        if p.lower() == actor.lower():
                            is_primary = True
                            break
                    if is_primary:
                        continue
                        
                    # 2. Overlap Check
                    is_substring = False
                    for primary in primary_actors:
                        if actor in primary or primary in actor: 
                             if len(actor) < len(primary):
                                 is_substring = True
                    
                    if is_substring:
                        continue

                    self._add_class(actor, stereotype="actor", source_id=story_id)
                    self._add_relationship(actor, use_case_name, "-->", source_id=story_id)

        except Exception as e:
            logger.error(f"Use case extraction error for story {story_id}: {e}")

    def _add_relationship(self, source, target, rel_type="-->", card_a=None, card_b=None, source_id=None):
        """
        Override relationship addition for Use Case diagrams.
        - Source (Actor) MUST be normalized (as it was added via _add_class).
        - Target (Use Case) MUST NOT be normalized (it keeps spaces).
        """
        # Normalize Source (Actor)
        source = self._normalize_name(source)
        # Keep Target (Use Case) as is (Cleaned but not PascalCased)
        target = target.strip() 
        
        rel_key = (source, target, rel_type)
        if rel_key not in self.found_relationships:
            self.found_relationships.add(rel_key)
            self.model_elements.append({
                'type': 'Relationship',
                'data': {'class_a': source, 'class_b': target, 'type': rel_type, 'card_a': card_a, 'card_b': card_b},
                'source_id': source_id
            })




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
                doc = self._process_text(text)
            
                # Find all potential objects (Actors or Classes)

                participants = [ent.text for ent in doc.ents if ent.label_ in ["ACTOR", "CLASS"]]
                
                sender = "User"
                receiver = "System"
                
                # First entity is sender. If there is a second entity, it's the receiver.
                if participants:
                    sender = participants[0]
                    if len(participants) > 1:
                        receiver = participants[1]
                
                # Extract the message (action)
                message = "process request" # Default
                if "want to" in text.lower():
                    # Get text after 'want to'
                    parts = re.split(r"want to", text, flags=re.IGNORECASE)
                    if len(parts) > 1:
                        # Clean up: remove trailing punctuation
                        message = parts[1].split('.')[0].split(',')[0].strip()
                
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
            else:   # FALLBACK LOGIC (when groq_output is missing)
                doc = self._process_text(text)
                lanes = [ent.text for ent in doc.ents if ent.label_ == "ACTOR"]

                if not lanes:
                    lanes = ["User"] # Default to User if no actor found
                
                current_lane = lanes[0]
                
                # IMPROVED REGEX (Capture everything after "want to" until a comma or period)
                steps = re.findall(r"want to\s+(.*?)(?:,|$|\.)", text, re.IGNORECASE)
                
                for step in steps:
                    self.model_elements.append({
                        'type': 'ActivityStep',
                        'data': {'lane': current_lane, 'step': step.strip().capitalize()},
                        'source_id': story_id
                    })
        except Exception as e:
            logger.error(f"Activity extraction error for story {story_id}: {e}")




class ComponentDiagramExtractor(BaseDiagramExtractor):
    """
    Extracts components, interfaces, and relationships for component diagrams.
    Requires architectural narration as input.
    """
    def __init__(self, nlp_model, ner_model=None, tech_mappings_path="technology_mappings.json"):
        super().__init__(nlp_model, ner_model)
        self.components = {}  # {name: {stereotype, interfaces, dependencies, parent_package, ports}}
        self.external_systems = set()
        self.interfaces = {}  # {name: type (provided/required)}
        self.packages = {}    # {name: [components]}
        self.ports = {}       # {component_name: [ports]}
        self.relationships = []
        
        # Load technology mappings
        self.tech_mappings = {}
        self.relationship_keywords = {}
        try:
            with open(tech_mappings_path, 'r') as f:
                mappings = json.load(f)
                self.tech_mappings = mappings.get('component_stereotypes', {})
                self.relationship_keywords = mappings.get('relationship_keywords', {})
                self.component_keywords = mappings.get('component_keywords', [])
        except Exception as e:
            logger.error(f"Failed to load technology mappings: {e}")
    
    def _process_text(self, text):
        """
        Process text with dependency parser and custom NER.
        Ensures both dependency tree (from parsing model) and entities (from NER model) are present.
        """
        import spacy
        
        # 1. Parsing Model (Dependencies)
        if not hasattr(self, 'parser_model'):
            try:
                # Prefer the large model if available (consistent with rest of project)
                logger.info("Loading en_core_web_lg for dependency parsing...")
                self.parser_model = spacy.load("en_core_web_lg")
            except OSError:
                try:
                    logger.warning("en_core_web_lg not found, falling back to en_core_web_sm")
                    self.parser_model = spacy.load("en_core_web_sm")
                except OSError:
                    logger.warning("no standard spaCy model found, falling back to blank model (no deps)")
                    self.parser_model = spacy.blank("en")
        
        # Use parser model for Doc creation (tokens + deps)
        doc = self.parser_model(text)
        
        # 2. NER Model (Entities)
        # Apply custom NER entities to the parsed doc
        if self.ner_model:
            try:
                ner_doc = self.ner_model(text)
                
                # Filter compatible spans
                new_ents = []
                for ent in ner_doc.ents:
                    # Snap to tokens in the parser doc
                    # (Tokenization might differ slightly, so we use char offsets)
                    span = doc.char_span(ent.start_char, ent.end_char, label=ent.label_)
                    if span:
                        new_ents.append(span)
                    else:
                        # Fallback for alignment issues
                        logger.debug(f"Entity alignment failed for {ent.text}")
                
                doc.ents = new_ents
            except Exception as e:
                logger.warning(f"Failed to merge NER entities: {e}")
                
        return doc
        
    def extract(self, narration_text):
        """
        Extract components from architecture narration.
        Returns list of model elements.
        """
        if not narration_text or not narration_text.strip():
            logger.warning("No architecture narration provided for component diagram")
            return []
        
        self.model_elements = []
        self.components = {}
        self.external_systems = set()
        self.relationships = []
        self.interfaces = {}
        self.packages = {}
        self.ports = {}
        
        # Process text with NER model
        doc = self._process_text(narration_text)
        
        # =====================================================================
        # EXTRACTION STRATEGY:
        # 1. NER MODEL is the PRIMARY source for entity extraction
        # 2. Gap-filling catches entities NER missed (training data gaps)
        # 3. Pattern-based code is ONLY for normalization and deduplication
        # 4. Relationships use pattern matching (NER may not capture verbs well)
        # =====================================================================
        
        if self.ner_model:
            # Primary: NER extracts COMPONENT, EXTERNAL_SYSTEM, INTERFACE, TECHNOLOGY
            self._extract_from_ner(doc)
            
            # New Extractions (Patterns)
            self._extract_interfaces(doc)
            self._extract_packages(doc)
            self._extract_ports(doc)
            
            # Gap-filling: Catch entities that NER missed due to training gaps
            # This is minimal and targeted, not a full pattern extraction
            self._fill_ner_gaps(narration_text, doc)
        else:
            # Fallback ONLY when no NER model available (shouldn't happen in production)
            print("[WARNING] No NER model - falling back to pattern extraction")
            self._extract_components_pattern(narration_text)
            self._extract_external_systems_pattern(narration_text)
        
        # Relationships extracted via patterns (verb phrases like "sends to", "uses")
        self._extract_relationships(narration_text)
    
        # Robust NLP-based relationship extraction
        if doc:
            self._extract_relationships_nlp(doc)
        
        # Build model elements
        self._build_component_elements()
        
        return self.model_elements
    
    def _extract_from_ner(self, doc):
        """
        Extract ALL entities from the NER model.
        This is the PRIMARY extraction method - model does the heavy lifting.
        
        NER Labels from architecture_uml_model:
        - COMPONENT: Services, modules, APIs (e.g., "inventory service", "payment API")
        - EXTERNAL_SYSTEM: Third-party integrations (e.g., "Amazon S3", "Stripe")
        - TECHNOLOGY: Databases, caches, frameworks (e.g., "MySQL", "Redis", "Docker")
        - NODE: Infrastructure (e.g., "Linux server", "cloud instance")
        - DEVICE: User devices (e.g., "mobile device", "desktop browser")
        - ENVIRONMENT: Deployment environments (e.g., "Docker containers", "Kubernetes")
        - INTERFACE: APIs, ports (e.g., "REST API", "port 8080")
        """
        for ent in doc.ents:
            entity_text = ent.text.strip()
            entity_lower = entity_text.lower()
            label = ent.label_
            
            if label == "COMPONENT":
                # Main application components/services
                comp_name = normalize_component_name(entity_text)
                stereotype = self._infer_stereotype(entity_lower)
                self._add_component(comp_name, stereotype)
            
            elif label == "EXTERNAL_SYSTEM":
                # Third-party services, external integrations
                # Only add to external_systems set - they'll be added as components
                # with <<external>> stereotype in _build_component_elements
                sys_name = normalize_external_system(entity_text)
                self.external_systems.add(sys_name)
                # Don't add to components here - avoid duplicates
            
            elif label == "TECHNOLOGY":
                # Databases, caches, message queues, frameworks
                tech_name = normalize_component_name(entity_text)
                # Infer stereotype from technology type
                if any(db in entity_lower for db in ['sql', 'database', 'db', 'mongo', 'postgres', 'mysql', 'redis', 'cache']):
                    stereotype = "database"
                elif any(mq in entity_lower for mq in ['queue', 'kafka', 'rabbit', 'mq']):
                    stereotype = "queue"
                else:
                    stereotype = self._infer_stereotype(entity_lower)
                self._add_component(tech_name, stereotype)
            
            elif label == "INTERFACE":
                # APIs, ports, endpoints
                interface_name = normalize_interface(entity_text)
                self.interfaces.add(interface_name)
            
            # NODE, DEVICE, ENVIRONMENT are handled by DeploymentDiagramExtractor
            # but we can capture infrastructure components here too
            elif label in ("NODE", "ENVIRONMENT"):
                # Infrastructure that might also be a logical component
                # e.g., "Docker containers" is both deployment and logical grouping
                pass  # Let deployment extractor handle these
    
    def _fill_ner_gaps(self, text, doc):
        """
        Fill gaps in NER extraction.
        
        The NER model may miss some entities due to training data gaps.
        This method catches obvious patterns that NER missed, but ONLY adds
        entities that are clearly mentioned in the text and not already extracted.
        
        This is NOT a full pattern extraction - it's targeted gap-filling.
        """
        text_lower = text.lower()
        
        # Get what NER already extracted (normalized names for comparison)
        ner_extracted = set()
        for ent in doc.ents:
            ner_extracted.add(ent.text.lower())
            # Also add normalized versions
            if ent.label_ == "COMPONENT":
                ner_extracted.add(normalize_component_name(ent.text).lower())
        
        # Also add what we've already collected
        for comp_name in self.components.keys():
            ner_extracted.add(comp_name.lower())
        
        # Pattern: "[word] service" that NER missed
        # e.g., "user interface service", "authentication service"
        service_pattern = re.findall(r'\b(\w+(?:\s+\w+)?)\s+service\b', text_lower)
        for match in service_pattern:
            full_name = f"{match} service"
            normalized = normalize_component_name(full_name)
            
            # Only add if not already extracted by NER
            if full_name not in ner_extracted and normalized.lower() not in ner_extracted:
                # Avoid generic patterns like "the service" or "a service"
                if match.strip() not in ('the', 'a', 'an', 'this', 'that', 'each', 'every'):
                    stereotype = self._infer_stereotype(full_name)
                    self._add_component(normalized, stereotype)
                    ner_extracted.add(normalized.lower())  # Prevent duplicates
        
        # Pattern: "[word] API" that NER missed
        api_pattern = re.findall(r'\b(\w+(?:\s+\w+)?)\s+api\b', text_lower)
        for match in api_pattern:
            full_name = f"{match} api"
            normalized = normalize_component_name(full_name)
            
            if full_name not in ner_extracted and normalized.lower() not in ner_extracted:
                if match.strip() not in ('the', 'a', 'an', 'this', 'that', 'rest', 'restful'):
                    self._add_component(normalized, "backend")
                    ner_extracted.add(normalized.lower())
    
    def _extract_components_pattern(self, text):
        """Pattern-based component extraction using keywords and technologies."""
        text_lower = text.lower()
        sentences = re.split(r'[.!?]', text)
        
        for sentence in sentences:
            sentence_lower = sentence.lower()
            
            # Look for component keywords
            for keyword in self.component_keywords:
                pattern = rf'\b(\w+\s+)?{keyword}\b'
                matches = re.finditer(pattern, sentence_lower)
                for match in matches:
                    comp_text = match.group(0).strip()
                    comp_name = self._normalize_component_name(comp_text)
                    stereotype = self._infer_stereotype(comp_text)
                    self._add_component(comp_name, stereotype)
            
            # Look for technology names
            for tech, stereotype in self.tech_mappings.items():
                if tech in sentence_lower:
                    # Try to find component name near technology
                    # Pattern: "React frontend", "Flask API", "PostgreSQL database"
                    pattern = rf'(\w+\s+)?{tech}(\s+\w+)?'
                    match = re.search(pattern, sentence_lower, re.IGNORECASE)
                    if match:
                        comp_name = self._normalize_component_name(match.group(0))
                        self._add_component(comp_name, stereotype)
    
    def _extract_external_systems_pattern(self, text):
        """
        Pattern-based external system extraction.
        ONLY used as fallback when NER model is not available.
        """
        text_lower = text.lower()
        external_indicators = ['external', 'third-party', 'third party', 'payment gateway', 
                               'auth provider', 'oauth', 'stripe', 'paypal', 'firebase',
                               'aws', 'amazon', 'azure', 'google cloud', 'twilio', 's3']
        
        sentences = re.split(r'[.!?]', text)
        for sentence in sentences:
            sentence_lower = sentence.lower()
            for indicator in external_indicators:
                if indicator in sentence_lower:
                    # Extract the system name
                    pattern = rf'(\w+\s+)?{indicator}(\s+\w+)?'
                    match = re.search(pattern, sentence_lower, re.IGNORECASE)
                    if match:
                        sys_name = normalize_external_system(match.group(0))
                        self.external_systems.add(sys_name)
    

    def _extract_interfaces(self, doc):
        """Extract provided (Lollipop) and required (Socket) interfaces."""
        # 1. "Exposes/Provides/Offers" patterns
        for sent in doc.sents:
            text = sent.text.lower()
            
            # Find the subject (Component)
            comp_name = self._find_component_in_text(sent.text)
            if not comp_name:
                continue
                
            # Check for verbs
            if any(v in text for v in ['exposes', 'provides', 'offers', 'implements']):
                # Find the object (Interface)
                match = re.search(r'(exposes|provides|offers|implements)\s+((?:an?|the)\s+)?(.+?)(?:\.|,|$)', sent.text, re.IGNORECASE)
                if match:
                    interface_raw = match.group(3)
                    # Clean up
                    interface_name = self._clean_interface_name(interface_raw)
                    if interface_name:
                        self._add_interface(interface_name, 'provided', comp_name, raw_name=interface_raw)

            # Check for Required (Socket)
            if any(v in text for v in ['requires', 'consumes', 'depends on', 'needs']):
                 match = re.search(r'(requires|consumes|depends on|needs)\s+((?:an?|the)\s+)?(.+?)(?:\.|,|$)', sent.text, re.IGNORECASE)
                 if match:
                    interface_raw = match.group(3)
                    interface_name = self._clean_interface_name(interface_raw)
                    if interface_name:
                        self._add_interface(interface_name, 'required', comp_name, raw_name=interface_raw)

    def _extract_packages(self, doc):
        """Extract package groupings."""
        for sent in doc.sents:
            text = sent.text.lower()
            # "Component A is part of Module B"
            if 'part of' in text or 'contained in' in text:
                comp_name = self._find_component_in_text(sent.text)
                if comp_name:
                    match = re.search(r'(part of|contained in|inside)\s+((?:a|an|the)\s+)?(.+?)(?:\.|,|$)', sent.text, re.IGNORECASE)
                    if match:
                        package_name = self._normalize_component_name(match.group(3))
                        if package_name:
                             # Register package
                             if package_name not in self.packages:
                                 self.packages[package_name] = []
                             
                             # If package was wrongly identified as a component, remove it
                             # Check raw match too: match.group(3)
                             raw_pkg = match.group(3).strip()
                             if package_name in self.components:
                                 del self.components[package_name]
                             elif raw_pkg in self.components:
                                  del self.components[raw_pkg]

                             self.packages[package_name].append(comp_name)
                             
                             # Update component parent
                             if comp_name in self.components:
                                 self.components[comp_name]['parent_package'] = package_name

            # "Module B contains Component A"
            if 'contains' in text or 'includes' in text:
                 # Try to find the Subject as Package
                 match = re.search(r'^(.+?)\s+(contains|includes)\s+(.+?)(?:\.|,|$)', sent.text, re.IGNORECASE)
                 if match:
                     pkg_raw = match.group(1).strip()
                     content_raw = match.group(3)
                     
                     # Simple heuristic: if Subject ends in "Module" or "Layer" or "Package"
                     if any(k in pkg_raw.lower() for k in ['module', 'layer', 'package', 'subsystem', 'system']):
                         pkg_name = self._normalize_component_name(pkg_raw)
                         # contents might be list "A, B and C"
                         if pkg_name not in self.packages:
                                 self.packages[pkg_name] = []
                         
                         # If package was wrongly identified as a component, remove it
                         if pkg_name in self.components:
                             del self.components[pkg_name]
                         elif pkg_raw in self.components:
                             del self.components[pkg_raw]

                         # Try to find components in the content string
                         for known_comp in list(self.components.keys()):
                             if known_comp.lower() in content_raw.lower():
                                 self.packages[pkg_name].append(known_comp)
                                 self.components[known_comp]['parent_package'] = pkg_name

    def _extract_ports(self, doc):
        """Extract explicit ports."""
        for sent in doc.sents:
            text = sent.text.lower()
            if 'port' in text:
                comp_name = self._find_component_in_text(sent.text)
                if comp_name:
                    # "connects via port 80"
                    match = re.search(r'(via|on|has|at|defines)\s+port\s+(\d+)', text)
                    if match:
                        port_num = match.group(2)
                        if comp_name not in self.ports:
                            self.ports[comp_name] = []
                        self.ports[comp_name].append(port_num)
        
        # Cleanup: Remove components that look like ports (e.g. "Port 8080")
        to_remove = []
        for name in self.components:
             if re.match(r'^Port\s+\d+\s*$', name, re.IGNORECASE):
                 to_remove.append(name)
        for name in to_remove:
            del self.components[name]

    def _clean_interface_name(self, raw):
        """Heuristic cleaning for interface names."""
        # Remove noise
        raw = re.sub(r'\b(api|endpoint|interface)\b', '', raw, flags=re.IGNORECASE).strip()
        # If result is empty, use the generic term back (e.g. "GraphQL API" -> "GraphQL")
        if not raw:
             return "Interface"
        
        # Stop at parens or common conjuncts
        raw = raw.split(' using ')[0]
        raw = raw.split(' to ')[0]
        raw = raw.split(' from ')[0]
        raw = raw.split(' via ')[0]
        raw = raw.split(' with ')[0]
        
        return self._normalize_component_name(raw)

    def _add_interface(self, name, type_, comp_name, raw_name=None):
        if not name or len(name) < 2: return
        
        # Register interface
        # Register interface
        if name not in self.interfaces:
            self.interfaces[name] = {'name': name, 'provider': None, 'consumers': []}
        
        # If interface was wrongly identified as a component, remove it
        if name in self.components:
            del self.components[name]
        if raw_name and raw_name in self.components:
             del self.components[raw_name]
        
        if type_ == 'provided':
            self.interfaces[name]['provider'] = comp_name
        elif type_ == 'required':
            self.interfaces[name]['consumers'].append(comp_name)

    def _extract_relationships(self, text):
        """Extract component relationships based on interaction keywords and patterns."""
        # print(f"DEBUG: Extracting relationships from: {text}")
        # print(f"DEBUG: Known components: {list(self.components.keys())}")
        sentences = re.split(r'[.!?]', text)
        
        # Common interaction patterns in architecture descriptions
        relationship_patterns = [
            # "X sends requests to Y", "X sends data to Y"
            (r'(\w+(?:\s+\w+){0,3})\s+sends?\s+(?:requests?|data|messages?)\s+to\s+(\w+(?:\s+\w+){0,3})', 'sends to'),
            # "X stores data in Y", "X persists data in Y", "X saves data to Y"
            (r'(\w+(?:\s+\w+){0,3})\s+(?:stores?|persists?|saves?)\s+(?:data\s+)?(?:in|to)\s+(?:an?\s+)?(\w+(?:\s+\w+){0,3})', 'stores in'),
            # "X reads from Y", "X writes to Y", "X reads and writes data to Y"
            (r'(\w+(?:\s+\w+){0,3})\s+(?:reads?|writes?|reads?\s+and\s+writes?)\s+(?:data\s+)?(?:to|from)\s+(\w+(?:\s+\w+){0,3})', 'uses'),
            # "X communicates with Y", "X interacts with Y"
            (r'(\w+(?:\s+\w+){0,3})\s+(?:communicates?|interacts?)\s+with\s+(?:an?\s+)?(?:external\s+)?(\w+(?:\s+\w+){0,3})', 'communicates with'),
            # "X uses Y"
            (r'(\w+(?:\s+\w+){0,3})\s+(?:uses?|leverages?|utilizes?)\s+(?:an?\s+)?(\w+(?:\s+\w+){0,3})', 'uses'),
            # "X depends on Y"
            (r'(\w+(?:\s+\w+){0,3})\s+depends?\s+on\s+(\w+(?:\s+\w+){0,3})', 'depends on'),
            # "X connects to Y"
            (r'(\w+(?:\s+\w+){0,3})\s+connects?\s+to\s+(\w+(?:\s+\w+){0,3})', 'connects to'),
            # "X accesses Y"
            (r'(\w+(?:\s+\w+){0,3})\s+(?:accesses?|connects?\s+to)\s+(\w+(?:\s+\w+){0,3})', 'accesses'),
            # Case 14: "X interacts with Y via Z" or "X uses Y via Z"
            (r'(\w+(?:\s+\w+){0,3})\s+(?:interacts?|communicates?|uses?)\s+(?:with\s+)?(\w+(?:\s+\w+){0,3})\s+(?:via|through)\s+(?:a\s+|an\s+|the\s+)?(\w+(?:\s+\w+){0,3})', 'via'),
            # "X uses Y to Z" (Case 14: "uses Zapper API to aggregate")
            (r'(\w+(?:\s+\w+){0,3})\s+uses\s+(?:the\s+)?(\w+(?:\s+\w+){0,3})\s+to\s+(\w+)', 'uses'),
        ]
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # Try each pattern
            for pattern, rel_type in relationship_patterns:
                matches = re.finditer(pattern, sentence, re.IGNORECASE)
                for match in matches:
                    source_text = match.group(1).strip()
                    target_text = match.group(2).strip()
                    via_text = match.group(3).strip() if match.lastindex >= 3 else None
                    
                    # Try to match to known components
                    source_comp = self._find_best_component_match(source_text)
                    target_comp = self._find_best_component_match(target_text)
                    
                    # Protocol extraction
                    protocol = None
                    if via_text:
                        # Check if 'via' is a protocol
                        protocols = ['http', 'https', 'grpc', 'jdbc', 'amqp', 'tcp', 'udp', 'rest', 'graphql', 'soap', 'websocket']
                        if any(p in via_text.lower() for p in protocols):
                            # Extract specific protocol
                            for p in protocols:
                                if p in via_text.lower():
                                    protocol = f"<<{p.upper()}>>"
                                    break
                        else:
                            # 'via' might be a component (e.g. "via Gateway")
                            # If it's a component, we might want to link to it, but for now let's just use it as label
                            pass
                    
                    # If either side didn't match, try to resolve by searching the sentence
                    sentence_lower = sentence.lower()
                    if not source_comp or not target_comp:
                        # ... (existing fallback logic, can be simplified or kept) ...
                         for comp_name in self.components.keys():
                            if comp_name.lower() in sentence_lower:
                                # prefer mapping to whichever side is missing, ensuring strict containment
                                if not source_comp and comp_name.lower() in source_text.lower():
                                    source_comp = comp_name
                                if not target_comp and comp_name.lower() in target_text.lower():
                                    target_comp = comp_name

                    if not target_comp and rel_type in ('via', 'communicates with', 'uses') and target_text:
                         # Heuristic: matches "Ethereum Mainnet"
                         # Force add it if it looks valid (capitalized)
                         if target_text[0].isupper() and len(target_text) > 3:
                             norm_target = self._normalize_component_name(target_text)
                             if norm_target not in self.components:
                                 self._add_component(norm_target, self._infer_stereotype(target_text))
                                 target_comp = norm_target

                    # Fallback for SOURCE component (e.g. "The Dashboard interacts...")
                    if not source_comp and rel_type in ('via', 'communicates with', 'uses') and source_text:
                         if source_text[0].isupper() and len(source_text) > 3:
                             norm_source = self._normalize_component_name(source_text)
                             # Avoid "The" being the name
                             if norm_source.lower() not in ('the', 'this', 'system'):
                                 if norm_source not in self.components:
                                     self._add_component(norm_source, self._infer_stereotype(source_text))
                                     source_comp = norm_source

                    if source_comp and target_comp and source_comp != target_comp:
                         description = rel_type
                         if rel_type == 'via':
                             description = "interacts" # simplify
                         
                         if protocol:
                             description = f"{description} {protocol}"

                         # Avoid duplicate relationships
                         rel_key = (source_comp, target_comp, description)
                         if not any(r['source'] == source_comp and r['target'] == target_comp and r.get('type') == description
                                   for r in self.relationships):
                             self.relationships.append({
                                 'source': source_comp,
                                 'target': target_comp,
                                 'type': description
                             })

                    # Avoid creating DB->DB relationships: prefer a service as subject when both matched DBs
                    try:
                        source_st = self.components.get(source_comp, {}).get('stereotype') if source_comp else None
                        target_st = self.components.get(target_comp, {}).get('stereotype') if target_comp else None
                    except Exception:
                        source_st = target_st = None

                    # Helper: is database-like
                    def _is_db(stype, name):
                        if not stype and not name:
                            return False
                        if stype and 'database' in stype:
                            return True
                        if name and ('postgres' in name.lower() or 'mysql' in name.lower() or 'redis' in name.lower() or 'mongodb' in name.lower() or 'database' in name.lower()):
                            return True
                        return False

                    if source_comp and target_comp:
                        if _is_db(source_st, source_comp) and _is_db(target_st, target_comp):
                            # Try to find a service component in the sentence to be the actual subject
                            found_service = None
                            for comp_name, comp_data in self.components.items():
                                if comp_name.lower() in sentence_lower and comp_name not in (source_comp, target_comp):
                                    if 'service' in comp_name.lower() or (comp_data.get('stereotype') and 'backend' in str(comp_data.get('stereotype')).lower()) or 'api' in comp_name.lower():
                                        found_service = comp_name
                                        break
                            if found_service:
                                # Re-attach relation: service -> the database (target or source depending on sentence order)
                                # Prefer targeting the DB that appears after the verb (target_comp)
                                source_comp = found_service
                            else:
                                # No service found; skip this ambiguous DB-DB relation
                                continue

                    # Finally, add relationship if both sides are known and distinct
                    if source_comp and target_comp and source_comp != target_comp:
                        # Avoid duplicate relationships
                        if not any(r['source'] == source_comp and r['target'] == target_comp 
                                  for r in self.relationships):
                            self.relationships.append({
                                'source': source_comp,
                                'target': target_comp,
                                'type': rel_type
                            })
                            logger.debug(f"Extracted relationship: {source_comp} -> {target_comp} ({rel_type})")
    
    def _find_best_component_match(self, text):
        """Find the best matching component name from extracted components."""
        text_lower = text.lower().strip()
        
        # Remove common words
        text_lower = re.sub(r'\b(the|a|an|this|that)\b', '', text_lower).strip()
        
        # Direct match with known components
        for comp_name in self.components.keys():
            if comp_name.lower() == text_lower or comp_name.lower() in text_lower:
                return comp_name
        
        # Match with external systems
        for ext_sys in self.external_systems:
            if ext_sys.lower() == text_lower or ext_sys.lower() in text_lower:
                return ext_sys
        
        # Try normalization
        normalized = self._normalize_component_name(text)
        if normalized in self.components:
            return normalized
        if normalized in self.external_systems:
            return normalized
        
        return None
    
    def _extract_relationships_old(self, text):
        """Old relationship extraction method (kept as fallback)."""
        sentences = re.split(r'[.!?]', text)
        
        interaction_keywords = self.relationship_keywords.get('interaction', [])
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            sentence_lower = sentence.lower()
            
            # Look for interaction patterns
            for keyword in interaction_keywords:
                if keyword in sentence_lower:
                    # Split on the keyword
                    parts = sentence.split(keyword, 1)  # Split only on first occurrence
                    if len(parts) >= 2:
                        # Extract component names from parts
                        source_text = parts[0].strip()
                        target_text = parts[1].strip()
                        
                        source_comp = self._extract_component_from_sentence(source_text)
                        target_comp = self._extract_component_from_sentence(target_text)
                        
                        if source_comp and target_comp:
                            # Normalize names
                            source_comp = self._normalize_component_name(source_comp)
                            target_comp = self._normalize_component_name(target_comp)
                            
                            # Determine relationship type
                            rel_type = keyword
                            
                            # Avoid duplicate relationships
                            rel_key = (source_comp, target_comp, rel_type)
                            if not any(r['source'] == source_comp and r['target'] == target_comp 
                                      for r in self.relationships):
                                self.relationships.append({
                                    'source': source_comp,
                                    'target': target_comp,
                                    'type': rel_type
                                })
                                logger.debug(f"Extracted relationship: {source_comp} -> {target_comp} ({rel_type})")
    
    def _find_component_in_text(self, text):
        """Find a known component name in a text fragment."""
        text = text.strip().lower()
        for comp_name in self.components.keys():
            if comp_name.lower() in text:
                return comp_name
        for ext_sys in self.external_systems:
            if ext_sys.lower() in text:
                return ext_sys
        return None
    
    def _extract_component_from_sentence(self, text):
        """
        Extract component name from a sentence fragment.
        Looks for known component keywords and technology terms.
        """
        text = text.strip()
        if not text:
            return None
        
        # Remove common prefixes
        text = re.sub(r'^(the|a|an)\s+', '', text, flags=re.IGNORECASE)
        
        # First check if we already know this component
        for comp_name in list(self.components.keys()) + list(self.external_systems):
            if comp_name.lower() in text.lower():
                return comp_name
        
        # Look for component keywords + qualifiers
        # Pattern: "frontend", "payment service", "backend API", etc.
        component_patterns = [
            r'(\w+\s+)?(?:service|api|application|app|frontend|backend|system|database|cache|server|gateway)',
            r'(?:service|api|application|app|frontend|backend|system|database|cache|server|gateway)(?:\s+\w+)?'
        ]
        
        for pattern in component_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0).strip()
        
        # Look for technology names
        for tech in self.tech_mappings.keys():
            if tech in text.lower():
                # Return text around the technology
                pattern = rf'(\w+\s+)?{tech}(\s+\w+)?'
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    return match.group(0).strip()
        
        # Last resort: return first noun phrase
        words = text.split()
        if len(words) > 0:
            # Take first 1-3 words
            return ' '.join(words[:min(3, len(words))])
        
        return None
    
    def _normalize_component_name(self, name):
        """Normalize component names to avoid duplicates using the centralized normalization."""
        return normalize_component_name(name)
    
    def _infer_stereotype(self, text):
        """Infer component stereotype from text."""
        text_lower = text.lower()
        for tech, stereotype in self.tech_mappings.items():
            if tech in text_lower:
                return stereotype
        return None
    
    def _add_component(self, name, stereotype=None):
        """Add a component to the collection with deduplication."""
        if not name:
            return
            
        name = self._normalize_component_name(name)
        
        # Filter out noise terms
        noise_terms = [
            'system', 'the system', 'application', 'the application',
            'for client', 'client communication', 'for communication',
            'using', 'with', 'from', 'to', 'and', 'or', 'the',
            # Generic actor words that aren't useful as components
            'client', 'customer', 'user', 'frontend'
        ]
        if name.lower() in noise_terms or len(name) < 3:
            return
        
        # Filter out malformed extractions
        malformed_patterns = [
            r'^(for|with|from|to|in|on|at|by|using|via|through)\s',
            r'\s(for|with|from|to|in|on|at|by|using|via|through)$',
            r'^(exposes|provides|offers)\s', # Filter out interface descriptions
            r'^\w{1,2}\s',  # Skip single/double letter prefixes like "Db Database"
        ]
        if any(re.match(pattern, name, re.IGNORECASE) for pattern in malformed_patterns):
            return
        
        # Filter out deployment infrastructure terms
        infrastructure_terms = ['server', 'container', 'virtual machine', 'vm', 'host', 'cluster']
        if any(term in name.lower() for term in infrastructure_terms):
            return
        
        # Check for near-duplicates (e.g., "Payment API" vs "Payment Service API")
        for existing_name in list(self.components.keys()):
            # If one name contains the other, merge them
            if name.lower() in existing_name.lower():
                # Use the longer, more descriptive name
                if stereotype and not self.components[existing_name]['stereotype']:
                    self.components[existing_name]['stereotype'] = stereotype
                return  # Don't add duplicate
            elif existing_name.lower() in name.lower():
                # Current name is more descriptive, replace existing
                if existing_name in self.components:
                    old_data = self.components.pop(existing_name)
                    self.components[name] = {
                        'stereotype': stereotype or old_data['stereotype'],
                        'interfaces': old_data['interfaces'],
                        'dependencies': old_data['dependencies']
                    }
                return
        
        # No duplicate found, add new component
        if name not in self.components:
            self.components[name] = {
                'stereotype': stereotype,
                'interfaces': [],
                'dependencies': []
            }
            logger.debug(f"Added component: {name} with stereotype {stereotype}")
    
    def _build_component_elements(self):
        """Build model elements from extracted data with deduplication."""
        # Deduplicate: merge components and external systems, keep unique normalized names
        all_components = {}
        
        # Generic/abstract component names that should be skipped when specific ones exist
        generic_component_patterns = {
            'api service': ['payment', 'order', 'user', 'auth', 'product', 'inventory', 'shipping'],
            'backend service': ['payment', 'order', 'user', 'auth', 'product', 'inventory', 'shipping'],
            'frontend service': ['ecommerce', 'web', 'admin', 'mobile', 'customer'],
            'service': ['payment', 'order', 'user', 'auth', 'product', 'inventory', 'shipping', 'email', 'notification'],
            'gateway': ['payment', 'api', 'stripe', 'paypal'],
            'payment gateway': ['stripe', 'paypal', 'square', 'braintree'],
            'api gateway': ['kong', 'apigee', 'aws'],
        }
        
        # Add regular components
        for comp_name, comp_data in self.components.items():
            # Skip generic/noise components
            noise_terms = [
                'system', 'the system', 'application', 'the application',
                'for client', 'client communication', 'for communication',
                'using', 'with', 'from', 'to', 'and', 'or', 'the'
            ]
            if comp_name.lower() in noise_terms or len(comp_name) < 3:
                continue
            
            # Skip malformed extractions (starts with preposition or ends with incomplete phrase)
            malformed_patterns = [
                r'^(for|with|from|to|in|on|at|by|using|via|through)\s',
                r'\s(for|with|from|to|in|on|at|by|using|via|through)$',
                r'^(exposes|provides|offers)\s', # Filter out interface descriptions
                r'^\w{1,2}\s',  # Skip single/double letter prefixes like "Db Database"
            ]
            if any(re.match(pattern, comp_name, re.IGNORECASE) for pattern in malformed_patterns):
                continue
            
            # Skip deployment infrastructure terms (these are nodes, not components)
            infrastructure_terms = ['server', 'container', 'virtual machine', 'vm', 'host', 'cluster']
            if any(term in comp_name.lower() for term in infrastructure_terms):
                continue
            
            # Skip deployment nodes that aren't components
            if comp_data['stereotype'] in ['<<server>>', '<<container>>', '<<device>>', '<<node>>']:
                continue
            
            # Skip generic component names if we have more specific ones
            is_generic = False
            comp_lower = comp_name.lower()
            for generic_pattern, specific_keywords in generic_component_patterns.items():
                if comp_lower == generic_pattern or comp_lower.strip() == generic_pattern.strip():
                    # Check if we have a more specific component with one of the keywords
                    for other_name in list(self.components.keys()) + list(self.external_systems):
                        other_lower = other_name.lower()
                        if other_lower != comp_lower:
                            for keyword in specific_keywords:
                                if keyword in other_lower and (generic_pattern.split()[0] in other_lower or 'service' in other_lower or 'gateway' in other_lower):
                                    is_generic = True
                                    logger.debug(f"Skipping generic '{comp_name}' because specific '{other_name}' exists")
                                    break
                        if is_generic:
                            break
                    if is_generic:
                        break
            
            if is_generic:
                continue
            
            # Deduplicate similar service names (Order Service vs Order Management Service)
            skip_duplicate = False
            for existing_name in list(all_components.keys()):
                # Check if this is a shorter version of an existing component
                comp_words = set(comp_name.lower().split())
                existing_words = set(existing_name.lower().split())
                
                # If one is a subset of the other, keep the longer/more specific one
                if comp_words < existing_words:  # comp_name is subset
                    skip_duplicate = True
                    break
                elif existing_words < comp_words:  # existing is subset, replace it
                    del all_components[existing_name]
                    
            if skip_duplicate:
                continue
                
            all_components[comp_name] = {
                'name': comp_name,
                'stereotype': comp_data['stereotype'],
                'parent_package': comp_data.get('parent_package'),
                'ports': self.ports.get(comp_name, [])
            }
        
        # Add external systems (with deduplication)
        for ext_sys in self.external_systems:
            # Skip if we already have a more specific version
            # e.g., skip "Stripe" if we have "Stripe Gateway"
            skip = False
            for existing_name in list(all_components.keys()):
                # If existing component contains this external system name, skip
                if ext_sys.lower() in existing_name.lower() and len(ext_sys) < len(existing_name):
                    skip = True
                    break
                # If this external system contains an existing component, replace it
                if existing_name.lower() in ext_sys.lower() and len(existing_name) < len(ext_sys):
                    del all_components[existing_name]
                    skip = False
                    break
            
            if not skip:
                # Check for generic terms that might be more specific elsewhere
                generic_terms = {
                    'payment gateway': ['stripe', 'paypal', 'square'],
                    'auth service': ['okta', 'auth0', 'cognito'],
                    'api gateway': ['kong', 'apigee'],
                    'message queue': ['rabbitmq', 'kafka'],
                }
                
                is_generic = False
                for generic_term, brands in generic_terms.items():
                    if generic_term in ext_sys.lower():
                        # Check if we have a more specific branded version
                        has_specific = any(
                            any(brand in existing.lower() for brand in brands)
                            for existing in all_components.keys()
                        )
                        if has_specific:
                            is_generic = True
                            break
                
                if is_generic:
                    skip = True
                
                if not skip:
                    all_components[ext_sys] = {
                        'name': ext_sys,
                        'stereotype': '<<external>>'
                    }
        
        # Convert to model elements
        for comp_data in all_components.values():
            self.model_elements.append({
                'type': 'Component',
                'data': comp_data,
                'source_id': None
            })
        
        # Add relationships
        for rel in self.relationships:
            self.model_elements.append({
                'type': 'ComponentRelationship',
                'data': rel,
                'source_id': None
            })

        # Add Interfaces
        for iface_data in self.interfaces.values():
            self.model_elements.append({
                'type': 'Interface',
                'data': iface_data,
                'source_id': None
            })




    def _resolve_coreference(self, token_or_text):
        """Resolve a token/text to a known component name."""
        # 1. Basic Text Resolution
        text = token_or_text.text if hasattr(token_or_text, 'text') else token_or_text
        text_lower = text.strip().lower()
        
        # Helper to check a string against components
        def check_match(t_low):
            all_candidates = []
            for c in self.components: all_candidates.append(c)
            for i in self.interfaces: all_candidates.append(i)
            for e in self.external_systems: all_candidates.append(e)
            
            # Score: 3=Exact, 2=Suffix, 1=Contains/Partial
            scored_candidates = []
            
            for name in all_candidates:
                n_low = name.lower()
                if n_low == t_low:
                     scored_candidates.append((name, 3))
                elif n_low.endswith(t_low):
                     # Guard against short suffix matches (e.g. "a" matching "Data")
                     if len(t_low) > 2:
                         scored_candidates.append((name, 2))
                elif t_low in n_low and len(t_low) > 3:
                     scored_candidates.append((name, 1))
                elif n_low in t_low and len(n_low) > 3:
                     scored_candidates.append((name, 1))
            
            if not scored_candidates:
                return None
                
            # Get highest score
            max_score = max(s for n, s in scored_candidates)
            best_candidates = [n for n, s in scored_candidates if s == max_score]
            
            if len(best_candidates) == 1:
                return best_candidates[0]
            
            # If ambiguity at max score (e.g. multiple Suffixes), fail
            # logger.debug(f"Ambiguous coref for '{t_low}': {best_candidates}")
            return None

        # 2. Ignored terms
        if text_lower in ['system', 'the system', 'application', 'it', 'this']:
            return 'SYSTEM_REF'
            
        # 3. Try Single Token
        match = check_match(text_lower)
        if match: return match
        
        # 4. Try Noun Chunk (if Token)
        if hasattr(token_or_text, 'dep_'): # Is Token
            # Find the chunk this token belongs to
            for chunk in token_or_text.doc.noun_chunks:
                if chunk.start <= token_or_text.i < chunk.end:
                    # Found chunk
                    chunk_text = chunk.text.strip().lower()
                    if chunk_text != text_lower: # Avoid redundant check
                        match = check_match(chunk_text)
                        if match: return match
                    break
                    
        return None

    def _extract_relationships_nlp(self, doc):
        """Robust NLP-based relationship extraction."""
        logger.info("Extracting relationships using NLP")
        last_subject = None
        
        interaction_verbs = ['communicate', 'interact', 'connect', 'send', 'use', 'access', 
                             'integrate', 'call', 'require', 'consume', 'provide', 'expose', 
                             'consist', 'write', 'publish', 'subscribe', 'store']

        for sent in doc.sents:
            # Find root verbs
            for token in sent:
                logger.debug(f"Scan: {token.text} ({token.pos_}/{token.lemma_})")
                if token.pos_ == "VERB" and token.lemma_ in interaction_verbs:
                    logger.debug(f"Hit VERB: {token.text}")
                    
                    # 1. Identify Subject
                    subj_token = None
                    for child in token.children:
                        if child.dep_ in ('nsubj', 'nsubjpass'):
                            subj_token = child
                            break
                    
                    source = None
                    if subj_token:
                        source = self._resolve_coreference(subj_token)
                        # Inference: If subject is Proper Noun but not in components, add it
                        if not source and subj_token.pos_ == "PROPN":
                            # Get noun chunk
                            phrase = subj_token.text
                            for chunk in doc.noun_chunks:
                                if chunk.start <= subj_token.i < chunk.end:
                                    phrase = self._normalize_component_name(chunk.text)
                                    break
                            
                            if phrase and phrase[0].isupper() and len(phrase) > 2:
                                if phrase not in self.components:
                                    logger.info(f"Inferring component from subject: {phrase}")
                                    self._add_component(phrase, 'Component')
                                source = phrase

                    # Handle Implicit Context (System/It)
                    if source == 'SYSTEM_REF' or (not source and not subj_token):
                         if last_subject:
                             source = last_subject
                    
                    # 2. Identify Objects
                    targets = []
                    
                    # Helper to extract from a token (recursive-ish)
                    def extract_targets_from_node(node, rel_prefix=""):
                        hits = []
                        # Check node itself (if it's not the verb)
                        if node != token:
                            t = self._resolve_coreference(node)
                            # Inference for Object
                            if not t and node.pos_ == "PROPN":
                                phrase = node.text
                                for chunk in doc.noun_chunks:
                                    if chunk.start <= node.i < chunk.end:
                                        phrase = self._normalize_component_name(chunk.text)
                                        break
                                if phrase and phrase[0].isupper() and len(phrase) > 2:
                                    if phrase not in self.components:
                                         logger.info(f"Inferring component from object: {phrase}")
                                         self._add_component(phrase, 'Component')
                                    t = phrase
                            
                            if t and t != 'SYSTEM_REF':
                                desc = token.lemma_
                                if rel_prefix: desc = f"{token.lemma_} {rel_prefix}"
                                hits.append((t, desc))
                                # logger.debug(f"Target found: {t} via {desc}")
                        
                        # Check children (Prepositions)
                        for child in node.children:
                            if child.dep_ == 'prep':
                                for pobj in child.children:
                                    if pobj.dep_ in ('pobj', 'dobj'):
                                        # logger.debug(f"Exploring prep: {child.text}, pobj: {pobj.text}")
                                        # Found a target via preposition
                                        prep_text = child.text
                                        if rel_prefix: prep_text = f"{rel_prefix} {child.text}"
                                        
                                        # Recurse? No, just extract from pobj
                                        # But pobj might have MORE preps (via Y via Z)
                                        # We accept pobj as target
                                        t_pobj = self._resolve_coreference(pobj)
                                        
                                        # Inference
                                        if not t_pobj and pobj.pos_ == "PROPN":
                                            phrase = pobj.text
                                            for chunk in doc.noun_chunks:
                                                if chunk.start <= pobj.i < chunk.end:
                                                    phrase = self._normalize_component_name(chunk.text)
                                                    break
                                            if phrase and phrase[0].isupper() and len(phrase) > 2:
                                                 if phrase not in self.components:
                                                     logger.info(f"Inferring component from pobj: {phrase}")
                                                     self._add_component(phrase, 'Component')
                                                 t_pobj = phrase
                                        
                                        if t_pobj and t_pobj != 'SYSTEM_REF':
                                            desc = f"{token.lemma_} {prep_text}"
                                            hits.append((t_pobj, desc))
                                            # logger.debug(f"Target found via prep: {t_pobj}")
                                            
                                        # Continue traversal from pobj?
                                        # e.g. "via consumer group"
                                        hits.extend(extract_targets_from_node(pobj, prep_text))
                                        
                        return hits

                    # Check direct children of Verb
                    for child in token.children:
                        if child.dep_ in ('dobj', 'attr', 'dative', 'oprd'):
                            # logger.debug(f"Checking direct object: {child.text}")
                            # The direct object itself might be a component (e.g. "Process uses X")
                            # Or it's a noun like "messages" which has preps "to Y"
                            targets.extend(extract_targets_from_node(child, ""))
                            
                        elif child.dep_ == 'prep':
                             # logger.debug(f"Checking verb prep: {child.text}")
                             # Preposition directly on verb (e.g. "writes to X")
                             # We delegate to helper to find pobj
                             # We pass verb as node? No.
                             # We need to look INTO prep.
                             for pobj in child.children:
                                  if pobj.dep_ in ('pobj', 'dobj'):
                                      # This is the target
                                      targets.extend(extract_targets_from_node(pobj, child.text))

                    # logger.debug(f"Source: {source}, Targets: {targets}")
                    # 3. Add Relationships
                    if source and source != 'SYSTEM_REF':
                         last_subject = source
                         
                         for target, rel_desc in targets:
                             if source != target:
                                 # Determine if Interface
                                 if target in self.interfaces:
                                     if any(v in rel_desc for v in ['provide', 'expose', 'implement']):
                                          self.interfaces[target]['provider'] = source
                                     else:
                                          if source not in self.interfaces[target]['consumers']:
                                               self.interfaces[target]['consumers'].append(source)
                                 else:
                                     # Component-Component
                                     # Basic dedupe
                                     exists = any(r['source'] == source and r['target'] == target for r in self.relationships)
                                     if not exists:
                                         self.relationships.append({
                                             'source': source,
                                             'target': target,
                                             'type': rel_desc
                                         })


class DeploymentDiagramExtractor(BaseDiagramExtractor):
    """
    Extracts nodes, artifacts, and deployment relationships for deployment diagrams.
    Requires architectural narration as input.
    """
    def __init__(self, nlp_model, ner_model=None, tech_mappings_path="technology_mappings.json"):
        super().__init__(nlp_model, ner_model)
        self.nodes = {}  # {name: {stereotype, artifacts, devices}}
        self.artifacts = {}  # {name: component_mapping}
        self.devices = set()
        self.environments = set()  # Runtime environments (docker, k8s, etc.)
        self.deployment_relationships = []
        
        # Load technology mappings
        self.tech_mappings = {}
        self.relationship_keywords = {}
        try:
            with open(tech_mappings_path, 'r') as f:
                mappings = json.load(f)
                self.tech_mappings = mappings.get('deployment_stereotypes', {})
                self.relationship_keywords = mappings.get('relationship_keywords', {})
                self.node_keywords = mappings.get('node_keywords', [])
                self.device_keywords = mappings.get('device_keywords', [])
        except Exception as e:
            logger.error(f"Failed to load technology mappings: {e}")
    
    def extract(self, narration_text, component_artifacts=None):
        """
        Extract deployment architecture from narration.
        
        Args:
            narration_text: The architectural description text
            component_artifacts: Optional dict of {name: stereotype} from ComponentDiagramExtractor
                                 These will be used as artifacts (deployed services)
        
        Returns list of model elements.
        """
        if not narration_text or not narration_text.strip():
            logger.warning("No architecture narration provided for deployment diagram")
            return []
        
        # Store original text for containment extraction
        self._original_text = narration_text
        
        self.model_elements = []
        self.nodes = {}
        self.artifacts = {}
        self.devices = set()
        self.deployment_relationships = []
        
        # Process text with NER model
        doc = self._process_text(narration_text)
        
        # =====================================================================
        # EXTRACTION STRATEGY for Deployment:
        # 1. Use pre-extracted components from ComponentDiagramExtractor as artifacts
        #    (This ensures consistency between component and deployment diagrams)
        # 2. NER MODEL extracts: NODE, DEVICE, ENVIRONMENT
        # 3. Nodes/Devices use patterns as FALLBACK (NER may miss infrastructure)
        # =====================================================================
        
        # Import components from component diagram as artifacts
        if component_artifacts:
            for name, data in component_artifacts.items():
                stereotype = data.get('stereotype', '') if isinstance(data, dict) else data
                # Skip databases - they become nodes, not artifacts
                if stereotype and 'database' in str(stereotype).lower():
                    continue
                # Skip external systems - they're outside our deployment
                if stereotype and 'external' in str(stereotype).lower():
                    continue
                self.artifacts[name] = None  # Will be assigned to node later
        
        if self.ner_model:
            self._extract_from_ner(doc)
        
        # Nodes and devices can use patterns (infrastructure is less ambiguous)
        self._extract_nodes_pattern(narration_text)
        self._extract_devices_pattern(narration_text)
        
        # DO NOT extract artifacts via patterns - they create noise
        # Artifacts should come from NER's COMPONENT entities only
        # self._extract_artifacts_pattern(narration_text)  # DISABLED - causes noise
        
        self._extract_deployment_relationships(narration_text)
        
        # Build model elements
        self._build_deployment_elements()
        
        return self.model_elements
    
    def _extract_from_ner(self, doc):
        """Extract deployment entities from NER."""
        for ent in doc.ents:
            if ent.label_ == "NODE":
                node_name = normalize_node_name(ent.text)
                stereotype = self._infer_node_stereotype(ent.text.lower())
                self._add_node(node_name, stereotype)
            
            elif ent.label_ == "DEVICE":
                device_name = normalize_device_name(ent.text)
                self.devices.add(device_name)
            
            elif ent.label_ == "ARTIFACT":
                artifact_name = normalize_component_name(ent.text)
                # Skip generic/noise artifacts
                if self._is_valid_artifact(artifact_name):
                    self.artifacts[artifact_name] = None
            
            elif ent.label_ == "COMPONENT":
                # Components become deployable artifacts in deployment diagrams
                # (services, APIs, frontends that run inside nodes)
                comp_name = normalize_component_name(ent.text)
                # Skip databases - they become nodes, not artifacts
                entity_lower = ent.text.lower()
                if not any(db in entity_lower for db in ['database', 'db', 'sql', 'mongo', 'postgres', 'mysql', 'redis', 'cache']):
                    # Skip generic/noise artifacts
                    if self._is_valid_artifact(comp_name):
                        self.artifacts[comp_name] = None
            
            elif ent.label_ == "ENVIRONMENT" or ent.label_ == "ENVIRONMENT_TYPE":
                env_name = normalize_environment_name(ent.text)
                self.environments.add(env_name)
    
    def _is_valid_artifact(self, name):
        """Check if artifact name is valid (not generic noise)."""
        if not name or len(name) < 4:
            return False
        
        # Reject single generic words
        generic_noise = [
            'service', 'api', 'app', 'application', 'system', 'module',
            'component', 'interface', 'frontend', 'backend', 'server',
            'client', 'the', 'a', 'an'
        ]
        name_lower = name.lower().strip()
        if name_lower in generic_noise:
            return False
        
        return True
    
    def _extract_nodes_pattern(self, text):
        """Pattern-based node extraction."""
        text_lower = text.lower()
        sentences = re.split(r'[.!?]', text)
        
        for sentence in sentences:
            sentence_lower = sentence.lower()
            
            # Look for node keywords
            for keyword in self.node_keywords:
                pattern = rf'\b(\w+\s+)?{keyword}\b'
                matches = re.finditer(pattern, sentence_lower)
                for match in matches:
                    node_text = match.group(0).strip()
                    node_name = self._normalize_node_name(node_text)
                    stereotype = self._infer_node_stereotype(node_text)
                    self._add_node(node_name, stereotype)
            
            # Look for technology names that indicate nodes
            for tech, stereotype in self.tech_mappings.items():
                if tech in sentence_lower:
                    pattern = rf'(\w+\s+)?{tech}(\s+\w+)?'
                    match = re.search(pattern, sentence_lower, re.IGNORECASE)
                    if match:
                        node_name = self._normalize_node_name(match.group(0))
                        self._add_node(node_name, stereotype)
    
    def _extract_devices_pattern(self, text):
        """Extract devices (browsers, mobile, etc.)."""
        text_lower = text.lower()
        
        for keyword in self.device_keywords:
            if keyword in text_lower:
                pattern = rf'\b(\w+\s+)?{keyword}(\s+\w+)?\b'
                matches = re.finditer(pattern, text_lower)
                for match in matches:
                    device_name = normalize_device_name(match.group(0))
                    
                    # Filter out malformed/noise device names
                    if not device_name or len(device_name) < 4:
                        continue
                    
                    noise_words = ['client', 'using', 'for', 'with', 'from', 'the', 'and', 'system']
                    if device_name.lower() in noise_words:
                        continue
                    
                    # Skip if starts with preposition/conjunction
                    if re.match(r'^(for|with|using|from|and|or|the|via|through|in|on)\s', device_name, re.IGNORECASE):
                        continue
                    
                    # Check if this "device" is actually a software artifact we already found (e.g. "Client UI")
                    if any(art_name.lower() == device_name.lower() for art_name in self.artifacts.keys()):
                        continue

                    # Simply add - normalization already handled "Desktop Browser" → "Web Browser"
                    # Set automatically deduplicates
                    self.devices.add(device_name)
    
    def _extract_artifacts_pattern(self, text):
        """
        Extract software artifacts (services, APIs, frontends, etc.) that should be 
        deployed inside infrastructure nodes. These represent the actual application
        components that users interact with.
        """
        text_lower = text.lower()
        
        # Artifact keywords - these indicate software components that can be deployed
        artifact_patterns = [
            # Service patterns: "payment service", "backend services", "order service"
            (r'(\w+)\s+service(?:s)?(?:\s+API)?', 'service'),
            # API patterns: "payment API", "REST API", "the API"
            (r'(\w+)\s+API\b', 'api'),
            # Frontend patterns: "ecommerce frontend", "web frontend", "mobile frontend"
            (r'(\w+)\s+frontend', 'frontend'),
            # Application patterns: "web application", "mobile app"
            (r'(\w+)\s+(?:application|app)\b', 'application'),
            # Backend patterns: "backend services", "backend application"
            (r'backend\s+(\w+)', 'backend'),
        ]
        
        sentences = re.split(r'[.!?]', text)
        
        for sentence in sentences:
            sentence_lower = sentence.lower().strip()
            if not sentence_lower:
                continue
            
            for pattern, artifact_type in artifact_patterns:
                matches = re.finditer(pattern, sentence_lower, re.IGNORECASE)
                for match in matches:
                    # Get the full match and the qualifier
                    full_match = match.group(0).strip()
                    qualifier = match.group(1).strip() if match.lastindex >= 1 else ''
                    
                    # Skip noise words as qualifiers
                    noise_qualifiers = ['the', 'a', 'an', 'this', 'that', 'each', 'every', 'any']
                    if qualifier.lower() in noise_qualifiers:
                        continue
                    
                    # Build artifact name
                    if artifact_type == 'backend':
                        artifact_name = f"Backend {qualifier.title()}"
                    else:
                        artifact_name = normalize_component_name(full_match)
                    
                    # Skip if too short or noise
                    if not artifact_name or len(artifact_name) < 4:
                        continue
                    
                    # Skip database names (they're nodes, not artifacts)
                    db_terms = ['postgresql', 'postgres', 'mysql', 'mongodb', 'redis', 'database', 'cache']
                    if any(db in artifact_name.lower() for db in db_terms):
                        continue
                    
                    # Determine target node - where should this artifact be deployed?
                    target_node = None
                    
                    # Check sentence context for deployment location
                    # "services run in Docker containers" → deploy in Docker Container
                    # "frontend communicates with..." → deploy in Server (default for frontends)
                    if 'docker' in sentence_lower or 'container' in sentence_lower:
                        # Find container node
                        target_node = next((n for n in self.nodes.keys() 
                                           if 'container' in n.lower() or 'docker' in n.lower()), None)
                    elif 'server' in sentence_lower:
                        target_node = next((n for n in self.nodes.keys() 
                                           if 'server' in n.lower()), None)
                    else:
                        # Default: deploy to container if exists, else server
                        target_node = next((n for n in self.nodes.keys() 
                                           if 'container' in n.lower() or 'docker' in n.lower()), None)
                        if not target_node:
                            target_node = next((n for n in self.nodes.keys() 
                                               if 'server' in n.lower()), None)
                    
                    # Add artifact (deduplication handled by dict)
                    if artifact_name not in self.artifacts:
                        self.artifacts[artifact_name] = target_node
                        logger.info(f"Extracted artifact: {artifact_name} -> deployed on {target_node}")

    def _extract_deployment_relationships(self, text):
        """Extract deployment relationships (connections between nodes/devices and deployment)."""
        sentences = re.split(r'[.!?]', text)
        
        # Common relationship patterns for deployment diagrams
        # These show connections between devices, nodes, and how components are deployed
        relationship_patterns = [
            # "X sends requests to Y", "X sends data to Y"
            (r'(\w+(?:\s+\w+){0,3})\s+sends?\s+(?:requests?|data|messages?)\s+to\s+(\w+(?:\s+\w+){0,3})', 'connects to'),
            # "X reads from Y", "X writes to Y", "X reads and writes data to Y"
            (r'(\w+(?:\s+\w+){0,3})\s+(?:reads?|writes?|reads?\s+and\s+writes?)\s+(?:data\s+)?(?:to|from)\s+(\w+(?:\s+\w+){0,3})', 'accesses'),
            # "X communicates with Y", "X interacts with Y", "X connects to Y"
            (r'(\w+(?:\s+\w+){0,3})\s+(?:communicates?|interacts?|connects?)\s+(?:with|to)\s+(?:an?\s+)?(?:external\s+)?(\w+(?:\s+\w+){0,3})', 'connects to'),
            # "X uses Y", "X leverages Y", "X utilizes Y"
            (r'(\w+(?:\s+\w+){0,3})\s+(?:uses?|leverages?|utilizes?)\s+(?:an?\s+)?(\w+(?:\s+\w+){0,3})', 'uses'),
            # "X is deployed in/on/inside Y", "X runs on Y", "X hosted on Y"
            (r'(\w+(?:\s+\w+){0,3})\s+(?:is\s+deployed|deployed|runs?|hosted)\s+(?:in|on|inside)\s+(\w+(?:\s+\w+){0,3})', 'deployed on'),
            # "Customers/Users interact with X using Y"
            (r'(?:customers?|users?)\s+(?:interact|access|use)\s+(?:with\s+)?(?:the\s+)?(\w+(?:\s+\w+){0,2})\s+using\s+(\w+(?:\s+\w+){0,2})', 'accesses via'),
        ]
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # Try each pattern
            for pattern, rel_type in relationship_patterns:
                matches = re.finditer(pattern, sentence, re.IGNORECASE)
                for match in matches:
                    source_text = match.group(1).strip()
                    target_text = match.group(2).strip()
                    
                    # Try to match to known nodes or devices
                    source = self._find_deployment_entity(source_text)
                    target = self._find_deployment_entity(target_text)
                    
                    if source and target and source != target:
                        # Avoid duplicate relationships
                        if not any(r['source'] == source and r['target'] == target 
                                  for r in self.deployment_relationships):
                            self.deployment_relationships.append({
                                'source': source,
                                'target': target,
                                'type': rel_type
                            })
                            logger.debug(f"Extracted deployment relationship: {source} -> {target} ({rel_type})")
        
        # ALWAYS ensure devices have access relationships to the system
        # Devices (browsers, mobile) access the application (artifacts), not infrastructure directly
        # Check if any device already has a relationship
        devices_with_relationships = {r['source'] for r in self.deployment_relationships if r['source'] in self.devices}
        devices_without_relationships = self.devices - devices_with_relationships
        
        if devices_without_relationships:
            # Find the best target for devices (frontend artifact preferred)
            frontend_artifact = None
            service_artifact = None
            
            for artifact_name in self.artifacts.keys():
                art_lower = artifact_name.lower()
                if 'frontend' in art_lower or 'application' in art_lower or 'app' in art_lower:
                    frontend_artifact = artifact_name
                elif 'service' in art_lower or 'api' in art_lower or 'backend' in art_lower:
                    if not service_artifact:  # Take first service found
                        service_artifact = artifact_name
            
            # Target priority: frontend artifact > service artifact > server node
            target = frontend_artifact or service_artifact
            
            if not target:
                # No artifacts, fallback to server
                target = next((n for n in self.nodes.keys() if 'server' in n.lower()), None)
            
            if target:
                for device in devices_without_relationships:
                    self.deployment_relationships.append({
                        'source': device,
                        'target': target,
                        'type': 'accesses'
                    })
                    logger.info(f"Added device access: {device} accesses {target}")
    
    def _find_deployment_entity(self, text):
        """Find matching node or device name from text."""
        text_lower = text.lower().strip()
        
        # Remove common words
        text_lower = re.sub(r'\b(the|a|an|this|that)\b', '', text_lower).strip()
        
        logger.debug(f"Finding deployment entity for: '{text}' → '{text_lower}'")
        
        # Direct match with known nodes
        for node_name in self.nodes.keys():
            if node_name.lower() == text_lower or node_name.lower() in text_lower or text_lower in node_name.lower():
                logger.debug(f"  → Matched node: {node_name}")
                return node_name
        
        # Match with devices
        for device_name in self.devices:
            if device_name.lower() == text_lower or device_name.lower() in text_lower or text_lower in device_name.lower():
                logger.debug(f"  → Matched device: {device_name}")
                return device_name
        
        # Try normalization to canonical form
        normalized_node = self._normalize_node_name(text)
        if normalized_node in self.nodes:
            logger.debug(f"  → Matched via node normalization: {normalized_node}")
            return normalized_node
        
        # Check if normalized node matches existing nodes
        for node_name in self.nodes.keys():
            if normalized_node.lower() in node_name.lower() or node_name.lower() in normalized_node.lower():
                logger.debug(f"  → Matched via partial node normalization: {node_name}")
                return node_name
        
        # Check if it matches a device pattern
        normalized_device = normalize_device_name(text)
        if normalized_device in self.devices:
            logger.debug(f"  → Matched via device normalization: {normalized_device}")
            return normalized_device
        
        # Check if normalized device matches existing devices
        for device_name in self.devices:
            if normalized_device.lower() in device_name.lower() or device_name.lower() in normalized_device.lower():
                logger.debug(f"  → Matched via partial device normalization: {device_name}")
                return device_name
        
        # Match with artifacts (software components deployed)
        for artifact_name in self.artifacts.keys():
            if artifact_name.lower() == text_lower or artifact_name.lower() in text_lower or text_lower in artifact_name.lower():
                logger.debug(f"  → Matched artifact: {artifact_name}")
                return artifact_name
        
        logger.debug(f"  → No match found")
        return None
    
    def _extract_artifact_name(self, text):
        """Extract artifact name from text."""
        # Look for component-like names (capitalized words)
        words = text.split()
        for i in range(len(words) - 1, -1, -1):
            word = words[i].strip(',')
            if word and word[0].isupper():
                # Could be a component/artifact name
                return ' '.join(words[max(0, i-1):i+1]).strip(',').strip()
        return None
    
    def _find_node_in_text(self, text):
        """Find a known node name in text."""
        text = text.strip().lower()
        for node_name in self.nodes.keys():
            if node_name.lower() in text:
                return node_name
        # Try to extract from known tech
        for tech, _ in self.tech_mappings.items():
            if tech in text:
                return self._normalize_node_name(tech)
        return None
    
    def _normalize_node_name(self, name):
        """Normalize node names using the centralized normalization."""
        return normalize_node_name(name)
    
    def _infer_node_stereotype(self, text):
        """Infer node stereotype from text."""
        text_lower = text.lower()
        for tech, stereotype in self.tech_mappings.items():
            if tech in text_lower:
                return stereotype
        return "<<server>>"  # Default stereotype
    
    def _add_node(self, name, stereotype=None):
        """Add a node to the collection."""
        if name and name not in self.nodes:
            self.nodes[name] = {
                'stereotype': stereotype or "<<server>>",
                'artifacts': []
            }
    
    def _build_deployment_elements(self):
        """Build model elements from extracted data with cross-collection deduplication and nesting."""
        from scripts.normalization_config_loader import get_config
        
        config = get_config()
        
        # Detect containment relationships (what's inside what)
        # Common patterns: "X deployed inside/in/on Y", "X hosted on Y", "Y hosts X"
        containment_map = {}  # child_node -> parent_node
        
        # Extract containment from original text (if available)
        if hasattr(self, '_original_text'):
            # More specific patterns that look for actual infrastructure terms
            containment_patterns = [
                # "deployed inside Docker containers" - look for known node types
                (r'deployed\s+(?:inside|in|on)\s+(\w+(?:\s+\w+)?(?:\s+containers?)?)', 'parent'),
                # "hosted on Ubuntu servers" - look for server patterns
                (r'hosted\s+on\s+(\w+(?:\s+\w+)?(?:\s+servers?)?)', 'parent'),
                # "runs on Kubernetes"
                (r'runs?\s+on\s+(\w+(?:\s+\w+)?)', 'parent'),
                # "containers hosted on servers" - containers inside servers
                (r'(\w+\s+)?containers?\s+hosted\s+on\s+(\w+(?:\s+\w+)?(?:\s+servers?)?)', 'container_in_server'),
            ]
            
            logger.debug(f"Searching for containment in text: {self._original_text[:100]}...")
            
            # First, establish what should be inside what based on infrastructure hierarchy
            # Server > Container > Database is typical hierarchy
            has_server = any('server' in n.lower() for n in self.nodes.keys())
            has_container = any('container' in n.lower() or 'docker' in n.lower() for n in self.nodes.keys())
            has_database = any(self.nodes[n]['stereotype'] == '<<database>>' for n in self.nodes.keys())
            
            # Check text for explicit containment
            text_lower = self._original_text.lower()
            
            # Find container and server nodes
            container_node = next((n for n in self.nodes.keys() if 'container' in n.lower() or 'docker' in n.lower()), None)
            server_node = next((n for n in self.nodes.keys() if 'server' in n.lower()), None)
            
            # Various patterns that indicate containers are on/in servers:
            # - "run in Docker containers on Linux servers"
            # - "deployed inside Docker containers hosted on servers"
            # - "containers hosted on servers"
            container_on_server_patterns = [
                r'(?:run|runs|running)\s+(?:in|on)\s+(?:\w+\s+)?containers?\s+on\s+(?:\w+\s+)?servers?',
                r'deployed\s+(?:inside|in|on)\s+(?:\w+\s+)?containers?',
                r'containers?\s+(?:hosted|deployed|running)\s+on\s+(?:\w+\s+)?servers?',
                r'(?:docker|kubernetes|k8s)\s+(?:on|running\s+on)\s+(?:\w+\s+)?servers?',
            ]
            
            for pattern in container_on_server_patterns:
                if re.search(pattern, text_lower):
                    if container_node and server_node and container_node not in containment_map:
                        containment_map[container_node] = server_node
                        logger.info(f"Containment: {container_node} inside {server_node} (pattern: {pattern})")
                        break
            
            # Databases are typically inside containers or servers
            if has_database and (has_container or has_server):
                db_nodes = [n for n in self.nodes.keys() if self.nodes[n]['stereotype'] == '<<database>>']
                
                for db_node in db_nodes:
                    if db_node not in containment_map:
                        # Put database in container if exists, otherwise in server
                        parent = container_node or server_node
                        if parent:
                            containment_map[db_node] = parent
                            logger.info(f"Containment: {db_node} inside {parent}")
        
        # Get cross-collection rules (prevent entities from appearing in multiple collections)
        cross_collection_rules = config.get_cross_collection_rules()
        
        # Deduplicate: if an entity appears in both nodes and devices, keep only the preferred collection
        entities_to_nodes = set(self.nodes.keys())
        entities_to_devices = set(self.devices.copy())
        
        for rule in cross_collection_rules:
            patterns = rule.get('patterns', [])
            preferred = rule.get('preferred_collection', 'nodes')
            
            # Find entities matching the patterns
            for pattern in patterns:
                # Check both collections for matches
                node_matches = {n for n in entities_to_nodes if re.search(pattern, n, re.IGNORECASE)}
                device_matches = {d for d in entities_to_devices if re.search(pattern, d, re.IGNORECASE)}
                
                all_matches = node_matches | device_matches
                
                if len(all_matches) > 0:
                    # Keep in preferred collection only
                    if preferred == 'nodes':
                        # Remove from devices, keep in nodes (or add to nodes if not there)
                        for match in all_matches:
                            if match in device_matches:
                                entities_to_devices.discard(match)
                            if match not in entities_to_nodes:
                                # Add to nodes
                                self._add_node(match, "<<browser>>" if 'browser' in match.lower() else "<<device>>")
                                entities_to_nodes.add(match)
                    else:  # preferred == 'devices'
                        # Remove from nodes, keep in devices
                        for match in all_matches:
                            if match in node_matches:
                                if match in self.nodes:
                                    del self.nodes[match]
                                entities_to_nodes.discard(match)
                            if match not in entities_to_devices:
                                entities_to_devices.add(match)
        
        # Update self.devices to match deduplicated set
        self.devices = entities_to_devices
        
        # Consolidate browser devices - if we have multiple browser variants, keep only "Web Browser"
        browser_devices = [d for d in self.devices if 'browser' in d.lower()]
        if len(browser_devices) > 1 or (len(browser_devices) == 1 and browser_devices[0] != 'Web Browser'):
            # Remove all browser variants
            for browser in browser_devices:
                self.devices.discard(browser)
            # Add canonical form
            self.devices.add('Web Browser')
        
        # =====================================================================
        # ARTIFACT DEDUPLICATION
        # Remove generic artifacts when specific ones exist, and dedupe plurals
        # =====================================================================
        artifacts_to_remove = set()
        artifact_names = list(self.artifacts.keys())
        
        for artifact in artifact_names:
            artifact_lower = artifact.lower()
            
            # 1. Remove plural duplicates: "Backend Services" when "Backend Service" exists
            if artifact_lower.endswith('s') and not artifact_lower.endswith('ss'):
                singular = artifact[:-1]  # Remove 's'
                if singular in self.artifacts:
                    artifacts_to_remove.add(artifact)
                    logger.debug(f"Removing plural artifact '{artifact}' (singular '{singular}' exists)")
                    continue
            
            # 2. Remove "Api Service" when a specific service exists (Payment Service, Order Service, etc.)
            generic_artifacts = ['api service', 'backend service', 'the service', 'web service']
            if artifact_lower in generic_artifacts:
                # Check if a more specific service exists
                specific_keywords = ['payment', 'order', 'user', 'auth', 'notification', 
                                    'inventory', 'shipping', 'billing', 'email', 'message']
                for other_artifact in artifact_names:
                    other_lower = other_artifact.lower()
                    if other_lower != artifact_lower:
                        # Check if other artifact has a specific keyword + service/api
                        for keyword in specific_keywords:
                            if keyword in other_lower and ('service' in other_lower or 'api' in other_lower):
                                artifacts_to_remove.add(artifact)
                                logger.debug(f"Removing generic artifact '{artifact}' (specific '{other_artifact}' exists)")
                                break
                    if artifact in artifacts_to_remove:
                        break
        
        # Remove marked artifacts
        for artifact in artifacts_to_remove:
            if artifact in self.artifacts:
                del self.artifacts[artifact]
        
        logger.info(f"After artifact deduplication: {len(self.artifacts)} artifacts")
        
        # =====================================================================
        # ASSIGN ARTIFACTS TO NODES
        # Artifacts (services) should be deployed inside infrastructure nodes
        # Priority: Container > Server (services typically run in containers)
        # =====================================================================
        container_node = next((n for n in self.nodes.keys() if 'container' in n.lower() or 'docker' in n.lower()), None)
        server_node = next((n for n in self.nodes.keys() if 'server' in n.lower()), None)
        target_node = container_node or server_node  # Prefer container
        
        if target_node:
            # Assign all unassigned artifacts to the target node
            for artifact_name in self.artifacts.keys():
                if self.artifacts[artifact_name] is None:
                    self.artifacts[artifact_name] = target_node
                    logger.debug(f"Assigned artifact '{artifact_name}' to node '{target_node}'")
        
        # Add nodes with their artifacts and children nodes
        for node_name, node_data in self.nodes.items():
            # Find artifacts deployed on this node
            node_artifacts = [art for art, node in self.artifacts.items() if node == node_name]
            
            # Find child nodes (nodes contained within this node)
            child_nodes = [child for child, parent in containment_map.items() if parent == node_name]
            
            self.model_elements.append({
                'type': 'Node',
                'data': {
                    'name': node_name,
                    'stereotype': node_data['stereotype'],
                    'artifacts': node_artifacts,
                    'children': child_nodes  # Add children for nesting
                },
                'source_id': None
            })
        
        # Add devices
        for device_name in self.devices:
            self.model_elements.append({
                'type': 'Device',
                'data': {
                    'name': device_name,
                    'stereotype': '<<browser>>' if 'browser' in device_name.lower() else '<<device>>'
                },
                'source_id': None
            })
        
        # Add orphaned artifacts (not assigned to any node)
        orphaned_artifacts = [art for art, node in self.artifacts.items() if node is None]
        for artifact_name in orphaned_artifacts:
            self.model_elements.append({
                'type': 'Artifact',
                'data': {
                    'name': artifact_name
                },
                'source_id': None
            })
        
        # Add deployment relationships (connections between nodes/devices)
        # Skip "deployed on" relationships when artifact is already INSIDE the node
        # Also skip relationships that reference removed/deduplicated artifacts
        valid_artifact_names = set(self.artifacts.keys())
        node_names = set(self.nodes.keys())
        device_names = set(self.devices)
        
        # Build set of all valid entity names (for relationship validation)
        all_valid_entities = valid_artifact_names | node_names | device_names
        
        for rel in self.deployment_relationships:
            source = rel.get('source', '')
            target = rel.get('target', '')
            
            # Skip relationships where source or target was removed during deduplication
            # Check if source/target exists in our valid entities
            source_valid = any(source.lower() == e.lower() or source.lower() in e.lower() or e.lower() in source.lower() 
                              for e in all_valid_entities)
            target_valid = any(target.lower() == e.lower() or target.lower() in e.lower() or e.lower() in target.lower() 
                              for e in all_valid_entities)
            
            if not source_valid or not target_valid:
                logger.debug(f"Skipping relationship with invalid entity: {source} -> {target}")
                continue
            
            # Skip redundant "deployed on" relationships where artifact is already inside the node
            if rel.get('type') == 'deployed on':
                # If source is an artifact that's already deployed to target node, skip
                if source in valid_artifact_names:
                    deployed_node = self.artifacts.get(source)
                    if deployed_node and (deployed_node == target or 
                                          target.lower() in deployed_node.lower() or
                                          deployed_node.lower() in target.lower()):
                        logger.debug(f"Skipping redundant 'deployed on' relationship: {source} -> {target}")
                        continue
            
            self.model_elements.append({
                'type': 'DeploymentRelationship',
                'data': rel,
                'source_id': None
            })
    
    def _find_node_match(self, text):
        """Find matching node name from text."""
        text_lower = text.lower().strip()
        for node_name in self.nodes.keys():
            if node_name.lower() == text_lower or node_name.lower() in text_lower or text_lower in node_name.lower():
                return node_name
        return None

