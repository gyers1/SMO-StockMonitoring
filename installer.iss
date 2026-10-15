#ifndef MyAppVersion
  #error MyAppVersion must be supplied by build.bat
#endif
[Setup]
AppId={{7E42BA26-33C2-4142-8F14-A7502D26C405}
AppName=SMO
AppVersion={#MyAppVersion}
AppPublisher=SMO
DefaultDirName={localappdata}\Programs\SMO
DefaultGroupName=SMO
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
MinVersion=10.0.19041
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=release
OutputBaseFilename=SMO-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=assets\smo.ico
UninstallDisplayIcon={app}\SMO.exe
CloseApplications=yes
[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
[Tasks]
Name: "desktopicon"; Description: "바탕 화면에 SMO 바로가기 만들기"; Flags: unchecked
[Files]
Source: "dist\SMO\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\SMO"; Filename: "{app}\SMO.exe"; WorkingDir: "{app}"; IconFilename: "{app}\SMO.exe"
Name: "{autodesktop}\SMO"; Filename: "{app}\SMO.exe"; WorkingDir: "{app}"; IconFilename: "{app}\SMO.exe"; Tasks: desktopicon
[Run]
Filename: "{app}\SMO.exe"; Description: "SMO 실행"; Flags: nowait postinstall skipifsilent
