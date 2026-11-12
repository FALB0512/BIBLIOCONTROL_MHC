@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -m venv .venv
  if errorlevel 1 (echo ERROR: Instala Python 3 y habilita py o python en PATH.& pause & exit /b 1)
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (echo No se pudo instalar Flask. Verifica la conexion a Internet.& pause & exit /b 1)
echo.
echo Abre en tu navegador: http://127.0.0.1:5000
".venv\Scripts\python.exe" app.py
pause
