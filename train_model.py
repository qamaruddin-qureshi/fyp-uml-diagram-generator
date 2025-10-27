import spacy
import os
import json
from spacy.tokens import DocBin
from spacy.cli.init_config import init_config
from spacy.cli.train import train
import shutil
from sklearn.model_selection import train_test_split


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

        # Generate entity spans for each field
        for key, label in fields.items():
            value = groq_output.get(key)
            if not value:
                continue

            if isinstance(value, list):
                for v in value:
                    start = text.find(str(v))
                    if start != -1:
                        end = start + len(str(v))
                        span = doc.char_span(start, end, label=label)
                        if span:
                            ents.append(span)
            else:
                start = text.find(str(value))
                if start != -1:
                    end = start + len(str(value))
                    span = doc.char_span(start, end, label=label)
                    if span:
                        ents.append(span)

        doc.ents = ents
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
