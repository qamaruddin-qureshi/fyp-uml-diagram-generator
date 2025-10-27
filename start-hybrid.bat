@echo off
REM Quick Start Script for Hybrid UML Diagram Generator
REM This script starts both Flask backend and Next.js frontend

echo.
echo ========================================
echo UML Diagram Generator - Hybrid Setup
echo ========================================
echo.

REM Check if we're in the right directory
if not exist "frontend" (
    echo Error: frontend folder not found!
    echo Please run this script from the project root directory
    pause
    exit /b 1
)

echo Starting both servers...
echo.

REM Start Flask backend in a new window
echo [1/2] Starting Flask backend on port 5000...
start "Flask Backend" cmd /k "cd /d %cd% && vr\Scripts\activate && python main.py"

REM Wait a moment for Flask to start
timeout /t 3 /nobreak

REM Start Next.js frontend in a new window
echo [2/2] Starting Next.js frontend on port 3000...
start "Next.js Frontend" cmd /k "cd /d %cd%\frontend && npm run dev"

echo.
echo ========================================
echo Both servers starting!
echo ========================================
echo.
echo Backend:  http://localhost:5000
echo Frontend: http://localhost:3000
echo.
echo Open http://localhost:3000 in your browser!
echo.
pause
