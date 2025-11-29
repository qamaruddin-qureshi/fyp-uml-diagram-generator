# AI Coding Assistant Instructions for UML Diagram Generator

## Project Overview
This is a full-stack web application that generates UML diagrams from natural language user stories using machine learning. The system consists of:

- **Backend**: Flask API with PostgreSQL, spaCy NER model for entity extraction
- **Frontend**: Next.js React app with Zustand state management
- **ML Pipeline**: Custom spaCy model trained to extract UML elements (actors, classes, methods, attributes, relationships)
- **Diagram Generation**: PlantUML generates PNG images from extracted model elements

## Architecture & Data Flow

### Core Components
- `main.py`: Flask app entry point, initializes extractors and diagram generator
- `uml_extractors.py`: Four extractor classes (Class, Use Case, Sequence, Activity) that convert user stories to model elements
- `uml_generator.py`: PlantUML code generation and PNG rendering
- `models.py`: SQLAlchemy ORM models (User, Project, UserStory, ModelElement)
- `persistence.py`: Database operations layer
- `frontend/`: Next.js app with API client, Zustand stores, and React components

### Request Flow
1. User submits stories via Next.js frontend → Flask `/project/{id}/update` endpoint
2. Stories saved to `userstories` table with project association
3. SpaCy model extracts entities (actors, classes, methods, attributes) from each story
4. Extracted elements saved to `modelelements` table with foreign key to source story
5. PlantUML generates diagram from elements, saved as `{type}_{project_id}.png`

## Critical Developer Workflows

### Local Development Setup
```bash
# Start both servers (Windows)
start-hybrid.bat

# Or manually:
# Terminal 1: python main.py (Flask on :5000)
# Terminal 2: cd frontend && npm run dev (Next.js on :3000)

# Database setup (Docker)
docker-compose up postgres adminer
```

### ML Model Training
```bash
# Requires training_data.json with user stories and groq_output annotations
python train_model.py
# Outputs trained model to ./my_uml_model/model-best
```

### Database Schema
- Uses PostgreSQL with psycopg2 driver
- Tables: users, projects, userstories, modelelements
- Foreign key relationships: projects→users, userstories→projects, modelelements→projects+userstories

## Project-Specific Patterns & Conventions

### User Story Processing
- **Dual Format Support**: Stories can be plain text OR JSON with `groq_output` field containing pre-extracted entities
- **Fallback Strategy**: If spaCy model fails, falls back to regex patterns and blank English model
- **Entity Types**: ACTOR, CLASS, METHOD, ATTRIBUTE, USE_CASE, RELATIONSHIP, etc.

### Element Extraction Strategy
```python
# Pattern: Extractor classes inherit from BaseDiagramExtractor
class ClassDiagramExtractor(BaseDiagramExtractor):
    def extract(self, stories_list):
        # Process each story, extract entities, build model elements
        # Return list of {'type': 'Class', 'data': {...}, 'source_id': story_id}
```

### Diagram Generation
- **PlantUML Integration**: Requires `plantuml.jar` in project root
- **File Naming**: `{diagram_type}_{project_id}.png` in `static/` directory
- **Error Handling**: Creates red placeholder PNG if PlantUML fails

### API Response Patterns
```javascript
// Success responses include project data + diagram URL
{
  success: true,
  ProjectID: "uuid",
  ProjectName: "My Project", 
  stories_text: "...",
  diagram_url: "/static/class_uuid.png?t=timestamp"
}
```

### State Management (Frontend)
```javascript
// Zustand stores follow this pattern
const useAuthStore = create((set) => ({
  user: null,
  isAuthenticated: false,
  setUser: (user) => set({ user, isAuthenticated: !!user }),
  logout: () => set({ user: null, isAuthenticated: false })
}))
```

## Key Files & Their Roles

### Backend Core
- `main.py`: App initialization, CORS setup, blueprint registration
- `persistence.py`: All database operations (CRUD for projects/stories/elements)
- `projectcontroller.py`: Business logic for project operations
- `projectroutes.py`: Flask routes with UUID validation and auth checks

### ML Pipeline
- `train_model.py`: Converts JSON training data to spaCy format, runs training
- `config.cfg`: SpaCy training configuration (NER model with tok2vec)
- `my_uml_model/`: Trained spaCy model directory

### Frontend Architecture
- `frontend/src/lib/api.js`: Axios client with auth headers and error handling
- `frontend/src/store/`: Zustand stores (auth.js, projects.js)
- `frontend/src/app/projects/[id]/page.jsx`: Project editor with diagram preview

## Common Development Tasks

### Adding New Diagram Type
1. Create extractor class in `uml_extractors.py` inheriting from `BaseDiagramExtractor`
2. Add generation method in `uml_generator.py`
3. Update frontend diagram type selection
4. Add PlantUML template for new diagram type

### Modifying Entity Extraction
- Update `fields` mapping in `train_model.py` for new entity types
- Add extraction logic in appropriate extractor class
- Retrain model with new training data

### Database Changes
- Update SQLAlchemy models in `models.py`
- Run `Base.metadata.create_all(engine)` to sync schema
- Update persistence layer methods accordingly

### Frontend API Integration
- Add method to `api.js` following existing patterns
- Update Zustand store with new state/actions
- Handle loading/error states in components

## Dependencies & Environment

### Python Requirements
- Flask ecosystem (flask, flask-login, flask-cors, werkzeug)
- ML: spacy, scikit-learn
- Database: SQLAlchemy, psycopg2-binary
- Image: Pillow, reportlab (PDF generation)
- PlantUML: plantuml (Python wrapper)

### Environment Variables
```bash
# Database (defaults to Docker values)
DB_HOST=localhost
DB_USER=docker
DB_PASSWORD=docker
DB_NAME=postgres
DB_PORT=5432

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:5000
```

## Testing & Validation

### Manual Testing Flow
1. Create project via frontend
2. Add user stories in text area
3. Select diagram type (class/use_case/sequence/activity)
4. Click "Generate/Update Diagram"
5. Verify PNG appears in diagram preview

### Common Issues
- **PlantUML errors**: Check `plantuml.jar` exists, Java installed
- **Model loading**: Ensure `./my_uml_model/model-best` exists, fallback to blank model
- **Database connection**: Verify PostgreSQL running, credentials correct
- **CORS issues**: Frontend proxy expects Flask on port 5000

## Deployment Considerations

### Docker Setup
- `docker-compose.yml`: PostgreSQL + Adminer + Python app
- Volumes for model files, static assets, generated PUML
- Network isolation with dev-network

### Production Notes
- Use Waitress WSGI server (configured in main.py)
- Static file serving via Flask (diagrams, PUML files)
- JWT tokens stored in localStorage (frontend)
- Session management via Flask-Login

## Code Quality Patterns

### Error Handling
```python
try:
    # Operation
    result = risky_operation()
except Exception as e:
    logger.error(f"Operation failed: {e}")
    # Graceful fallback or error response
```

### Logging
- Comprehensive logging throughout backend
- DEBUG level shows all requests, database operations
- ERROR level for failures with stack traces

### Validation
- UUID format validation on all project routes
- User authentication checks on protected endpoints
- Input sanitization and length limits