; setup_installer.iss

[Setup]
AppName=Avakin
AppVersion=1.0.1
AppPublisher=Your Name
DefaultDirName={autopf}\Avakin
DefaultGroupName=Avakin
OutputBaseFilename=Avakin_v1.0.1_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin ; Required to install pip packages for all users

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; This tells the installer to grab everything from your successful build folder
; and put it in the user's installation directory.
Source: "build\exe.win-amd64-3.13\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Avakin"; Filename: "{app}\Avakin.exe"
Name: "{autodesktop}\Avakin"; Filename: "{app}\Avakin.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}";

[Run]
; This is the magic part. After installing, it runs pip to get the dependencies.
; We use 'py -m pip' which is a reliable way to call Python's pip on Windows.
Filename: "py.exe"; Parameters: "-m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121"; \
    Flags: runhidden shellexec waituntilterminated
Filename: "py.exe"; Parameters: "-m pip install sentence-transformers transformers chromadb uvicorn fastapi python-multipart"; \
    Flags: runhidden shellexec waituntilterminated

[Code]
// A helper function to check if Python is installed.
function IsPythonInstalled(): Boolean;
var
  ResultCode: Integer;
begin
  // 'py --version' is a standard way to check for Python launcher on Windows.
  // It returns 0 if successful.
  Exec('py.exe', '--version', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := (ResultCode = 0);
end;

// This function runs before the installer starts.
function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  // If Python is not installed, show a message and abort the installation.
  if not IsPythonInstalled() then
  begin
    MsgBox('Python is not installed or not found in your system''s PATH. Please install Python 3.10 or newer from python.org and ensure it is added to your PATH.', mbError, MB_OK);
    Result := 'Python not found. Installation aborted.';
  end
  else
    Result := '';
end;