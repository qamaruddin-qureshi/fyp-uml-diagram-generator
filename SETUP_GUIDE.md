# UML Generator - Setup Guide

This guide will help you set up the UML Generator with user authentication.

## Overview

The UML Generator now supports user authentication with the following features:
- **Registered Users**: Can create multiple projects and update them
- **Guest Users**: Can create new projects but CANNOT update existing projects (must create a new project each time)

## Database Setup

### Step 1: Run the Database Migration

Before running the application, you need to update your database schema:

1. Open SQL Server Management Studio (SSMS)
2. Connect to your SQL Server instance
3. Open `database_migration.sql`
4. Execute the script

This will:
- Create a `Users` table for storing user accounts
- Add a `UserID` column to the `Projects` table
- Set up foreign key relationships

### Step 2: Update Database Connection

Update the database connection settings in `main.py` (lines 24-29):
```python
DB_CONFIG = {
    'driver': '{ODBC Driver 17 for SQL Server}',
    'server': 'YOUR_SERVER_NAME',
    'database': 'UML_Project_DB',
    'trusted_connection': 'yes'
}
```

## Installation

### Step 1: Install Dependencies

```bash
# Activate your virtual environment
source vr/Scripts/activate  # Linux/Mac
# or
vr\Scripts\activate  # Windows

# Install required packages
pip install -r requirements.txt
```

### Step 2: Install Spacy Model

You'll need to download the Spacy model:
```bash
python -m spacy download en_core_web_lg
```

## Running the Application

```bash
python main.py
```

The application will start on `http://127.0.0.1:5000`

## Usage

### For Guest Users

1. Visit the home page
2. Create a new project by entering a project name
3. Enter user stories and generate diagrams
4. **Important**: As a guest, you cannot update existing projects. Each time you need a new diagram, you must create a new project.

### For Registered Users

1. Click "Register" on the home page
2. Create an account with username and password
3. Login with your credentials
4. Create projects - they will be saved to your account
5. Update existing projects as many times as you want

## Features

### User Authentication
- Registration with username and password
- Secure password hashing using Werkzeug
- Session-based authentication
- User-specific project management

### Project Management
- Each user can create multiple projects
- Projects are associated with user accounts
- Guest users' projects have NULL UserID
- Only owners can update their projects

### UML Diagram Generation
- Class Diagrams
- Use Case Diagrams
- Sequence Diagrams
- Activity Diagrams

## Security Notes

1. **Change the secret key** in production: Line 16 in `main.py`
   ```python
   app.secret_key = 'your-secure-secret-key-here'
   ```

2. The application uses secure password hashing
3. Guest projects (UserID = NULL) are accessible to everyone but only via direct link
4. User-specific projects are only visible to their owners in the dashboard

## Troubleshooting

### Database Connection Issues
- Ensure SQL Server is running
- Verify ODBC Driver 17 is installed
- Check server name and database name in DB_CONFIG

### Model Loading Issues
- Make sure the Spacy model is downloaded
- Run `train_model.py` if you have custom training data

### Guest User Restrictions
- Guest users see a warning when trying to update projects owned by them
- The update button is disabled for guests
- Guests must login to save progress

## Database Schema

```
Users
- UserID (PK, Identity)
- Username (Unique)
- PasswordHash
- CreatedAt

Projects
- ProjectID (PK, Identity)
- ProjectName
- UserID (FK to Users.UserID, NULL for guests)
- CreatedAt

UserStories
- StoryID (PK, Identity)
- ProjectID (FK to Projects)
- StoryText

ModelElements
- ElementID (PK, Identity)
- ProjectID (FK to Projects)
- ElementType
- ElementData (JSON)
- SourceStoryID (FK to UserStories)
```

## API Endpoints

- `GET /` - Dashboard (shows user's projects)
- `POST /register` - Create new user account
- `POST /login` - Login user
- `GET /logout` - Logout user
- `POST /project/new` - Create new project
- `GET /project/<id>` - View project
- `POST /project/<id>/update` - Update project (requires login + ownership)

## Notes

- First-time users should register before creating projects to save their work
- Guest mode is available for quick testing
- All database operations are logged for debugging

