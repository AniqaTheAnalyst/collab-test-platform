@echo off
set PYTHON_EXE=E:\Python313\python.exe

if not exist "%PYTHON_EXE%" (
    echo Python was not found at %PYTHON_EXE%
    pause
    exit /b 1
)

echo Starting Streamlit...
start "Streamlit" cmd /k ""%PYTHON_EXE%" -m streamlit run app.py"

echo Starting FastAPI...
start "FastAPI" cmd /k ""%PYTHON_EXE%" -m uvicorn api.server:app --reload --port 8001"

pause