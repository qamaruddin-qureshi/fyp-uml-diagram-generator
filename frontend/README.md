# UML Diagram Generator - Next.js Frontend

Modern React/Next.js frontend for the UML Diagram Generator that works with the Flask backend API.

## 🚀 Quick Start

### Prerequisites
- Node.js 18+ and npm
- Flask backend running on `http://localhost:5000`

### Installation

```bash
# Install dependencies
npm install

# Set up environment variables
# Create .env.local (already created with defaults)

# Start development server
npm run dev
```

The frontend will be available at `http://localhost:3000`

## 📁 Project Structure

```
frontend/
├── src/
│   ├── app/                    # Next.js app directory
│   │   ├── layout.jsx          # Root layout with navbar
│   │   ├── page.jsx            # Home/landing page
│   │   ├── globals.css         # Global styles
│   │   ├── auth/
│   │   │   ├── login/page.jsx
│   │   │   └── register/page.jsx
│   │   ├── dashboard/
│   │   │   └── page.jsx        # Projects dashboard
│   │   └── projects/
│   │       └── [id]/page.jsx   # Project editor
│   ├── components/
│   │   └── Navbar.jsx          # Navigation bar
│   ├── lib/
│   │   └── api.js              # API client with axios
│   └── store/
│       ├── auth.js             # Authentication store (Zustand)
│       └── projects.js         # Projects store (Zustand)
├── package.json
├── next.config.js
├── tailwind.config.js
├── postcss.config.js
├── tsconfig.json
├── .env.local                  # Environment variables
└── README.md
```

## 🔧 Configuration

### Environment Variables (.env.local)

```env
# API Configuration - Point to your Flask backend
NEXT_PUBLIC_API_URL=http://localhost:5000

# Flask Backend URL (for rewrites)
FLASK_API_URL=http://localhost:5000
```

## 🎨 Features

### Pages

#### 1. **Home Page** (`/`)
- Landing page with feature overview
- Redirects authenticated users to dashboard
- Call-to-action buttons for login/register

#### 2. **Register** (`/auth/register`)
- Create new account
- Password validation
- Auto-login after registration

#### 3. **Login** (`/auth/login`)
- Sign in with credentials
- Error handling
- Redirect to dashboard

#### 4. **Dashboard** (`/dashboard`)
- View all user projects
- Create new projects
- Quick access to project editor
- Project cards with metadata

#### 5. **Project Editor** (`/projects/[id]`)
- Edit user stories
- Select diagram type (Class, Use Case, Sequence, Activity)
- Real-time diagram preview
- Auto-save diagram type preference in localStorage
- Generate/update diagrams

## 🔌 API Integration

### API Endpoints Called

All requests are proxied through Next.js to `http://localhost:5000`:

```javascript
// Authentication
POST   /auth/register
POST   /auth/login
POST   /auth/logout

// Projects
GET    /projects                    # Get all projects
POST   /project/new                # Create project
GET    /project/{id}               # Get project details
POST   /project/{id}/update        # Update project & generate diagram

// Static Files
GET    /static/{diagram_type}_{id}.png  # Get generated diagrams
```

### API Client (`src/lib/api.js`)

```javascript
import { authAPI, projectAPI } from '@/lib/api'

// Auth
await authAPI.login(username, password)
await authAPI.register(username, password)

// Projects
await projectAPI.getAll()
await projectAPI.getById(projectId)
await projectAPI.create(projectName)
await projectAPI.update(projectId, { userStories, diagramType })
```

## 🧠 State Management

### Zustand Stores

#### Auth Store (`src/store/auth.js`)
```javascript
const { user, isAuthenticated, setUser, setToken, logout } = useAuthStore()
```

#### Projects Store (`src/store/projects.js`)
```javascript
const { projects, currentProject, setProjects, setCurrentProject, updateProject } = useProjectStore()
```

## 🎯 Features

### Authentication
- ✅ User registration with password validation
- ✅ Login with token storage
- ✅ Protected routes (redirect to login if not authenticated)
- ✅ Logout functionality
- ✅ Session persistence via localStorage

### Projects
- ✅ Create new projects
- ✅ View all projects in dashboard
- ✅ Edit user stories
- ✅ Generate diagrams (Class, Use Case, Sequence, Activity)
- ✅ Diagram preview with auto-refresh
- ✅ Save diagram type preference

### UI/UX
- ✅ Dark theme (Tailwind CSS)
- ✅ Responsive design (mobile, tablet, desktop)
- ✅ Toast notifications (react-hot-toast)
- ✅ Loading states and error handling
- ✅ Bootstrap-like components with Tailwind

## 📦 Dependencies

### Core
- **next**: React framework
- **react**: UI library
- **react-dom**: React DOM renderer

### State Management & HTTP
- **zustand**: Lightweight state management
- **axios**: HTTP client

### UI & Styling
- **tailwindcss**: Utility-first CSS framework
- **react-hot-toast**: Toast notifications
- **lucide-react**: Beautiful SVG icons
- **autoprefixer**: PostCSS plugin for vendor prefixes

## 🚀 Deployment

### Development
```bash
npm run dev      # Start dev server on port 3000
```

### Production Build
```bash
npm run build    # Build for production
npm start        # Start production server
```

### Docker (Optional)
Create a `Dockerfile` in the frontend directory:

```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npm", "start"]
```

Build and run:
```bash
docker build -t uml-generator-frontend .
docker run -p 3000:3000 -e NEXT_PUBLIC_API_URL=http://backend:5000 uml-generator-frontend
```

## 🔗 Integration with Flask Backend

### Steps to Run Both Servers

1. **Terminal 1 - Flask Backend**
```bash
cd ..
python main.py
# Flask running on http://localhost:5000
```

2. **Terminal 2 - Next.js Frontend**
```bash
cd frontend
npm run dev
# Next.js running on http://localhost:3000
```

3. **Access the App**
   - Open http://localhost:3000 in your browser
   - Register or login
   - Start creating diagrams!

## 🔒 Security Considerations

- ✅ CORS enabled (handled by Next.js rewrites)
- ✅ JWT tokens stored in localStorage
- ✅ Auto-logout on 401 responses
- ✅ Protected routes with authentication checks
- ✅ Input validation on forms

## 📝 Development Notes

### Adding New Routes
1. Create file in `src/app/` (e.g., `src/app/new-page/page.jsx`)
2. Use Next.js file-based routing automatically
3. Import necessary components and hooks

### Adding New API Calls
1. Add method to appropriate API client in `src/lib/api.js`
2. Use in components with error handling
3. Show toast notifications for user feedback

### Styling
- Uses Tailwind CSS for styling
- Dark theme colors configured in `tailwind.config.js`
- Responsive utilities built-in (mobile-first approach)

## 🐛 Troubleshooting

### Frontend can't connect to backend
- Ensure Flask is running on `http://localhost:5000`
- Check `NEXT_PUBLIC_API_URL` in `.env.local`
- Check browser console for CORS errors

### Login not working
- Verify Flask authentication endpoints are working
- Check token is stored in localStorage
- Look for API errors in console

### Diagrams not loading
- Ensure Flask backend generated the diagram files
- Check `/static/` directory exists in Flask project
- Verify diagram filename matches expected pattern

## 📚 Resources

- [Next.js Documentation](https://nextjs.org/docs)
- [React Documentation](https://react.dev)
- [Tailwind CSS](https://tailwindcss.com)
- [Zustand](https://github.com/pmndrs/zustand)
- [Axios](https://axios-http.com)

## 📄 License

Same as parent project

## 👥 Contributing

1. Create feature branch
2. Make changes
3. Test thoroughly
4. Submit PR

---

**Happy diagram generating! 🎉**
