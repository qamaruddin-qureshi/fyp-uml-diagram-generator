# FYP UML Diagram Generator

## Project Overview
This project is an advanced **AI-powered UML Diagram Generator** capable of transforming natural language User Stories into professional UML diagrams (Class, Use Case, Sequence, and Activity). It uses a hybrid pipeline combining NLP (spaCy) for precise entity extraction and logical analysis for relationship mapping.

Key Features:
-   **Multi-Diagram Support**: Generates Class, Use Case, Sequence, and Activity diagrams from the same input stories.
-   **AI-Driven Extraction**: Uses custom-trained spaCy NER models + fallback for robust extraction.
-   **Regression Testing**: Includes a "Golden Master" verification system to prevent regressions.
-   **Deterministic Output**: Ensures consistent diagram generation for testing stability.

## Class Diagram Notation
The generator uses standard PlantUML arrow notation to represent relationships in Class Diagrams:

| Relationship | Notation | Description |
| :--- | :---: | :--- |
| **Association** | `-->` | Solid line with open arrow. Represents a general "uses" or link. |
| **Inheritance** | `--\|>` | Solid line with hollow triangle. "Is-a" relationship (e.g., Cat --\|> Animal). |
| **Realization** | `..\|>` | Dashed line with hollow triangle. Interface implementation. |
| **Dependency** | `..>` | Dashed line with open arrow. "Depends-on" relationship. |
| **Aggregation** | `o--` | Solid line with hollow diamond. "Has-a" relationship (weak/shared ownership). |
| **Composition** | `*--` | Solid line with filled diamond. "Part-of" relationship (strong/exclusive ownership). |

## Requirements
Ensure you have the following dependencies installed (see `requirements.txt` for versions):
*   Python 3.x
*   Java (for PlantUML JAR execution)
*   Graphviz (optional, for some PlantUML layouts)

**Python Packages**:
```bash
pip install -r requirements.txt
```
*Note: You may need to download the `en_core_web_lg` spaCy model:*
```bash
python -m spacy download en_core_web_lg
```

## How to Run

### 1. Hybrid Server (Backend)
Run the main Flask application which handles diagram generation requests:
```bash
python main.py
```
Or use the wrapper script:
```bat
start-hybrid.bat
```
The server typically runs on `http://localhost:5000`.

### 2. Regression Testing System
This project includes a robust regression testing suite (`user_stories/verify_stories.py`) that compares generated diagrams against known "Golden Masters" to ensure correctness.

**Run All Tests**:
```bash
python user_stories/verify_stories.py
```

**Run Specific Suite**:
```bash
python user_stories/verify_stories.py --suite E_Commerce
```

**Update Golden Masters**:
*Use this ONLY when you have intentionally modified logic and verified the new output is correct.*
```bash
python user_stories/verify_stories.py --update-gold
```

**Run for specific Diagram Type**:
The verification script automatically checks Class, Use Case, Sequence, and Activity diagrams if defined in the suite.

## Project Structure
*   `main.py`: Entry point for the Flask backend.
*   `uml_extractors.py`: Core logic for NLP extraction of UML elements using spaCy.
*   `uml_generator.py`: Converts extracted elements into PlantUML code and generates images.
*   `user_stories/`: Contains User Story datasets and the Regression Test suite.
    *   `verify_stories.py`: The testing script.
    *   `golden_puml/`: Directory containing the "Truth" diagrams for regression.
*   `static/` & `generated_puml/`: Output directories for generated assets.

## Notes
*   **PlantUML**: The project uses `plantuml.jar` (included in root) to render diagrams. Ensure Java is in your system PATH.
