# build_installer.ps1 — Compile ScanWebPDA_Setup.exe avec PyInstaller
# Usage : .\build_installer.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "ScanWebPDA - Build de l'installateur" -ForegroundColor Cyan
Write-Host ""

# ── Répertoire racine du projet ───────────────────────────────────────────────
$ProjectDir = $PSScriptRoot
$InstallerScript = Join-Path $ProjectDir "installer\setup.py"
$OutputDir = Join-Path $ProjectDir "dist"

# ── 1. Vérifier PyInstaller ───────────────────────────────────────────────────
Write-Host "[1/4] Verification de PyInstaller..." -ForegroundColor Yellow
$piCheck = python -m PyInstaller --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  Installation de PyInstaller..." -ForegroundColor Gray
    pip install pyinstaller --quiet
    if ($LASTEXITCODE -ne 0) { Write-Error "Impossible d'installer PyInstaller."; exit 1 }
}
Write-Host "  OK  PyInstaller pret." -ForegroundColor Green

# ── 2. Récupérer le chemin des assets customtkinter ──────────────────────────
Write-Host "[2/4] Localisation des assets customtkinter..." -ForegroundColor Yellow
$CTkPath = python -c "import customtkinter, os; print(os.path.dirname(customtkinter.__file__))"
if (-not $CTkPath) { Write-Error "customtkinter introuvable."; exit 1 }
Write-Host "  OK  customtkinter : $CTkPath" -ForegroundColor Green

# ── 3. Compilation avec PyInstaller ───────────────────────────────────────────
Write-Host "[3/4] Compilation de l'installateur..." -ForegroundColor Yellow
Write-Host "  (Cela peut prendre 2-5 minutes...)" -ForegroundColor Gray

$AddData = "`"$CTkPath;customtkinter`""

python -m PyInstaller `
    --onefile `
    --windowed `
    --name "ScanWebPDA_Setup" `
    --add-data "$CTkPath;customtkinter" `
    --hidden-import "customtkinter" `
    --hidden-import "PIL" `
    --hidden-import "PIL._tkinter_finder" `
    --hidden-import "requests" `
    --hidden-import "packaging" `
    --hidden-import "zipfile" `
    --clean `
    --noconfirm `
    "$InstallerScript"

if ($LASTEXITCODE -ne 0) {
    Write-Host "  ECHEC  Compilation echouee." -ForegroundColor Red
    exit 1
}

# ── 4. Résultat ───────────────────────────────────────────────────────────────
$ExePath = Join-Path $OutputDir "ScanWebPDA_Setup.exe"
if (Test-Path $ExePath) {
    $Size = [math]::Round((Get-Item $ExePath).Length / 1MB, 1)
    Write-Host ""
    Write-Host "=== Installateur cree avec succes ! ===" -ForegroundColor Green
    Write-Host "  Fichier : $ExePath" -ForegroundColor Cyan
    Write-Host "  Taille  : $Size Mo" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Testez-le avec : .\dist\ScanWebPDA_Setup.exe" -ForegroundColor Yellow
} else {
    Write-Host "  ECHEC  Le fichier .exe n'a pas ete cree." -ForegroundColor Red
    exit 1
}
