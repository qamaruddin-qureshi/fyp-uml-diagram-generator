# uml_extractors.py
"""
Contains all diagram extractor classes for UML model extraction from user stories.
"""
import re
import json
import logging

logger = logging.getLogger(__name__)




class BaseDiagramExtractor:
    def __init__(self, nlp_model, ner_model=None):
        self.nlp = nlp_model
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

    def _extract_use_cases(self, story_id, text):
        try:
            logger.info(f"Extracting use cases for story {story_id}")
            data = {}
            if text and isinstance(text, str):
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    pass
            
            # 1. Try to get data from the Model Output (Primary)
            if 'groq_output' in data and 'use_case' in data['groq_output']:
                uc_name = data['groq_output']['use_case']
                actor_name = data['groq_output'].get('actor')
                
                if actor_name:
                    self._add_class(actor_name, stereotype="actor", source_id=story_id)
                    
                self.model_elements.append({
                    'type': 'UseCase',
                    'data': {'name': uc_name},  # Keep original spaces
                    'source_id': story_id
                })
                
                if actor_name:
                    self._add_relationship(actor_name, uc_name, "-->", source_id=story_id)
            else:   # Fallback to regex/NLP (Secondary)
                doc = self._process_text(text)
                actors = []
                for ent in doc.ents:
                    if ent.label_ == "ACTOR":

                        actors.append(ent.text)
                        self._add_class(ent.text, stereotype="actor", source_id=story_id)
                
                # ALWAYS check for "As a X" pattern to capture Administrator even if Model found false positives
                # Allow optional "a/an" for cases like "As Administrator"
                actor_match = re.search(r"As (?:an? )?(.*?)(?:,|$)", text, re.IGNORECASE)
                if actor_match:
                    actor_clean = actor_match.group(1).strip()
                    if actor_clean not in actors: # Avoid duplicates
                        print(f"DEBUG: Regex found actor: {actor_clean}")
                        actors.append(actor_clean)
                        self._add_class(actor_clean, stereotype="actor", source_id=story_id)

                # If no actors found by ANY means...
                if not actors: 
                     pass 


                # IMPROVED REGEX (Capture full phrase after "want to")
                # Matches "want to [everything until comma or period]"
                match = re.search(r"want to\s+(.*?)(?:,|$|\.)", text, re.IGNORECASE)
                
                if match:
                    # Strip whitespace but keep internal spaces
                    use_case_name = match.group(1).strip().capitalize()
                    
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
