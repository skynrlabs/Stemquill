; Inno Setup script for the Windows installer.
; Built by .github/workflows/build.yml after PyInstaller has produced dist\Stemquill.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{369E9D04-2C0D-42F3-8025-0E8AFF921E34}
AppName=Stemquill
AppVersion={#AppVersion}
AppVerName=Stemquill {#AppVersion}
AppPublisher=Skynr Labs
AppPublisherURL=https://github.com/skynrlabs
AppSupportURL=https://github.com/skynrlabs/Stemquill/issues
AppUpdatesURL=https://skynrlabs.itch.io/stemquill
DefaultDirName={autopf}\Stemquill
DefaultGroupName=Stemquill
DisableProgramGroupPage=yes
; Installs for the current user without needing admin rights (users can still choose "all users").
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
LicenseFile=..\LICENSE
OutputDir=..\dist\installer
OutputBaseFilename=Stemquill-Setup-{#AppVersion}
SetupIconFile=..\stemquill\assets\stemquill.ico
UninstallDisplayIcon={app}\Stemquill.exe
UninstallDisplayName=Stemquill
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "chords"; Description: "Better chord detection for guitar, keys and synth stems (basic-pitch, adds about 45 MB)"; GroupDescription: "Optional features:"

[InstallDelete]
; Start the add-on fresh on every install; it's copied back below if the box is ticked.
Type: filesandordirs; Name: "{app}\addons\chords"

[Files]
Source: "..\dist\Stemquill\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\dist\addons\chords\*"; DestDir: "{app}\addons\chords"; Tasks: chords; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Stemquill"; Filename: "{app}\Stemquill.exe"
Name: "{autodesktop}\Stemquill"; Filename: "{app}\Stemquill.exe"; Tasks: desktopicon

[UninstallDelete]
Type: filesandordirs; Name: "{app}\addons"

[Run]
Filename: "{app}\Stemquill.exe"; Description: "{cm:LaunchProgram,Stemquill}"; Flags: nowait postinstall skipifsilent
