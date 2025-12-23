
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

from uml_extractors import (
    ClassDiagramExtractor,
    UseCaseDiagramExtractor,
    SequenceDiagramExtractor,
    ActivityDiagramExtractor,
    ComponentDiagramExtractor,
    DeploymentDiagramExtractor
)
from uml_generator import DiagramGenerator
try:
    import structural_test_data as std
    import importlib
    importlib.reload(std)
    from structural_test_data import COMPONENT_TEST_DATA, DEPLOYMENT_TEST_DATA
    print(f"DEBUG source: {std.__file__}")
    print(f"DEBUG count: {len(COMPONENT_TEST_DATA)}")
except ImportError:
    # Fallback if running from root
    from user_stories.structural_test_data import COMPONENT_TEST_DATA, DEPLOYMENT_TEST_DATA
    import user_stories.structural_test_data as std
    print(f"DEBUG source: {std.__file__}")


# Configure logging
logging.basicConfig(level=logging.ERROR, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# --- CONFIG ---
GOLDEN_DIR = os.path.join(current_dir, "golden_puml")
OUTPUT_DIR = os.path.join(current_dir, "output_puml")

# --- TEST DATA ---
# (TEST_SUITES dictionary is preserved in the file content, skipping re-definition for brevity in tool call if possible, 
# but replace_file_content requires replacing the TARGET block. I will avoid touching TEST_SUITES and only replace the verification logic below it if I can targeting line ranges.)

# Since TEST_SUITES is large, I will target the imports and the verify_suite function separately or use multi-replace?
# The tool allow replace_file_content for single contiguous block.
# Imports are at the top. Function is at the bottom.
# I should use multi_replace.

# Let's switch to multi_replace.


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
        {"storyid": 509, "storytext": "As Administrator, I want to add, edit, delete a Product including name, price, and description."},
        {"storyid": 510, "storytext": "As Administrator, I want to create, rename, delete a Category."},
        {"storyid": 511, "storytext": "As Administrator, I want to view Order details."}
    ],
    "CRM_Advanced": [
        {"storyid": 601, "storytext": "As a Sales Rep, I want to be able to set a follow-up reminder for a specific contact, so I don't miss important communication."},
        {"storyid": 602, "storytext": "As a Sales Rep, I want to view all contacts associated with a specific company (account), so I understand the organizational structure."},
        {"storyid": 603, "storytext": "As a Manager, I want to assign ownership of a lead to a specific Sales Rep, so accountability is clear."},
        {"storyid": 604, "storytext": "As a System, I want to send an automated welcome email to a new contact when they are entered into the system, so they are immediately engaged."},
        {"storyid": 605, "storytext": "As a Sales Rep, I want to mark an opportunity as 'Closed Won' when a deal is finalized, so the sales record is updated."},
        {"storyid": 606, "storytext": "As a User, I want to be able to export a list of leads for a specific campaign, so I can use it for targeted marketing."}
    ]
}

def verify_suite(suite_name, stories, update_gold=False):
    print(f"\nVerifying Suite: {suite_name}")
    
    # 1. Load Models (Simplified for speed in output)
    try:
        nlp_standard = spacy.load("en_core_web_lg")
    except:
        nlp_standard = spacy.blank("en")
    
    MODEL_PATH = os.path.join(parent_dir, "behavioral_uml_model", "model-best")
    nlp_ner = None
    if os.path.exists(MODEL_PATH):
        try:
            nlp_ner = spacy.load(MODEL_PATH)
            print(f"Loaded NER model from: {MODEL_PATH}")
        except:
            print(f"Warning: Failed to load model at {MODEL_PATH}")
            pass
    else:
        print(f"Warning: No NER model found at {MODEL_PATH}. Using fallback/regex.")


    # Extended Regression: Verify ALL diagram types
    extractors = {
        "class": ClassDiagramExtractor,
        "use_case": UseCaseDiagramExtractor,
        "sequence": SequenceDiagramExtractor,
        "activity": ActivityDiagramExtractor
    }
    
    generator = DiagramGenerator()
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(GOLDEN_DIR, exist_ok=True)
    project_id = f"test_{suite_name}"
    
    all_passed = True

    for diagram_type, ExtractorCls in extractors.items():
        # Define Type-Specific Directories
        type_output_dir = os.path.join(OUTPUT_DIR, diagram_type)
        type_golden_dir = os.path.join(GOLDEN_DIR, diagram_type)
        type_static_dir = os.path.join(current_dir, "output_static", diagram_type)

        # Ensure directories exist
        os.makedirs(type_output_dir, exist_ok=True)
        os.makedirs(type_golden_dir, exist_ok=True)
        # static dir is created by plantuml usually, but good to be safe if passed as arg? 
        # Actually generator passes it to -o, plantuml creates it if missing? 
        # But let's create it.
        os.makedirs(type_static_dir, exist_ok=True)

        # 2. Extract
        try:
            extractor = ExtractorCls(nlp_standard, ner_model=nlp_ner)
            elements = extractor.extract(stories)
        except Exception as e:
            print(f"FAILED: Extraction error for {suite_name} ({diagram_type}): {e}")
            all_passed = False
            continue

        # 3. Generate Diagram
        try:
            # Generator expects types: 'class', 'use_case', 'sequence', 'activity'
            # Note: static_dir passed to generator is where IMAGES go. puml_dir is where PUML goes.
            generator.generate_diagram(project_id, diagram_type, elements, static_dir=type_static_dir, puml_dir=type_output_dir)
        except Exception as e:
            print(f"FAILED: Generation error for {suite_name} ({diagram_type}): {e}")
            all_passed = False
            continue
        
        # 4. Compare with Golden
        # Filename convention from generator: {type}_{project_id}.puml
        filename = f"{diagram_type}_{project_id}.puml"
        generated_path = os.path.join(type_output_dir, filename)
        golden_path = os.path.join(type_golden_dir, filename)
        
        if not os.path.exists(generated_path):
            if os.path.exists(golden_path):
                 print(f"FAILED: Regression - Output file missing for {suite_name} ({diagram_type}) but Golden exists.")
                 all_passed = False
            # If neither exists, it means extraction found no elements (e.g. no sequence messages), which is expected for some suites.
            continue

        with open(generated_path, 'r') as f:
            generated_content = f.read()

        golden_content = ""
        if os.path.exists(golden_path):
            with open(golden_path, 'r') as f:
                golden_content = f.read()
        else:
            if not update_gold:
                 print(f"WARNING: No golden master found for {suite_name} ({diagram_type})")
                 # If no golden master and NOT updating, we can't verify, but maybe shouldn't fail?
                 # For regression, missing master is usually a Fail or Warning. Defaulting to Warning for now.
        
        # Normalize newlines
        generated_content = generated_content.strip().replace('\r\n', '\n')
        golden_content = golden_content.strip().replace('\r\n', '\n')

        if generated_content != golden_content:
            if update_gold:
                print(f"UPDATE: Updating golden master for {suite_name} ({diagram_type})")
                with open(golden_path, 'w') as f:
                    f.write(generated_content)
            else:
                print(f"FAILED: Mismatch detected for {suite_name} ({diagram_type})")
                print(f"--- DIFF ({diagram_type}) ---")
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
                all_passed = False
        else:
             # Only print PASS if it passed comparison (and golden existed)
             if os.path.exists(golden_path):
                 pass # Silent success for individual types to avoid spam? Or print specific pass?
                 # print(f"PASS: {diagram_type}")

    if all_passed:
        print(f"PASS: {suite_name}")
    
    return all_passed

def verify_structural_suite(suite_name, test_data, diagram_type, update_gold=False):
    """
    Verify structural diagrams (Component, Deployment) from narrations.
    test_data: List of dicts, each having 'narration' key.
    """
    print(f"\nVerifying Structural Suite: {suite_name} ({diagram_type})")
    print(f"DEBUG: Loaded {len(test_data)} test items.")
    
    # Load NER Model (Architecture)
    nlp_standard = spacy.blank("en")
    MODEL_PATH = os.path.join(parent_dir, "architecture_uml_model", "model-best")
    nlp_ner = None
    if os.path.exists(MODEL_PATH):
        try:
            nlp_ner = spacy.load(MODEL_PATH)
            print(f"Loaded Architecture NER model from: {MODEL_PATH}")
        except:
            print(f"Warning: Failed to load model at {MODEL_PATH}")
    else:
        print(f"Warning: No Architecture NER model found at {MODEL_PATH}. Using fallback/regex.")

    # Select Extractor
    if diagram_type == 'component':
        ExtractorCls = ComponentDiagramExtractor
    elif diagram_type == 'deployment':
        ExtractorCls = DeploymentDiagramExtractor
    else:
        print(f"Error: Unknown diagram type {diagram_type}")
        return False

    generator = DiagramGenerator()
    
    # Directories
    type_output_dir = os.path.join(OUTPUT_DIR, diagram_type)
    type_golden_dir = os.path.join(GOLDEN_DIR, diagram_type)
    type_static_dir = os.path.join(current_dir, "output_static", diagram_type)
    
    os.makedirs(type_output_dir, exist_ok=True)
    os.makedirs(type_golden_dir, exist_ok=True)
    os.makedirs(type_static_dir, exist_ok=True)

    all_passed = True

    for i, item in enumerate(test_data):
        test_id = item.get('id', i+1)
        narration = item.get('narration', '')
        # Using sanitized string or just ID for filename? 
        # behavioral uses "suite_name", but here we have distinct test cases.
        # Let's use suite_name + id
        project_id = f"{suite_name}_Case_{test_id}"
        
        # 1. Extract
        try:
             # component extractor needs standard nlp + ner
            extractor = ExtractorCls(nlp_standard, ner_model=nlp_ner)
            # The extract method for Architecture extractors takes a single string `narration_text`
            elements = extractor.extract(narration)
        except Exception as e:
            print(f"FAILED: Extraction error for {project_id}: {e}")
            all_passed = False
            continue

        # 2. Generate
        try:
            generator.generate_diagram(project_id, diagram_type, elements, static_dir=type_static_dir, puml_dir=type_output_dir)
        except Exception as e:
            print(f"FAILED: Generation error for {project_id}: {e}")
            all_passed = False
            continue

        # 3. Compare
        filename = f"{diagram_type}_{project_id}.puml"
        generated_path = os.path.join(type_output_dir, filename)
        golden_path = os.path.join(type_golden_dir, filename)
        
        if not os.path.exists(generated_path):
             print(f"FAILED: Output file missing for {project_id}")
             all_passed = False
             continue

        with open(generated_path, 'r') as f:
            generated_content = f.read()

        golden_content = ""
        if os.path.exists(golden_path):
            with open(golden_path, 'r') as f:
                golden_content = f.read()
        else:
            if not update_gold:
                 print(f"WARNING: No golden master found for {project_id}")
        
        generated_content = generated_content.strip().replace('\r\n', '\n')
        golden_content = golden_content.strip().replace('\r\n', '\n')

        if generated_content != golden_content:
            if update_gold:
                print(f"UPDATE: Updating golden master for {project_id}")
                with open(golden_path, 'w') as f:
                    f.write(generated_content)
            else:
                print(f"FAILED: Mismatch for {project_id}")
                 # Optional: print diff
                all_passed = False
    
    if all_passed:
        print(f"PASS: {suite_name} ({diagram_type})")
        
    return all_passed

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

    results = {}
    
    # 1. Run Behavioral Suites
    if args.suite:
        # If specific suite requested
        if args.suite in TEST_SUITES:
            results[args.suite] = verify_suite(args.suite, TEST_SUITES[args.suite], update_gold=args.update_gold)
        # Check if it's one of the structural suites? naming convention...
        elif args.suite == "Structural_Component":
             results["Structural_Component"] = verify_structural_suite("Structural", COMPONENT_TEST_DATA, "component", update_gold=args.update_gold)
        elif args.suite == "Structural_Deployment":
             results["Structural_Deployment"] = verify_structural_suite("Structural", DEPLOYMENT_TEST_DATA, "deployment", update_gold=args.update_gold)
    else:
        # Run ALL behavioral
        for name, stories in TEST_SUITES.items():
            results[name] = verify_suite(name, stories, update_gold=args.update_gold)
        
        # Run Structural
        results["Structural_Component"] = verify_structural_suite("Structural", COMPONENT_TEST_DATA, "component", update_gold=args.update_gold)
        results["Structural_Deployment"] = verify_structural_suite("Structural", DEPLOYMENT_TEST_DATA, "deployment", update_gold=args.update_gold)

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
