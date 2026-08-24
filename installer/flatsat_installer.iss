; flatsat_installer.iss
; Script for Inno Setup

[Setup]
AppId={{4F9E4E3D-3D6C-5B2F-9F4C-2D5E6F7A8B9C}
AppName=FlatSat Ground Station
AppVersion=1.0.0
AppPublisher=Electronic Cats
AppPublisherURL=https://github.com/ElectronicCats/flat-sat-fw-interno
AppSupportURL=https://github.com/ElectronicCats/flat-sat-fw-interno/issues
AppComments=FlatSat Ground Station host CLI & analysis suite
AppCopyright=Copyright © 2026 Electronic Cats
DefaultDirName={autopf}\FlatSat
DefaultGroupName=FlatSat
UninstallDisplayIcon={app}\flatsat.exe
Compression=lzma2
SolidCompression=yes
OutputDir=..\dist
OutputBaseFilename=FlatSat-Setup
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "addtopath"; Description: "Add FlatSat to PATH"; GroupDescription: "Configuration:"; Flags: checkedonce

[Files]
Source: "..\dist\flatsat\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\scripts\install_windows_drivers.ps1"; DestDir: "{app}\scripts"; Flags: ignoreversion

[Icons]
Name: "{group}\FlatSat CLI"; Filename: "{cmd}"; Parameters: "/k ""{app}\flatsat.exe"""; IconFilename: "{app}\flatsat.exe"
Name: "{group}\FlatSat Documentation"; Filename: "{app}\README.md"
Name: "{group}\Uninstall FlatSat"; Filename: "{uninstallexe}"
Name: "{autodesktop}\FlatSat CLI"; Filename: "{cmd}"; Parameters: "/k ""{app}\flatsat.exe"""; IconFilename: "{app}\flatsat.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\flatsat.exe"; Parameters: "--help"; Description: "Verify installation"; Flags: postinstall runhidden

[Registry]
Root: HKLM; Subkey: "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Tasks: addtopath; Check: NeedsAddPath(ExpandConstant('{app}'))

[Code]
function NeedsAddPath(Param: string): boolean;
var
  OrigPath: string;
begin
  if not RegQueryStringValue(HKEY_LOCAL_MACHINE,
    'SYSTEM\CurrentControlSet\Control\Session Manager\Environment',
    'Path', OrigPath)
  then begin
    Result := True;
    exit;
  end;
  Result := Pos(Param, OrigPath) = 0;
end;
