import spacy
import os
import json
from spacy.tokens import DocBin
from spacy.cli.init_config import init_config
from spacy.cli.train import train
import shutil
from sklearn.model_selection import train_test_split


def remove_overlapping_entities(entities):
    """
    Remove overlapping entities, keeping the longer span when there's overlap.
    Entities should be tuples of (start, end, label).
    Returns a sorted list of non-overlapping entities.
    """
    if not entities:
        return []
    
    # Sort by start position, then by length (longest first)
    sorted_entities = sorted(entities, key=lambda x: (x[0], -(x[1] - x[0])))
    
    # Remove overlaps
    filtered = []
    for entity in sorted_entities:
        start, end, label = entity
        
        # Check if this entity overlaps with any already accepted entity
        is_overlapping = False
        for existing_start, existing_end, _ in filtered:
            # Check for any kind of overlap
            if not (end <= existing_start or start >= existing_end):
                is_overlapping = True
                break
        
        if not is_overlapping:
            filtered.append(entity)
    
    # Sort by start position for spaCy
    return sorted(filtered, key=lambda x: x[0])


def convert_architecture_json_to_spacy(json_file_path, output_train_path="./architecture_train.spacy", output_dev_path="./architecture_dev.spacy"):
    """
    Convert architecture training data to spaCy format.
    Expects JSON with architecture_narration and architecture_output/deployment_output fields.
    """
    nlp = spacy.blank("en")
    
    print(f"Loading architecture training data from {json_file_path}...")
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    all_docs = []
    doc_count = 0
    skipped_count = 0

    for item in data:
        if not isinstance(item, dict):
            print(f"Warning: Skipping malformed item: {item}")
            skipped_count += 1
            continue
        
        # Handle nested structure: architecture_narration can be string or object with 'text' field
        arch_narration = item.get("architecture_narration")
        if arch_narration is None:
            print(f"Warning: Skipping item without architecture_narration")
            skipped_count += 1
            continue
            
        if isinstance(arch_narration, dict):
            text = arch_narration.get("text", "")
        elif isinstance(arch_narration, str):
            text = arch_narration
        else:
            print(f"Warning: Skipping item with invalid architecture_narration type: {type(arch_narration)}")
            skipped_count += 1
            continue
        
        if not text or not text.strip():
            print(f"Warning: Skipping item with empty text")
            skipped_count += 1
            continue
        
        # Skip template entries
        if "TEMPLATE" in text or "[COMPONENT_NAME]" in text:
            print(f"Skipping template entry")
            skipped_count += 1
            continue
        
        arch_output = item.get("architecture_output", {})
        deploy_output = item.get("deployment_output", {})
        
        doc = nlp.make_doc(text)
        ents = []

        # Helper function to find entity span in text
        def find_span(text, value):
            value_str = str(value).strip()
            start = text.lower().find(value_str.lower())
            if start != -1:
                return start, start + len(value_str)
            # Try word-by-word matching
            words = value_str.split()
            for word in words:
                if len(word) > 2:
                    idx = text.lower().find(word.lower())
                    if idx != -1:
                        return idx, idx + len(word)
            return None, None

        # Extract COMPONENT entities
        components = arch_output.get("components", [])
        for comp in components:
            # Handle both string format and dict format
            if isinstance(comp, str):
                comp_name = comp
            elif isinstance(comp, dict):
                comp_name = comp.get("name", "")
            else:
                continue
                
            if comp_name:
                start, end = find_span(text, comp_name)
                if start is not None:
                    ents.append((start, end, "COMPONENT"))

        # Extract EXTERNAL_SYSTEM entities
        external_systems = arch_output.get("external_systems", [])
        for sys in external_systems:
            # Handle both string format and dict format
            if isinstance(sys, str):
                sys_name = sys
            elif isinstance(sys, dict):
                sys_name = sys.get("name", "")
            else:
                continue
                
            if sys_name:
                start, end = find_span(text, sys_name)
                if start is not None:
                    ents.append((start, end, "EXTERNAL_SYSTEM"))

        # Extract INTERFACE entities
        interfaces = arch_output.get("interfaces", [])
        for iface in interfaces:
            # Handle both string format and dict format
            if isinstance(iface, str):
                iface_name = iface
            elif isinstance(iface, dict):
                iface_name = iface.get("name", "")
            else:
                continue
                
            if iface_name:
                start, end = find_span(text, iface_name)
                if start is not None:
                    ents.append((start, end, "INTERFACE"))

        # Extract NODE entities from deployment output
        nodes = deploy_output.get("nodes", [])
        for node in nodes:
            node_name = node.get("name", "")
            start, end = find_span(text, node_name)
            if start is not None:
                ents.append((start, end, "NODE"))
            
            # Also mark node type as ENVIRONMENT_TYPE if present
            node_type = node.get("type", "")
            if node_type:
                start, end = find_span(text, node_type)
                if start is not None:
                    ents.append((start, end, "ENVIRONMENT_TYPE"))

        # Extract DEVICE entities
        devices = deploy_output.get("devices", [])
        for device in devices:
            # Handle both string format and dict format
            if isinstance(device, str):
                device_name = device
            elif isinstance(device, dict):
                device_name = device.get("name", "")
            else:
                continue
                
            if device_name:
                start, end = find_span(text, device_name)
                if start is not None:
                    ents.append((start, end, "DEVICE"))

        # Extract ARTIFACT entities (deployed components)
        artifacts = deploy_output.get("artifacts", [])
        for artifact in artifacts:
            # Handle both string format and dict format
            if isinstance(artifact, str):
                artifact_name = artifact
            elif isinstance(artifact, dict):
                artifact_name = artifact.get("name", "")
            else:
                continue
                
            if artifact_name:
                start, end = find_span(text, artifact_name)
                if start is not None:
                    ents.append((start, end, "ARTIFACT"))

        # Extract TECHNOLOGY entities
        technologies = arch_output.get("technologies", [])
        for tech in technologies:
            # Handle both string format and dict format
            if isinstance(tech, str):
                tech_name = tech
            elif isinstance(tech, dict):
                tech_name = tech.get("name", "")
            else:
                continue
                
            if tech_name:
                start, end = find_span(text, tech_name)
                if start is not None:
                    ents.append((start, end, "TECHNOLOGY"))

        # Extract ENVIRONMENT entities
        environments = deploy_output.get("environments", [])
        for env in environments:
            # Handle both string format and dict format
            if isinstance(env, str):
                env_name = env
            elif isinstance(env, dict):
                env_name = env.get("name", "")
            else:
                continue
                
            if env_name:
                start, end = find_span(text, env_name)
                if start is not None:
                    ents.append((start, end, "ENVIRONMENT"))

        # Extract RELATIONSHIP entities from relationships list
        relationships = arch_output.get("relationships", [])
        for rel in relationships:
            if isinstance(rel, dict):
                # Extract the relationship type/relation
                relation = rel.get("relation", "")
                if relation:
                    start, end = find_span(text, relation)
                    if start is not None:
                        ents.append((start, end, "RELATIONSHIP"))

        # Remove overlapping entities
        ents = remove_overlapping_entities(ents)

        if ents:
            doc.ents = [doc.char_span(start, end, label=label) for start, end, label in ents if doc.char_span(start, end, label=label)]
            all_docs.append(doc)
            doc_count += 1
        else:
            print(f"Warning: No entities found for narration: {text[:100]}...")
            skipped_count += 1

    print(f"✅ Processed {doc_count} architecture narrations")
    print(f"⚠️ Skipped {skipped_count} entries")

    if doc_count == 0:
        print("❌ No valid training data found!")
        return

    # Split into train and dev sets
    train_docs, dev_docs = train_test_split(all_docs, test_size=0.2, random_state=42)
    
    # Save training set
    train_db = DocBin(docs=train_docs)
    train_db.to_disk(output_train_path)
    print(f"✅ Training data saved to {output_train_path} ({len(train_docs)} examples)")
    
    # Save dev set
    dev_db = DocBin(docs=dev_docs)
    dev_db.to_disk(output_dev_path)
    print(f"✅ Dev data saved to {output_dev_path} ({len(dev_docs)} examples)")


def create_architecture_config():
    """Create spaCy config for architecture NER model."""
    config_path = "architecture_config.cfg"
    
    print("Creating architecture model config...")
    
    # Initialize config with NER pipeline
    os.system(f'python -m spacy init config {config_path} --lang en --pipeline ner --optimize accuracy')
    
    print(f"✅ Config created at {config_path}")
    print("📝 You may need to manually edit the config file to adjust paths:")
    print("   - train: ./architecture_train.spacy")
    print("   - dev: ./architecture_dev.spacy")
    
    return config_path


def train_architecture_model(config_path="architecture_config.cfg", output_dir="./architecture_uml_model"):
    """Train the architecture NER model."""
    
    print(f"Starting architecture model training...")
    print(f"Config: {config_path}")
    print(f"Output: {output_dir}")
    
    if not os.path.exists(config_path):
        print(f"❌ Config file not found: {config_path}")
        print("Run create_architecture_config() first")
        return
    
    # Train using spaCy CLI
    os.system(f'python -m spacy train {config_path} --output {output_dir} --paths.train ./architecture_train.spacy --paths.dev ./architecture_dev.spacy')
    
    print(f"✅ Architecture model training complete!")
    print(f"📁 Model saved to: {output_dir}/model-best")


def main():
    """Main training pipeline for architecture model."""
    
    print("=" * 60)
    print("ARCHITECTURE UML MODEL TRAINING PIPELINE")
    print("=" * 60)
    
    # Step 1: Convert training data
    print("\n[Step 1] Converting JSON to spaCy format...")
    convert_architecture_json_to_spacy(
        "architecture_training_data.json",
        "architecture_train.spacy",
        "architecture_dev.spacy"
    )
    
    # Step 2: Create config (if doesn't exist)
    config_path = "architecture_config.cfg"
    if not os.path.exists(config_path):
        print("\n[Step 2] Creating spaCy config...")
        create_architecture_config()
        print("\n⚠️ IMPORTANT: Edit architecture_config.cfg to set correct data paths:")
        print("   [paths]")
        print("   train = \"architecture_train.spacy\"")
        print("   dev = \"architecture_dev.spacy\"")
        print("\nThen run this script again to train the model.")
        return
    else:
        print(f"\n[Step 2] Using existing config: {config_path}")
    
    # Step 3: Train model
    print("\n[Step 3] Training architecture NER model...")
    train_architecture_model(config_path, "./architecture_uml_model")
    
    print("\n" + "=" * 60)
    print("✅ TRAINING COMPLETE!")
    print("=" * 60)
    print(f"Model location: ./architecture_uml_model/model-best")
    print(f"To use: nlp = spacy.load('./architecture_uml_model/model-best')")


if __name__ == "__main__":
    main()
