@echo off
rem Genera dist\EtiquetasCofares\ con el .exe listo para copiar al ordenador de la farmacia.
cd /d "%~dp0"
python -m pip install -r requirements.txt pyinstaller || goto :error
python -m PyInstaller --noconfirm --clean --windowed --name EtiquetasCofares ^
  --hidden-import win32timezone etiquetas_cofares.py || goto :error
copy /y config.ini dist\EtiquetasCofares\ >nul
copy /y plantilla.lbx dist\EtiquetasCofares\ >nul
copy /y instalar_inicio_automatico.bat dist\EtiquetasCofares\ >nul
copy /y LEEME.md dist\EtiquetasCofares\ >nul
echo.
echo Listo: dist\EtiquetasCofares\EtiquetasCofares.exe
pause
exit /b 0
:error
echo Ha fallado la construccion.
pause
exit /b 1
