; ============================================================================
;  KeyMagic — Windows installer (Inno Setup 6)
;
;  Bilingual English / Persian. Selecting Persian switches the whole wizard
;  to a right-to-left layout via RightToLeft=yes in Persian.isl, and picks
;  Tahoma, which renders Farsi correctly (Segoe UI does not shape it well).
;
;  Build with:  build.py  (generates art + Persian.isl first, then compiles)
; ============================================================================

#define AppName        "KeyMagic"
#define AppVersion     "1.0.1"
#define AppPublisher   "Erfan Esmailzadeh"
#define AppURL         "https://github.com/kterfan/KeyMagic"
#define AppExeName     "KeyMagic.exe"

[Setup]
; Stable GUID — never change it, or upgrades will install side-by-side
; instead of replacing the previous version.
AppId={{A7F3C2E1-9B4D-4E8A-BC5F-1D2E3F4A5B6C}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}/releases
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} — keyboard layout fixer
VersionInfoCopyright=© {#AppPublisher}

DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
UninstallDisplayName={#AppName} {#AppVersion}
UninstallDisplayIcon={app}\{#AppExeName}
OutputDir=..\dist\installer
OutputBaseFilename={#AppName}-{#AppVersion}-Setup
SetupIconFile=..\assets\icon.ico

; --- Look and feel --------------------------------------------------------
WizardStyle=modern
WizardSizePercent=115
WizardImageFile=art\banner.bmp
WizardSmallImageFile=art\header.bmp
WizardImageStretch=yes
ShowLanguageDialog=yes
DisableWelcomePage=no
; The install path is the thing users most often want to confirm, so show it
; on the summary page as well as the directory page.
AlwaysShowDirOnReadyPage=yes
AlwaysShowGroupOnReadyPage=yes

; --- Packaging ------------------------------------------------------------
Compression=lzma2/ultra64
SolidCompression=yes
LZMANumBlockThreads=4
; The app injects input into other processes, so it needs to run elevated;
; installing per-machine into Program Files matches that.
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "fa"; MessagesFile: "Persian.isl"

[CustomMessages]
en.LaunchAfter=Launch {#AppName} now
fa.LaunchAfter=هم‌اکنون {#AppName} اجرا شود
en.DesktopIcon=Create a &desktop shortcut
fa.DesktopIcon=ساخت میان‌بر روی &میزکار
en.AutoStart=Start {#AppName} automatically with Windows
fa.AutoStart=اجرای خودکار {#AppName} هنگام شروع ویندوز
en.CreatedBy=Created by {#AppPublisher}
fa.CreatedBy=ساخته‌شده توسط عرفان اسماعیل‌زاده
en.InstallPathIs=Install location:
fa.InstallPathIs=محل نصب:

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopIcon}"; GroupDescription: "{cm:AutoStart}"; Flags: unchecked
; Checked by default — the app is a background utility and is useless if it
; is not running, but the user can clear this (and toggle it later in-app).
Name: "autostart";  Description: "{cm:AutoStart}";  GroupDescription: "{cm:AutoStart}"

[Files]
Source: "..\dist\KeyMagic\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\KeyMagic\*";             DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\assets\icon.ico";             DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md";                   DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}";        Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\icon.ico"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}";  Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon

[Run]
; `shellexec` is required, not cosmetic. The app ships a requireAdministrator
; manifest, and Inno's default CreateProcess cannot raise privileges — it
; fails with "CreateProcess failed; code 740 - The requested operation
; requires elevation" the moment Setup tries to launch it. ShellExecute is
; the API that knows how to satisfy an elevation request.
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchAfter}"; Flags: nowait postinstall skipifsilent shellexec

; No [UninstallDelete] for the app's per-user settings/log directories.
; The uninstaller runs elevated, so {userappdata} would resolve to the
; *administrator's* profile rather than the profile that actually holds the
; data — deleting there is both wrong and useless. Per-user leftovers
; (%APPDATA%\KeyMagic, %LOCALAPPDATA%\KeyMagic) are small and are reused if
; the app is reinstalled, which is the friendlier behaviour anyway.

[Code]
{ Remove the autostart registry entry on uninstall, and honour the user's
  choice when they clear the autostart task during install. The app itself
  owns this key at runtime, so the installer only needs to seed/clear it. }

const
  RunKey = 'Software\Microsoft\Windows\CurrentVersion\Run';

procedure WriteSettingsDisablingAutostart();
var
  SettingsDir: string;
begin
  // The app reads this on first launch; writing it here is how an unchecked
  // task survives, since the app would otherwise re-enable autostart from
  // its own defaults.
  //
  // Caveat: the installer runs elevated, so the userappdata constant
  // resolves to whichever account approved the UAC prompt. That is the
  // installing user in the normal case (an admin elevating themselves), but
  // if setup was launched with a different admin's credentials the file
  // lands in that admin's profile and the choice is not honoured. The user
  // can still turn autostart off from the app's own panel, so this degrades
  // gracefully.
  //
  // These are // comments, not brace comments, because an Inno constant
  // such as the one below would close a brace comment early.
  SettingsDir := ExpandConstant('{userappdata}\{#AppName}');
  if not DirExists(SettingsDir) then
    CreateDir(SettingsDir);
  SaveStringToFile(
    SettingsDir + '\settings.json',
    '{"language": "en", "muted": false, "show_toasts": true, "autostart": false}',
    False);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    if not WizardIsTaskSelected('autostart') then
      WriteSettingsDisablingAutostart();
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;
begin
  if CurUninstallStep = usUninstall then
  begin
    // Autostart is a scheduled task (a Run-key entry cannot start an
    // elevation-requiring app at logon — Windows skips it silently).
    Exec(ExpandConstant('{sys}\schtasks.exe'),
         '/Delete /TN "{#AppName}" /F', '', SW_HIDE,
         ewWaitUntilTerminated, ResultCode);
    // Also clear the Run value that pre-1.0.1 builds wrote.
    RegDeleteValue(HKEY_CURRENT_USER, RunKey, '{#AppName}');
  end;
end;
