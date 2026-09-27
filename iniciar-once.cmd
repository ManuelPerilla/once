@echo off
setlocal
cd /d "%~dp0"
echo ONCE - Docker Compose
docker info >nul 2>nul
if errorlevel 1 (
  echo Abre Docker Desktop y espera a que el motor este listo.
  pause
  exit /b 1
)
if not exist ".env" (
  echo Falta .env. Ejecuta python -m src.configure para configurar tu acceso.
  pause
  exit /b 1
)
docker compose up --build -d --wait
if errorlevel 1 (
  echo No se pudo arrancar ONCE. Revisa docker compose logs api frontend.
  pause
  exit /b 1
)
echo.
echo ONCE esta en marcha. Estos son los puertos publicados:
docker compose port frontend 80
echo Administrador: /  -  Explorar: /explore  -  Demo: /explore?demo=1
echo Puedes cerrar esta ventana. Docker mantiene los contenedores activos.
pause
