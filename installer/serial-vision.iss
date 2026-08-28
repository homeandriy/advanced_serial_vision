#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
#define AppName "Advanced Serial Vision"
#define AppExeName "SerialVision.exe"

[Setup]
AppId={{D7A5A23A-40F5-4B9C-9B93-69753B72B8FB}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=homeandriy
DefaultDirName={autopf}\Advanced Serial Vision
OutputDir=..\dist\installer
OutputBaseFilename=SerialVision-Setup-v{#AppVersion}
SetupIconFile=..\application\serial_vision\assets\app-icon.ico
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
PrivilegesRequired=lowest
CloseApplications=yes
CloseApplicationsFilter={#AppExeName}
SetupLogging=yes
ShowLanguageDialog=auto
LanguageDetectionMethod=uilanguage

[Languages]
Name: "uk"; MessagesFile: "compiler:Languages\Ukrainian.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "pl"; MessagesFile: "compiler:Languages\Polish.isl"

[Files]
Source: "..\dist\SerialVision\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Advanced Serial Vision"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\Advanced Serial Vision"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; Flags: unchecked

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,Advanced Serial Vision}"; Flags: nowait postinstall skipifsilent
