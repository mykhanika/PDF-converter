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
ChangesAssociations=yes
SetupIconFile=app.ico
UninstallDisplayIcon={app}\PDFToolkit.exe

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "dist\PDFToolkit\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
Source: "tesseract\*"; DestDir: "{app}\tesseract"; Flags: recursesubdirs ignoreversion skipifsourcedoesntexist

[Icons]
Name: "{group}\PDF Toolkit"; Filename: "{app}\PDFToolkit.exe"
Name: "{autodesktop}\PDF Toolkit"; Filename: "{app}\PDFToolkit.exe"; Tasks: desktopicon

[Registry]
Root: HKA; Subkey: "Software\Classes\PDFToolkit.Document"; ValueType: string; ValueData: "PDF Document"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\PDFToolkit.Document\DefaultIcon"; ValueType: string; ValueData: "{app}\PDFToolkit.exe,0"
Root: HKA; Subkey: "Software\Classes\PDFToolkit.Document\shell\open\command"; ValueType: string; ValueData: """{app}\PDFToolkit.exe"" ""%1"""
Root: HKA; Subkey: "Software\Classes\.pdf\OpenWithProgids"; ValueType: string; ValueName: "PDFToolkit.Document"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\Applications\PDFToolkit.exe\shell\open\command"; ValueType: string; ValueData: """{app}\PDFToolkit.exe"" ""%1"""; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\PDFToolkit.exe\SupportedTypes"; ValueType: string; ValueName: ".pdf"; ValueData: ""

[Run]
Filename: "{app}\PDFToolkit.exe"; Description: "Launch PDF Toolkit"; Flags: nowait postinstall skipifsilent
