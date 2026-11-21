; Inno Setup script: packs dist\PDFToolkit (and optional tesseract\) into PDFToolkit-Setup.exe
[Setup]
AppName=PDF Toolkit
AppVersion=1.0
AppPublisher=Washim Reja
AppContact=7003714487
DefaultDirName={autopf}\PDF Toolkit
DefaultGroupName=PDF Toolkit
OutputDir=installer
OutputBaseFilename=PDFToolkit-Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequiredOverridesAllowed=dialog
UninstallDisplayName=PDF Toolkit

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "dist\PDFToolkit\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
Source: "tesseract\*"; DestDir: "{app}\tesseract"; Flags: recursesubdirs ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\PDF Toolkit"; Filename: "{app}\PDFToolkit.exe"
Name: "{autodesktop}\PDF Toolkit"; Filename: "{app}\PDFToolkit.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\PDFToolkit.exe"; Description: "Launch PDF Toolkit"; Flags: nowait postinstall skipifsilent
