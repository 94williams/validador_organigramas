@echo off
REM ============================================================
REM Arranca el Validador de Organigramas para acceso en red local.
REM
REM Uso normal (doble clic o desde consola):
REM     start_server.bat
REM
REM Cambiar el puerto (por defecto 8501):
REM     set VALIDADOR_PORT=9000 && start_server.bat
REM
REM Proteger con contraseña (recomendado si compartes fuera de tu
REM red local, ej. con Tailscale):
REM     set VALIDADOR_PASSWORD=una-clave-segura && start_server.bat
REM ============================================================

if "%VALIDADOR_PORT%"=="" set VALIDADOR_PORT=8501

echo.
echo ============================================================
echo   Validador de Organigramas
echo ============================================================
echo   Se iniciara en el puerto %VALIDADOR_PORT%
echo.
echo   Acceso desde ESTA maquina:
echo     http://localhost:%VALIDADOR_PORT%
echo.
echo   Acceso desde OTRAS maquinas en tu red local (oficina):
echo     Ejecuta "ipconfig" en otra ventana y busca tu "Direccion IPv4"
echo     (algo como 192.168.x.x), luego comparte:
echo     http://TU-IP-LOCAL:%VALIDADOR_PORT%
echo.
echo   Para acceso desde FUERA de la red local, ve la seccion
echo   "Acceso remoto" del README (Tailscale recomendado).
echo ============================================================
echo.

streamlit run ui\app.py --server.address 0.0.0.0 --server.port %VALIDADOR_PORT%

pause
