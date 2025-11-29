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


def convert_json_to_spacy(json_file_path, output_path="./train.spacy"):
    nlp = spacy.blank("en")
    db = DocBin()

    print(f"Loading training data from {json_file_path}...")
    with open(json_file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    doc_count = 0
    skipped_count = 0

    for item in data:
        # Expecting keys: user_story and groq_output
        if not isinstance(item, dict) or "user_story" not in item or "groq_output" not in item:
            print(f"Warning: Skipping malformed item: {item}")
            skipped_count += 1
            continue

        text = item["user_story"]
        
        groq_output = item.get("groq_output") 
        
        if not isinstance(groq_output, dict):
            print(f"Warning: Skipping malformed groq_output in item: {item}")
            skipped_count += 1
            continue

        doc = nlp.make_doc(text)
        ents = []

        # Extended field mapping (all keys)
        fields = {
            "actor": "ACTOR",
            "class": "CLASS",
            "methods": "METHOD",
            "attributes": "ATTRIBUTE",
            "use_case": "USE_CASE",
            "relationship": "RELATIONSHIP",
            "visibility": "VISIBILITY",
            "multiplicity": "MULTIPLICITY",
            "interaction": "INTERACTION",
            "flow_steps": "FLOW_STEP"
        }

        # Improved entity span matching: partial matches, synonyms, and fallback annotation
        import difflib
        def find_best_span(text, value):
            # Try exact match first
            start = text.find(str(value))
            if start != -1:
                return start, start + len(str(value))
            # Try partial match (longest matching substring)
            words = str(value).split()
            for w in words:
                if len(w) > 2:
                    idx = text.lower().find(w.lower())
                    if idx != -1:
                        return idx, idx + len(w)
            # Try fuzzy match (difflib)
            matcher = difflib.SequenceMatcher(None, text.lower(), str(value).lower())
            match = matcher.find_longest_match(0, len(text), 0, len(str(value)))
            if match.size > 3:
                return match.a, match.a + match.size
            return None, None

        for key, label in fields.items():
            value = groq_output.get(key)
            if not value:
                continue

            if isinstance(value, list):
                for v in value:
                    start, end = find_best_span(text, v)
                    if start is not None and end is not None:
                        span = doc.char_span(start, end, label=label, alignment_mode="contract")
                        if span:
                            ents.append((span.start, span.end, label))
                    else:
                        # Fallback: annotate first word as entity
                        v_str = str(v)
                        if v_str:
                            idx = text.lower().find(v_str.split()[0].lower())
                            if idx != -1:
                                span = doc.char_span(idx, idx + len(v_str.split()[0]), label=label, alignment_mode="contract")
                                if span:
                                    ents.append((span.start, span.end, label))
            else:
                start, end = find_best_span(text, value)
                if start is not None and end is not None:
                    span = doc.char_span(start, end, label=label, alignment_mode="contract")
                    if span:
                        ents.append((span.start, span.end, label))
                else:
                    # Fallback: annotate first word as entity
                    value_str = str(value)
                    if value_str:
                        idx = text.lower().find(value_str.split()[0].lower())
                        if idx != -1:
                            span = doc.char_span(idx, idx + len(value_str.split()[0]), label=label, alignment_mode="contract")
                            if span:
                                ents.append((span.start, span.end, label))

        # Remove overlapping entities and sort by start position
        ents = remove_overlapping_entities(ents)
        
        # Convert tuples back to spans
        filtered_spans = []
        for start, end, label in ents:
            span = doc[start:end]
            if span.text.strip():  # Only add non-empty spans
                span.label_ = label
                filtered_spans.append(span)
        
        doc.ents = filtered_spans
        db.add(doc)
        doc_count += 1

    db.to_disk(output_path)
    print(f"Created {output_path} with {doc_count} documents. Skipped: {skipped_count}.")
    return doc_count > 0


def create_config_file(output_path="./config.cfg"):
    config = init_config(lang="en", pipeline=["ner"], optimize="accuracy")
    config["paths"]["vectors"] = "en_core_web_lg"
    with open(output_path, "w") as f:
        f.write(config.to_str())
    print(f"Created {output_path}.")


def run_training(config_path="./config.cfg", train_data_path="./train.spacy", output_model_path="./my_uml_model"):
    print("\n--- Starting Model Training ---")
    try:
        train(
            config_path=config_path,
            output_path=output_model_path,
            overrides={
                "paths.train": "./train.spacy",
                "paths.dev": "./dev.spacy"
            }
        )
        print(f"--- Training Complete! Model saved to {output_model_path} ---")
    except Exception as e:
        print(f"Training Error: {e}")


if __name__ == "__main__":
    JSON_DATA_FILE = "training_data.json"

    if not os.path.exists(JSON_DATA_FILE):
        print(f"Error: {JSON_DATA_FILE} not found.")
    else:
        # Clean previous artifacts
        for file in ["train.spacy", "dev.spacy", "config.cfg"]:
            if os.path.exists(file):
                os.remove(file)
                print(f"Removed old {file}.")
        if os.path.exists("./my_uml_model"):
            shutil.rmtree("./my_uml_model")
            print("Removed old model directory.")

        # Split into train/dev sets
        with open(JSON_DATA_FILE, "r", encoding="utf-8") as f:
            all_data = json.load(f)

        train_data, dev_data = train_test_split(all_data, test_size=0.2, random_state=42)

        with open("train_data.json", "w", encoding="utf-8") as f:
            json.dump(train_data, f, indent=2)
        with open("dev_data.json", "w", encoding="utf-8") as f:
            json.dump(dev_data, f, indent=2)

        success_train = convert_json_to_spacy("train_data.json", "train.spacy")
        success_dev = convert_json_to_spacy("dev_data.json", "dev.spacy")

        if success_train and success_dev:
            create_config_file()
            run_training()
        else:
            print("Training aborted due to data issues.")
