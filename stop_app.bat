@echo off
:: stop_app.bat - Skrypt do zatrzymywania Streamlit na Windows

echo [INFO] Szukanie procesow Streamlit...

:: Szukanie procesow python, ktore maja w nazwie streamlit
taskkill /FI "WINDOWTITLE eq Streamlit*" /F
if %errorlevel% neq 0 (
    :: Proba zamkniecia po nazwie obrazu (mniej precyzyjne)
    taskkill /IM "streamlit.exe" /F >nul 2>&1
)

echo [INFO] Procesy zostaly zatrzymane (jesli istnialy).
pause
