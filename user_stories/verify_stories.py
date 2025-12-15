
import sys
import os
import json
import logging
import spacy
import argparse
import difflib

# Add parent directory to path so we can import uml_extractors and uml_generator
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from uml_extractors import ClassDiagramExtractor
from uml_generator import DiagramGenerator

# Configure logging
logging.basicConfig(level=logging.ERROR, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# --- CONFIG ---
GOLDEN_DIR = os.path.join(current_dir, "golden_puml")
OUTPUT_DIR = os.path.join(current_dir, "output_puml")

# --- TEST DATA ---

TEST_SUITES = {
    "Original_Inspector_System": [
        {"storyid": 1, "storytext": "As a researcher, I want to download reports, so that I can use them in immediate and future in talks and articles."},
        {"storyid": 2, "storytext": "As a user, I want to update my profile picture and name so my teammates recognize me."},
        {"storyid": 3, "storytext": "As an Inspection Staff Supervisor, I want to Assign Inspections, so that I can make sure the appropriate Inspector receives the work."},
        {"storyid": 4, "storytext": "As a patron, I want to view multiple versions of a report/dataset to get both timely and historical information."}
    ],
    "Cloud_Storage": [
        {"storyid": 101, "storytext": "As a User, I want to create a new folder within my cloud storage, so I can organize my files."},
        {"storyid": 102, "storytext": "As a User, I want to be able to upload files from my computer into a specific folder, so I can back up my data."},
        {"storyid": 103, "storytext": "As a User, I want to be able to download a file or an entire folder to my local device, so I can access it offline."},
        {"storyid": 104, "storytext": "As a User, I want to be able to share a file with another user via a secure link, so they can view or edit it."}
    ],
    "Cloud_Storage_Advanced": [
        {"storyid": 201, "storytext": "As a User, I want to set permissions (Read-Only or Edit) on a shared file, so I control access."},
        {"storyid": 202, "storytext": "As a User, I want the system to track version history for files, so I can revert to a previous state if needed."},
        {"storyid": 203, "storytext": "As a User, I want to be able to search for files by name or content keywords, so I can locate specific documents quickly."}
    ],
    "Cloud_Storage_Management": [
        {"storyid": 301, "storytext": "As a System, I want to alert the user when their storage capacity reaches 90%, so they can manage their space."},
        {"storyid": 302, "storytext": "As a User, I want to be able to move a file from one folder to another using a drag-and-drop interface, so organization is simple."},
        {"storyid": 303, "storytext": "As a User, I want to be able to recover deleted files from a 'Trash' or 'Recycle Bin' for up to 30 days, so I can undo mistakes."}
    ],
    "CRM_System": [
        {"storyid": 401, "storytext": "As a Sales Rep, I want to create a new contact record for a potential client, so I can start tracking interactions."},
        {"storyid": 402, "storytext": "As a Sales Rep, I want to log an activity (e.g., call, email, meeting) against a contact or account, so the history is complete."},
        {"storyid": 403, "storytext": "As a Sales Rep, I want to create a new sales opportunity (lead) and track its value and stage in the pipeline, so I can forecast revenue."},
        {"storyid": 404, "storytext": "As a Manager, I want to view a dashboard of the current sales pipeline and total revenue forecast, so I can manage the team's performance."}
    ],
    "E_Commerce": [
        {"storyid": 501, "storytext": "As a Customer, I want to register Account with emailAddress and password."},
        {"storyid": 502, "storytext": "As a Customer, i want to login to my account."},
        {"storyid": 503, "storytext": "As a Customer, I want to view Product details by category."},
        {"storyid": 504, "storytext": "As a Customer, I want to add a Product to the ShoppingCart."},
        {"storyid": 505, "storytext": "As a Customer, I want to update ShoppingCart Product quantity."},
        {"storyid": 506, "storytext": "As a Customer, I want to place an Order with shippingAddress."},
        {"storyid": 507, "storytext": "As a Customer, I want to view my OrderHistory for orderDate and totalAmount."},
        {"storyid": 508, "storytext": "As a Customer, I want to manage my Addresses (add, edit, delete)."},
        {"storyid": 509, "storytext": "As Administrator, I want to manage a Product (add, edit, delete) including name, price, and description."},
        {"storyid": 510, "storytext": "As Administrator, I want to manage a Category (create, rename, delete)."},
        {"storyid": 511, "storytext": "As Administrator, I want to view Order details."}
    ]
}

def verify_suite(suite_name, stories, update_gold=False):
    print(f"\nVerifying Suite: {suite_name}")
    
    # 1. Load Models (Simplified for speed in output)
    try:
        nlp_standard = spacy.load("en_core_web_lg")
    except:
        nlp_standard = spacy.blank("en")
    
    MODEL_PATH = os.path.join(parent_dir, "my_uml_model", "model-best")
    nlp_ner = None
    if os.path.exists(MODEL_PATH):
        try:
            nlp_ner = spacy.load(MODEL_PATH)
        except:
            pass

    # 2. Extract
    extractor = ClassDiagramExtractor(nlp_standard, ner_model=nlp_ner)
    elements = extractor.extract(stories)

    # 3. Generate Diagram
    generator = DiagramGenerator()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(GOLDEN_DIR, exist_ok=True)
    
    project_id = f"test_{suite_name}"
    generator.generate_diagram(project_id, "class", elements, static_dir=os.path.join(current_dir, "output_static"), puml_dir=OUTPUT_DIR)
    
    # 4. Compare with Golden
    generated_path = os.path.join(OUTPUT_DIR, f"class_{project_id}.puml")
    golden_path = os.path.join(GOLDEN_DIR, f"class_{project_id}.puml")
    
    if not os.path.exists(generated_path):
        print(f"FAILED: Generation failed for {suite_name}")
        return False

    with open(generated_path, 'r') as f:
        generated_content = f.read()

    golden_content = ""
    if os.path.exists(golden_path):
        with open(golden_path, 'r') as f:
            golden_content = f.read()
    else:
        print(f"WARNING: No golden master found for {suite_name}")

    # Normalize newlines
    generated_content = generated_content.strip().replace('\r\n', '\n')
    golden_content = golden_content.strip().replace('\r\n', '\n')

    if generated_content != golden_content:
        if update_gold:
            print(f"UPDATE: Updating golden master for {suite_name}")
            with open(golden_path, 'w') as f:
                f.write(generated_content)
            return True
        else:
            print(f"FAILED: Mismatch detected for {suite_name}")
            print("--- DIFF ---")
            diff = difflib.unified_diff(
                golden_content.splitlines(), 
                generated_content.splitlines(), 
                fromfile='Golden', 
                tofile='Generated', 
                lineterm=''
            )
            for line in diff:
                print(line)
            print("------------")
            return False
    else:
        print(f"PASS: {suite_name}")
        return True

def run_all():
    parser = argparse.ArgumentParser(description="Run regression tests for User Stories.")
    parser.add_argument("--update-gold", action="store_true", help="Update Golden Master files with current output.")
    parser.add_argument("--suite", type=str, help="Run only a specific test suite (e.g., Cloud_Storage).")
    parser.add_argument("--force-all", action="store_true", help="Force update of all golden master files (overrides safety lock).")
    args = parser.parse_args()

    # Safety Lock Logic
    if args.update_gold:
        if not args.suite and not args.force_all:
            print("ERROR: Safety Lock Engaged!")
            print("  You cannot update ALL golden master files at once without explicit confirmation.")
            print("  Usage:")
            print("    1. Update ONE suite: python verify_stories.py --update-gold --suite <SuiteName>")
            print("    2. Force ALL suites: python verify_stories.py --update-gold --force-all")
            sys.exit(1)

    # Determine validation scope
    suites_to_run = {}
    if args.suite:
        if args.suite in TEST_SUITES:
            suites_to_run[args.suite] = TEST_SUITES[args.suite]
        else:
            print(f"ERROR: Suite '{args.suite}' not found.")
            print(f"Available suites: {list(TEST_SUITES.keys())}")
            sys.exit(1)
    else:
        suites_to_run = TEST_SUITES

    results = {}
    for name, stories in suites_to_run.items():
        results[name] = verify_suite(name, stories, update_gold=args.update_gold)

    print("\n=== SUMMARY ===")
    all_passed = True
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        if not passed: all_passed = False
        print(f"{name}: {status}")
    
    if not all_passed:
        sys.exit(1)

if __name__ == "__main__":
    run_all()
