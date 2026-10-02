@echo off
rem Crea un acceso directo en la carpeta Inicio de Windows para que el
rem programa arranque solo (minimizado) al encender el ordenador.
cd /d "%~dp0"
if not exist "%~dp0EtiquetasCofares.exe" (
  echo Este archivo debe estar en la misma carpeta que EtiquetasCofares.exe
  pause
  exit /b 1
)
rem Quita la marca "descargado de Internet" para que Windows no pida
rem confirmacion ("editor desconocido") cada vez que se abre el programa.
powershell -NoProfile -Command "Get-ChildItem -LiteralPath '%~dp0' -Recurse | Unblock-File"
powershell -NoProfile -Command ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Startup')+'\Etiquetas Cofares.lnk');" ^
  "$s.TargetPath='%~dp0EtiquetasCofares.exe'; $s.Arguments='--minimizado'; $s.WorkingDirectory='%~dp0'; $s.Save()" || goto :error
echo Hecho. El programa se abrira solo cada vez que se encienda el ordenador.
start "" "%~dp0EtiquetasCofares.exe"
pause
exit /b 0
:error
echo No se pudo crear el acceso directo.
pause
exit /b 1
