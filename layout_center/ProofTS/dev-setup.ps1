<#
Simple Windows PowerShell dev script for ProofTS.
Usage:
  .\dev-setup.ps1                # Activate the local conda env
  .\dev-setup.ps1 -InstallDeps   # Activate env and install dependencies
  nuitka --standalone --onefile --enable-plugin=pyside6 .\main.py
#>
param(
  [switch]$InstallDeps,
  [switch]$TestImports,
  [switch]$UseVenv,
  [switch]$CreateVenv
)

# Switch to repo root (script may be executed from anywhere)
Set-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)

if ($UseVenv) {
  # Ensure venv exists
  if ($CreateVenv -or -not (Test-Path -Path "$PWD\.venv")) {
    Write-Output "Creating Python venv at $PWD\.venv"
    # Use py -3 if available otherwise fallback to python
    if (Get-Command py -ErrorAction SilentlyContinue) {
      py -3 -m venv .venv
    } else {
      python -m venv .venv
    }
  }
  Write-Output "Activating venv at: $PWD\.venv"
  # Activate the venv in this shell session
  . .\.venv\Scripts\Activate.ps1
} else {
  Write-Output "Activating local conda environment at: $PWD\.conda"
  conda activate .\.conda
}

Write-Output "Python: $(python -c 'import sys; print(sys.executable)')"
Write-Output "Python version: $(python -V)"

if ($InstallDeps) {
  Write-Output "Installing dependencies from requirements.txt into local env..."
  if ($UseVenv) {
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
  } else {
    .\.conda\python.exe -m pip install -r requirements.txt
  }
  Write-Output "Installation finished."
}
if ($TestImports) {
  Write-Output "Testing imports (PySide6 clr fitz selenium webdriver_manager bs4 debugpy)..."
  if ($UseVenv) {
    .\.venv\Scripts\python.exe -c "import sys; modules=['PySide6','clr','fitz','selenium','webdriver_manager','bs4','debugpy'];
for m in modules:
  try:
    __import__(m)
    print(m + ' OK')
  except Exception as e:
    print(m + ' FAILED: ' + str(type(e).__name__) + ' ' + str(e))
print('Python executable:', sys.executable)"
    }
  else {
    .\.conda\python.exe -c "import sys; modules=['PySide6','clr','fitz','selenium','webdriver_manager','bs4','debugpy'];
for m in modules:
  try:
    __import__(m)
    print(m + ' OK')
  except Exception as e:
    print(m + ' FAILED: ' + str(type(e).__name__) + ' ' + str(e))
print('Python executable:', sys.executable)"
    }
    Write-Output "Import test complete."
}

Write-Output "Done. To run the GUI: python main.py"