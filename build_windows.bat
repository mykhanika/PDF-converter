@echo off
REM Builds PDFToolkit-Setup.exe on Windows. Needs Python 3.9+ and Inno Setup 6 (jrsoftware.org/isinfo.php).
python -m pip install -r requirements.txt || goto :err
python build.py || goto :err
REM Bundle Tesseract OCR into the installer if it is installed on this PC
if exist "C:\Program Files\Tesseract-OCR\tesseract.exe" (
  if not exist tesseract xcopy "C:\Program Files\Tesseract-OCR" tesseract\ /E /I /Q
)
set ISCC="%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist %ISCC% set ISCC="%ProgramFiles%\Inno Setup 6\ISCC.exe"
%ISCC% installer.iss || goto :err
echo.
echo Done: installer\PDFToolkit-Setup.exe
exit /b 0
:err
echo Build failed.
exit /b 1
