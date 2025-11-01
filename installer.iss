; ==============================================================
; Internet Kit / NetKit - Windows Installer Script
; Author: Zeeshan Khan
; ==============================================================

[Setup]
AppId={{8EAC0A28-6C78-4F73-9313-IK-NETKIT}}
AppName=Internet Kit
AppVersion=1.0.0
AppPublisher=Zeeshan Khan
AppComments=Network Speed Monitor with Dashboard
AppCopyright=© Zeeshan Khan
DefaultDirName={pf}\Internet Kit
DefaultGroupName=Internet Kit
OutputDir=.
OutputBaseFilename=InternetKit_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
SetupIconFile=assets\icon_black.ico
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
DisableWelcomePage=no

; optional: custom images if you add them
; WizardImageFile=assets\wizard_large.bmp
; WizardSmallImageFile=assets\wizard_small.bmp

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &Desktop shortcut"; GroupDescription: "Additional tasks:"; Flags: unchecked
Name: "startmenu"; Description: "Create a &Start Menu shortcut"; GroupDescription: "Additional tasks:"
Name: "autorun"; Description: "Run Internet Kit after installation"; GroupDescription: "Additional tasks:"; Flags: unchecked

[Files]
; === main executable ===
Source: "dist\InternetKit.exe"; DestDir: "{app}"; Flags: ignoreversion

; === assets ===
Source: "assets\*"; DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs createallsubdirs

; (optional) include dashboard or data
; Source: "dashboard.html"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
Name: "{app}\assets"
Name: "{userappdata}\NetSpeedData"; Flags: uninsneveruninstall

[Icons]
; Start Menu
Name: "{group}\Internet Kit"; Filename: "{app}\InternetKit.exe"; WorkingDir: "{app}"; IconFilename: "{app}\assets\icon_black.ico"; Tasks: startmenu
; Desktop
Name: "{userdesktop}\Internet Kit"; Filename: "{app}\InternetKit.exe"; WorkingDir: "{app}"; IconFilename: "{app}\assets\icon_black.ico"; Tasks: desktopicon

[Run]
; launch app after install
Filename: "{app}\InternetKit.exe"; Description: "Run Internet Kit now"; Flags: postinstall nowait skipifsilent; Tasks: autorun

[UninstallDelete]
; optional cleanup for user data
; Type: filesandordirs; Name: "{userappdata}\NetSpeedData"

[Code]
procedure InitializeWizard;
begin
  WizardForm.WelcomeLabel1.Caption := 'Welcome to the Internet Kit Setup';
  WizardForm.WelcomeLabel2.Caption := 'This will install Internet Kit by Zeeshan Khan on your computer.';
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    MsgBox('Internet Kit has been installed successfully!'#13#13 +
           'Created by Zeeshan Khan.'#13 +
           'You can launch it from the Start Menu or Desktop shortcut.',
           mbInformation, MB_OK);
end;
