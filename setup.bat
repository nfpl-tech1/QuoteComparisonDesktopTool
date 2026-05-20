@echo off
echo ============================================
echo  Vendor Quote Comparison Tool - Setup
echo ============================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not on PATH.
    pause
    exit /b 1
)

echo [1/4] Creating virtual environment...
python -m venv venv
if %errorlevel% neq 0 (
    echo ERROR: Failed to create virtual environment.
    pause
    exit /b 1
)

echo [2/4] Activating virtual environment...
call venv\Scripts\activate

echo [3/4] Installing dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

echo [4/4] Setting up .env file...
if not exist .env (
    copy .env.example .env
    echo Created .env from template. Please add your GEMINI_API_KEY.
) else (
    echo .env already exists, skipping.
)

echo.
echo ============================================
echo  Setup complete!
echo  Edit .env and add your GEMINI_API_KEY
echo  Then run:  run.bat
echo ============================================
pause
