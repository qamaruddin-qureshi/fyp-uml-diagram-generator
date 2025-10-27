# Hybrid Architecture Setup Guide

This guide explains how to run the Flask backend and Next.js frontend together.

## Architecture Overview

```
┌──────────────────────────┐
│  Next.js Frontend        │
│  Port: 3000              │
│  - React Components      │
│  - Client-side State     │
│  - UI Layer              │
└────────────┬─────────────┘
             │ API Requests (REST)
             ↓
┌──────────────────────────┐
│  Flask Backend           │
│  Port: 5000              │
│  - NLP Processing        │
│  - Database              │
│  - Diagram Generation    │
└──────────────────────────┘
```

## Prerequisites

### Backend Requirements
- Python 3.8+
- PostgreSQL database
- Java (for PlantUML)
- SpaCy NLP model

### Frontend Requirements
- Node.js 18+
- npm or yarn

## Step-by-Step Setup

### 1. Backend Setup

```bash
# Navigate to backend directory
cd d:\fyp-uml-diagram-generator

# Ensure virtual environment is activated
.\vr\Scripts\activate

# Install/update dependencies (if needed)
pip install -r requirements.txt

# Set environment variables
# Create .env file with:
DB_USER=docker
DB_PASSWORD=docker
DB_NAME=postgres
DB_HOST=localhost
DB_PORT=5432

# Run database migrations
python run_migration.py

# Start Flask server
python main.py
# Flask will run on http://localhost:5000
```

### 2. Frontend Setup

```bash
# Navigate to frontend directory
cd d:\fyp-uml-diagram-generator\frontend

# Install Node dependencies
npm install

# Create/update .env.local with:
NEXT_PUBLIC_API_URL=http://localhost:5000
FLASK_API_URL=http://localhost:5000

# Start Next.js development server
npm run dev
# Next.js will run on http://localhost:3000
```

### 3. Access the Application

1. Open browser to `http://localhost:3000`
2. Register a new account or login
3. Create projects and generate diagrams!

## Environment Variables

### Backend (.env)
```env
DB_USER=docker
DB_PASSWORD=docker
DB_NAME=postgres
DB_HOST=localhost
DB_PORT=5432
```

### Frontend (.env.local)
```env
NEXT_PUBLIC_API_URL=http://localhost:5000
FLASK_API_URL=http://localhost:5000
```

## Running in Multiple Terminals

### Terminal 1: Flask Backend
```bash
cd d:\fyp-uml-diagram-generator
.\vr\Scripts\activate
python main.py
```
Output should show:
```
Starting Production Server (Waitress) on http://localhost:5000...
Serving on http://[::1]:5000
Serving on http://127.0.0.1:5000
```

### Terminal 2: Next.js Frontend
```bash
cd d:\fyp-uml-diagram-generator\frontend
npm run dev
```
Output should show:
```
▲ Next.js 14.1.0
- Local:        http://localhost:3000
```

### Terminal 3 (Optional): Database/Services
If using Docker for PostgreSQL:
```bash
docker-compose up
```

## API Integration Points

The frontend communicates with backend through these endpoints:

### Authentication
```
POST /auth/register
{
  "username": "user",
  "password": "password"
}

POST /auth/login
{
  "username": "user",
  "password": "password"
}
```

### Projects
```
GET /projects
Returns: [{ ProjectID, ProjectName, UserID }, ...]

POST /project/new
{
  "project_name": "My Project"
}

GET /project/{id}
Returns: { ProjectID, ProjectName, UserID, stories_text, ... }

POST /project/{id}/update
{
  "user_stories": "...",
  "diagram_type": "class"
}
```

### Static Files
```
GET /static/{diagram_type}_{project_id}.png
Returns PNG image
```

## Troubleshooting

### Port Already in Use
- **Port 5000 (Flask)**:
  ```bash
  # Find process using port 5000
  netstat -ano | findstr :5000
  # Kill process
  taskkill /PID {PID} /F
  ```

- **Port 3000 (Next.js)**:
  ```bash
  # Run on different port
  npm run dev -- -p 3001
  ```

### CORS Issues
- Ensure Next.js `next.config.js` has rewrites configured
- Backend Flask-CORS should be installed: `pip install flask-cors`

### Database Connection Error
- Verify PostgreSQL is running
- Check environment variables
- Run migrations: `python run_migration.py`

### Frontend Can't Find Images
- Ensure Flask backend generated diagram files in `/static/`
- Check image filename matches pattern: `{diagram_type}_{project_id}.png`
- Verify Flask static directory is accessible

## Development Workflow

### 1. Feature Development
- Backend: Add/modify API endpoints in `projectcontroller.py`
- Frontend: Create/modify React components in `src/app/` or `src/components/`

### 2. Testing
- Test API manually with Postman or curl
- Test UI in browser at `http://localhost:3000`
- Check console for errors

### 3. Database Changes
- Modify `models.py` if schema changes needed
- Run migrations
- Restart Flask server

## Production Deployment

### Option 1: Traditional Servers
- **Backend**: Deploy Flask to:
  - AWS EC2
  - DigitalOcean
  - Heroku
  - PythonAnywhere

- **Frontend**: Deploy Next.js to:
  - Vercel (recommended)
  - Netlify
  - AWS Amplify
  - Self-hosted Node server

### Option 2: Docker Containerization
See `Dockerfile` examples in README files for both backend and frontend.

### Option 3: AWS/Cloud Native
- Backend: AWS ECS/Lambda
- Frontend: CloudFront + S3 or Amplify
- Database: RDS PostgreSQL

## Monitoring & Debugging

### Backend Logs
```bash
# Already shown in terminal running Flask
# Look for log messages with:
# - INFO
# - WARNING
# - ERROR
```

### Frontend Logs
```bash
# Open browser DevTools (F12)
# Console tab shows all client-side logs
```

### Network Requests
```bash
# Browser DevTools > Network tab
# Shows all API calls to Flask backend
# Check headers, request/response bodies
```

## Performance Tips

1. **Frontend**:
   - Enable image optimization
   - Use lazy loading for diagrams
   - Implement request debouncing

2. **Backend**:
   - Cache NLP model in memory
   - Use connection pooling for database
   - Optimize PlantUML generation

3. **Database**:
   - Add indexes on frequently queried fields
   - Regular VACUUM/ANALYZE

## Next Steps

1. ✅ Verify both servers are running
2. ✅ Test login/registration
3. ✅ Create a project and generate a diagram
4. ✅ Verify diagram displays correctly
5. 🚀 Start using the application!

## Support

For issues, check:
1. Console logs (both frontend and backend)
2. This guide's troubleshooting section
3. Project README files
4. Flask/Next.js official documentation

---

**Happy developing! 🚀**
