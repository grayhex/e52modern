; SymPort Bridge installer (Inno Setup 6). Per-user, no administrator rights, no drivers.
; Built by tools/windows/build_installer.py:
;   ISCC /DAppVersion=0.3.0 /DPortableDir=... /DOutputDir=... /DIconFile=... SymPortBridge.iss
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef PortableDir
  #define PortableDir "..\..\..\build\windows\portable"
#endif
#ifndef OutputDir
  #define OutputDir "..\..\..\build\windows\installer"
#endif
#define AppName "SymPort Bridge"
#define AppExe "SymPortBridge.exe"
#define Repo "https://github.com/grayhex/s60modern"

[Setup]
; Never change AppId: it is how upgrades find the installed copy.
AppId={{8F3C2B7A-5D41-4C0E-9B6A-7E52A1F0C3D9}
AppName={#AppName}
AppVersion={#AppVersion}
VersionInfoVersion={#AppVersion}.0
AppPublisher=SymPort contributors
AppPublisherURL={#Repo}
AppSupportURL={#Repo}/issues
AppUpdatesURL={#Repo}/releases
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=SymPortBridge-Setup-{#AppVersion}
#ifdef IconFile
SetupIconFile={#IconFile}
#endif
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
LicenseFile={#PortableDir}\LICENSE.txt
; A running tray Bridge has no window to close, so the Restart Manager cannot stop it and a silent
; update would abort. Setup stops it itself (see StopBridge); the updater only starts Setup while no
; phone operation runs, and exits on its own first.
CloseApplications=no
UsedUserAreasWarning=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[CustomMessages]
english.AutoStart=Start SymPort Bridge when I sign in to Windows
english.RemoveData=Also delete SymPort Bridge settings and the pairing key (the SymPortBridge folder in your local application data)?%n%nChoose No to keep them for a later reinstall. Private phone backups stored there are deleted with them.
english.Launch=Start SymPort Bridge
russian.AutoStart=Запускать SymPort Bridge при входе в Windows
russian.RemoveData=Удалить также настройки SymPort Bridge и ключ сопряжения (папка SymPortBridge в локальных данных приложений)?%n%nВыберите «Нет», чтобы сохранить их для повторной установки. Личные резервные копии телефона из этой папки будут удалены вместе с ними.
russian.Launch=Запустить SymPort Bridge

[Tasks]
Name: "autostart"; Description: "{cm:AutoStart}"; Flags: unchecked
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; Flags: unchecked

[Files]
Source: "{#PortableDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autoprograms}\{#AppName} — Uninstall"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; Same value the tray "Start at Windows sign-in" setting uses, so both stay consistent.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "SymPortBridge"; ValueData: """{app}\{#AppExe}"""; Flags: uninsdeletevalue; Tasks: autostart
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "SymPortBridge"; Flags: uninsdeletevalue

[Run]
; Interactive install: optional checkbox. Silent update (/StartAfter=1): start the new version.
Filename: "{app}\{#AppExe}"; Description: "{cm:Launch}"; Flags: nowait postinstall skipifsilent
Filename: "{app}\{#AppExe}"; Flags: nowait; Check: StartAfterSilentUpdate

[Code]
procedure StopBridge;
var
  Code: Integer;
begin
  // Only this user's processes can be ended; a missing process is not an error.
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/F /IM SymPortBridge.exe', '', SW_HIDE, ewWaitUntilTerminated, Code);
  Sleep(1500);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  StopBridge;
  Result := '';
end;

function InitializeUninstall: Boolean;
begin
  StopBridge;
  Result := True;
end;

function StartAfterSilentUpdate: Boolean;
begin
  Result := WizardSilent and (ExpandConstant('{param:StartAfter|0}') = '1');
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
  Remove: Boolean;
begin
  if CurUninstallStep <> usPostUninstall then
    exit;
  DataDir := ExpandConstant('{localappdata}\SymPortBridge');
  if not DirExists(DataDir) then
    exit;
  // Settings, the DPAPI-protected pairing key and private backups survive by default.
  if UninstallSilent then
    Remove := ExpandConstant('{param:REMOVEDATA|0}') = '1'
  else
    Remove := MsgBox(CustomMessage('RemoveData'), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES;
  if Remove then
    DelTree(DataDir, True, True, True);
end;
