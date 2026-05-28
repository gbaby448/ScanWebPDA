"""
installer/setup.py — Installateur Windows ScanWebPDA
Wizard 4 pages : Bienvenue → Configuration → Installation → Terminé
Compilé avec PyInstaller → ScanWebPDA_Setup.exe
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
import os, sys, threading, subprocess, zipfile, shutil, tempfile, requests
from pathlib import Path

# ── Constantes ────────────────────────────────────────────────────────────────
GITHUB_OWNER   = "gbaby448"
GITHUB_REPO    = "ScanWebPDA"
APP_NAME       = "ScanWebPDA"
APP_VERSION    = "1.0.2"
DEFAULT_DIR    = str(Path(os.environ.get("LOCALAPPDATA", "C:/Users/Default/AppData/Local")) / APP_NAME)
API_LATEST     = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"

# ── Palette ───────────────────────────────────────────────────────────────────
BG      = "#0f0f1a"
CARD    = "#1a1a2e"
ACCENT  = "#1565c0"
GREEN   = "#2e7d32"
RED     = "#c62828"
TEXT    = "#e0e0e0"
SUBTLE  = "#888888"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class InstallerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} — Installation")
        self.geometry("640x480")
        self.resizable(False, False)
        self.configure(fg_color=BG)

        # Variables
        self.install_dir   = tk.StringVar(value=DEFAULT_DIR)
        self.desktop_sc    = tk.BooleanVar(value=True)
        self.startmenu_sc  = tk.BooleanVar(value=True)
        self._install_ok   = False

        # Construire toutes les pages
        self._pages = {}
        self._build_welcome()
        self._build_config()
        self._build_progress()
        self._build_done()

        self._show("welcome")

    # ═══════════════════════════════════════════════════════
    #  NAVIGATION
    # ═══════════════════════════════════════════════════════

    def _show(self, name: str):
        for p in self._pages.values():
            p.place_forget()
        self._pages[name].place(relx=0, rely=0, relwidth=1, relheight=1)

    # ═══════════════════════════════════════════════════════
    #  PAGE 1 — BIENVENUE
    # ═══════════════════════════════════════════════════════

    def _build_welcome(self):
        f = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self._pages["welcome"] = f

        # Bande de couleur en haut
        top = ctk.CTkFrame(f, height=160, fg_color=CARD, corner_radius=0)
        top.pack(fill="x")

        ctk.CTkLabel(top, text="🔍", font=("Segoe UI Emoji", 52)).pack(pady=(24, 4))
        ctk.CTkLabel(top, text=APP_NAME,
                     font=ctk.CTkFont("Segoe UI", 28, "bold"),
                     text_color="#64b5f6").pack()
        ctk.CTkLabel(top, text=f"Installateur — v{APP_VERSION}",
                     font=ctk.CTkFont("Segoe UI", 12),
                     text_color=SUBTLE).pack()

        # Corps
        body = ctk.CTkFrame(f, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=40, pady=20)

        ctk.CTkLabel(body,
                     text="Bienvenue dans l'assistant d'installation de ScanWebPDA.\n\n"
                          "Ce logiciel surveille automatiquement les annonces de pièces\n"
                          "auto sur LeBonCoin, eBay, Ovoko, Opisto et bien d'autres,\n"
                          "grâce à une analyse intelligente par IA (Ollama local).\n\n"
                          "Cliquez sur Suivant pour choisir le dossier d'installation.",
                     font=ctk.CTkFont("Segoe UI", 13),
                     text_color=TEXT,
                     justify="left",
                     anchor="w").pack(fill="x")

        # Pied
        foot = ctk.CTkFrame(f, fg_color=CARD, height=56, corner_radius=0)
        foot.pack(fill="x", side="bottom")
        ctk.CTkButton(foot, text="Suivant  ›",
                      fg_color=ACCENT, hover_color="#1976d2",
                      font=ctk.CTkFont("Segoe UI", 13, "bold"),
                      width=130, height=36,
                      command=lambda: self._show("config")).pack(side="right", padx=20, pady=10)
        ctk.CTkButton(foot, text="Annuler",
                      fg_color="transparent", hover_color="#333355",
                      text_color=SUBTLE, width=90, height=36,
                      command=self.destroy).pack(side="right", padx=4, pady=10)

    # ═══════════════════════════════════════════════════════
    #  PAGE 2 — CONFIGURATION
    # ═══════════════════════════════════════════════════════

    def _build_config(self):
        f = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self._pages["config"] = f

        # En-tête
        self._header(f, "⚙️  Configuration", "Choisissez où installer ScanWebPDA")

        body = ctk.CTkFrame(f, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=40, pady=16)

        # Dossier d'installation
        ctk.CTkLabel(body, text="Dossier d'installation :",
                     font=ctk.CTkFont("Segoe UI", 12, "bold"),
                     text_color=TEXT).pack(anchor="w", pady=(0, 6))

        dir_row = ctk.CTkFrame(body, fg_color="transparent")
        dir_row.pack(fill="x", pady=(0, 20))

        ctk.CTkEntry(dir_row, textvariable=self.install_dir,
                     font=ctk.CTkFont("Segoe UI", 11),
                     height=36).pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(dir_row, text="Parcourir…", width=100, height=36,
                      fg_color=CARD, hover_color="#2a2a4a",
                      command=self._browse).pack(side="right")

        # Raccourcis
        ctk.CTkLabel(body, text="Options :",
                     font=ctk.CTkFont("Segoe UI", 12, "bold"),
                     text_color=TEXT).pack(anchor="w", pady=(0, 8))

        ctk.CTkCheckBox(body, text="Créer un raccourci sur le Bureau",
                        variable=self.desktop_sc,
                        font=ctk.CTkFont("Segoe UI", 12)).pack(anchor="w", pady=4)
        ctk.CTkCheckBox(body, text="Ajouter au Menu Démarrer",
                        variable=self.startmenu_sc,
                        font=ctk.CTkFont("Segoe UI", 12)).pack(anchor="w", pady=4)

        # Note Ollama
        note = ctk.CTkFrame(body, fg_color=CARD, corner_radius=8)
        note.pack(fill="x", pady=(20, 0))
        ctk.CTkLabel(note,
                     text="ℹ️  Ollama est requis pour l'analyse IA. S'il n'est pas installé,\n"
                          "l'application fonctionnera mais sans validation intelligente.",
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=SUBTLE, justify="left").pack(padx=14, pady=10)

        # Pied
        foot = ctk.CTkFrame(f, fg_color=CARD, height=56, corner_radius=0)
        foot.pack(fill="x", side="bottom")
        ctk.CTkButton(foot, text="‹  Retour",
                      fg_color="transparent", hover_color="#333355",
                      text_color=SUBTLE, width=100, height=36,
                      command=lambda: self._show("welcome")).pack(side="left", padx=20, pady=10)
        ctk.CTkButton(foot, text="Installer  ›",
                      fg_color=GREEN, hover_color="#1b5e20",
                      font=ctk.CTkFont("Segoe UI", 13, "bold"),
                      width=130, height=36,
                      command=self._start_install).pack(side="right", padx=20, pady=10)
        ctk.CTkButton(foot, text="Annuler",
                      fg_color="transparent", hover_color="#333355",
                      text_color=SUBTLE, width=90, height=36,
                      command=self.destroy).pack(side="right", padx=4, pady=10)

    def _browse(self):
        d = filedialog.askdirectory(initialdir=self.install_dir.get(), title="Choisir le dossier d'installation")
        if d:
            self.install_dir.set(d)

    # ═══════════════════════════════════════════════════════
    #  PAGE 3 — PROGRESSION
    # ═══════════════════════════════════════════════════════

    def _build_progress(self):
        f = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self._pages["progress"] = f

        self._header(f, "⬇️  Installation en cours…", "Veuillez patienter")

        body = ctk.CTkFrame(f, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=40, pady=16)

        self._progress_var = tk.DoubleVar(value=0)
        self._status_var   = tk.StringVar(value="Initialisation…")

        ctk.CTkLabel(body, textvariable=self._status_var,
                     font=ctk.CTkFont("Segoe UI", 13, "bold"),
                     text_color="#64b5f6").pack(anchor="w", pady=(0, 8))

        ctk.CTkProgressBar(body, variable=self._progress_var,
                           height=18, corner_radius=9).pack(fill="x", pady=(0, 12))

        self._log_box = ctk.CTkTextbox(body, height=200,
                                        font=ctk.CTkFont("Consolas", 11),
                                        fg_color=CARD, text_color="#b0bec5",
                                        wrap="word")
        self._log_box.pack(fill="both", expand=True)
        self._log_box.configure(state="disabled")

    def _start_install(self):
        self._show("progress")
        threading.Thread(target=self._run_install, daemon=True).start()

    def _log(self, msg: str, color=None):
        self._log_box.configure(state="normal")
        self._log_box.insert("end", f"  {msg}\n")
        self._log_box.see("end")
        self._log_box.configure(state="disabled")

    def _set_status(self, msg: str, pct: float):
        self._status_var.set(msg)
        self._progress_var.set(pct)

    def _run_install(self):
        """Thread d'installation principal."""
        install_dir = self.install_dir.get()
        try:
            # ── Étape 1 : Python ───────────────────────────────────────────
            self._set_status("Vérification de Python…", 0.05)
            python_ok, python_exe = self._find_python()
            if not python_ok:
                self._log("⚠  Python 3.10+ non trouvé. Installation via winget…")
                self._set_status("Installation de Python…", 0.1)
                r = subprocess.run(
                    ["winget", "install", "--id", "Python.Python.3.11", "-e", "--silent"],
                    capture_output=True, text=True
                )
                if r.returncode != 0:
                    raise RuntimeError("Impossible d'installer Python automatiquement. "
                                       "Installez Python 3.10+ manuellement depuis python.org")
                python_ok, python_exe = self._find_python()
                if not python_ok:
                    raise RuntimeError("Python introuvable après installation.")
            self._log(f"✔  Python trouvé : {python_exe}")

            # ── Étape 2 : Dossier ─────────────────────────────────────────
            self._set_status("Création du dossier…", 0.2)
            os.makedirs(install_dir, exist_ok=True)
            self._log(f"✔  Dossier créé : {install_dir}")

            # ── Étape 3 : Téléchargement ───────────────────────────────────
            self._set_status("Téléchargement de la dernière version…", 0.3)
            zip_url, version = self._get_latest_zip()
            self._log(f"✔  Version : {version}")

            tmp_zip = os.path.join(tempfile.gettempdir(), "scanwebpda_install.zip")
            resp = requests.get(zip_url, stream=True, timeout=60)
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            downloaded = 0
            with open(tmp_zip, "wb") as fh:
                for chunk in resp.iter_content(8192):
                    fh.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        pct = 0.3 + 0.3 * (downloaded / total)
                        self._set_status(f"Téléchargement… {downloaded // 1024} Ko", pct)
            self._log("✔  Téléchargement terminé")

            # ── Étape 4 : Extraction ───────────────────────────────────────
            self._set_status("Extraction des fichiers…", 0.62)
            PROTECTED = {"config.json", "data.db", "proxies.json", ".github_token"}
            tmp_dir = tempfile.mkdtemp()
            with zipfile.ZipFile(tmp_zip, "r") as zf:
                zf.extractall(tmp_dir)
            # GitHub crée un sous-dossier "owner-repo-hash/"
            root_entry = next(
                (e for e in os.listdir(tmp_dir) if os.path.isdir(os.path.join(tmp_dir, e))),
                None
            )
            src_root = os.path.join(tmp_dir, root_entry) if root_entry else tmp_dir

            for dirpath, _, files in os.walk(src_root):
                rel = os.path.relpath(dirpath, src_root)
                dest_dir = os.path.join(install_dir, rel)
                os.makedirs(dest_dir, exist_ok=True)
                for fname in files:
                    if fname in PROTECTED and rel == ".":
                        continue
                    shutil.copy2(os.path.join(dirpath, fname), os.path.join(dest_dir, fname))
            shutil.rmtree(tmp_dir, ignore_errors=True)
            os.unlink(tmp_zip)
            self._log("✔  Fichiers copiés")

            # ── Étape 5 : Dépendances ─────────────────────────────────────
            self._set_status("Installation des dépendances…", 0.72)
            req_file = os.path.join(install_dir, "requirements.txt")
            if os.path.exists(req_file):
                result = subprocess.run(
                    [python_exe, "-m", "pip", "install", "-r", req_file, "--quiet"],
                    capture_output=True, text=True, timeout=300
                )
                if result.returncode != 0:
                    self._log(f"⚠  Avertissement pip : {result.stderr[:200]}")
                else:
                    self._log("✔  Dépendances installées")

            # ── Étape 6 : Raccourcis ──────────────────────────────────────
            self._set_status("Création des raccourcis…", 0.90)
            pythonw = self._find_pythonw(python_exe)
            gui_path = os.path.join(install_dir, "gui.py")

            if self.desktop_sc.get():
                desktop = str(Path.home() / "Desktop")
                self._make_shortcut(
                    pythonw, f'"{gui_path}"',
                    os.path.join(desktop, f"{APP_NAME}.lnk"),
                    install_dir
                )
                self._log("✔  Raccourci Bureau créé")

            if self.startmenu_sc.get():
                sm = str(Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs")
                os.makedirs(sm, exist_ok=True)
                self._make_shortcut(
                    pythonw, f'"{gui_path}"',
                    os.path.join(sm, f"{APP_NAME}.lnk"),
                    install_dir
                )
                self._log("✔  Menu Démarrer créé")

            # ── Ollama ────────────────────────────────────────────────────
            ollama_ok = shutil.which("ollama") is not None
            if not ollama_ok:
                self._log("ℹ  Ollama non détecté — installez-le depuis https://ollama.com")

            self._set_status("Installation terminée !", 1.0)
            self._log("\n✅  ScanWebPDA a été installé avec succès !")
            self._install_ok = True
            self.after(800, lambda: self._show_done(True))

        except Exception as exc:
            self._log(f"\n❌  Erreur : {exc}")
            self._set_status("Erreur d'installation", self._progress_var.get())
            self.after(800, lambda: self._show_done(False))

    def _find_python(self) -> tuple[bool, str]:
        for cmd in ["python", "python3", "py"]:
            try:
                r = subprocess.run([cmd, "--version"], capture_output=True, text=True, timeout=5)
                if r.returncode == 0:
                    ver = r.stdout.strip() or r.stderr.strip()
                    parts = ver.split()[-1].split(".")
                    if len(parts) >= 2 and int(parts[0]) >= 3 and int(parts[1]) >= 10:
                        exe = subprocess.run(
                            [cmd, "-c", "import sys; print(sys.executable)"],
                            capture_output=True, text=True
                        ).stdout.strip()
                        return True, exe or cmd
            except Exception:
                pass
        return False, ""

    def _find_pythonw(self, python_exe: str) -> str:
        """Retourne le chemin vers pythonw.exe (sans console)."""
        pw = python_exe.replace("python.exe", "pythonw.exe")
        return pw if os.path.exists(pw) else python_exe

    def _get_latest_zip(self) -> tuple[str, str]:
        resp = requests.get(API_LATEST,
                            headers={"Accept": "application/vnd.github+json"},
                            timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data["zipball_url"], data["tag_name"]

    def _make_shortcut(self, target: str, args: str, lnk_path: str, working_dir: str):
        """Crée un raccourci .lnk via PowerShell (sans dépendance externe)."""
        ps = (
            f'$ws = New-Object -ComObject WScript.Shell; '
            f'$s = $ws.CreateShortcut("{lnk_path}"); '
            f'$s.TargetPath = "{target}"; '
            f'$s.Arguments = \'{args}\'; '
            f'$s.WorkingDirectory = "{working_dir}"; '
            f'$s.Save()'
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True, text=True
        )

    # ═══════════════════════════════════════════════════════
    #  PAGE 4 — TERMINÉ
    # ═══════════════════════════════════════════════════════

    def _build_done(self):
        f = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self._pages["done"] = f
        self._done_widgets = {}

        top = ctk.CTkFrame(f, height=160, fg_color=CARD, corner_radius=0)
        top.pack(fill="x")

        self._done_icon_lbl = ctk.CTkLabel(top, text="✅", font=("Segoe UI Emoji", 52))
        self._done_icon_lbl.pack(pady=(24, 4))
        self._done_title_lbl = ctk.CTkLabel(top, text="Installation réussie !",
                                             font=ctk.CTkFont("Segoe UI", 22, "bold"),
                                             text_color="#69f0ae")
        self._done_title_lbl.pack()

        body = ctk.CTkFrame(f, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=40, pady=24)

        self._done_msg_lbl = ctk.CTkLabel(body,
                                           text="ScanWebPDA est maintenant installé sur votre système.\n"
                                                "Vous pouvez le lancer depuis le raccourci Bureau\n"
                                                "ou via le Menu Démarrer.",
                                           font=ctk.CTkFont("Segoe UI", 13),
                                           text_color=TEXT, justify="left")
        self._done_msg_lbl.pack(anchor="w")

        foot = ctk.CTkFrame(f, fg_color=CARD, height=56, corner_radius=0)
        foot.pack(fill="x", side="bottom")

        self._done_widgets["launch"] = ctk.CTkButton(
            foot, text="🚀  Lancer ScanWebPDA",
            fg_color=GREEN, hover_color="#1b5e20",
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            width=200, height=36,
            command=self._launch_app
        )
        self._done_widgets["launch"].pack(side="right", padx=20, pady=10)

        ctk.CTkButton(foot, text="Fermer",
                      fg_color="transparent", hover_color="#333355",
                      text_color=SUBTLE, width=100, height=36,
                      command=self.destroy).pack(side="right", padx=4, pady=10)

    def _show_done(self, success: bool):
        if not success:
            self._done_icon_lbl.configure(text="❌")
            self._done_title_lbl.configure(text="Échec de l'installation",
                                            text_color="#ef5350")
            self._done_msg_lbl.configure(
                text="Une erreur est survenue pendant l'installation.\n"
                     "Consultez le journal ci-dessous pour plus de détails.\n"
                     "Vous pouvez réessayer ou installer manuellement."
            )
            self._done_widgets["launch"].configure(state="disabled")
        self._show("done")

    def _launch_app(self):
        install_dir = self.install_dir.get()
        gui_path = os.path.join(install_dir, "gui.py")
        _, python_exe = self._find_python()
        pythonw = self._find_pythonw(python_exe)
        subprocess.Popen([pythonw, gui_path], cwd=install_dir)
        self.destroy()

    # ═══════════════════════════════════════════════════════
    #  HELPERS UI
    # ═══════════════════════════════════════════════════════

    def _header(self, parent, title: str, subtitle: str):
        top = ctk.CTkFrame(parent, height=70, fg_color=CARD, corner_radius=0)
        top.pack(fill="x")
        ctk.CTkLabel(top, text=title,
                     font=ctk.CTkFont("Segoe UI", 17, "bold"),
                     text_color="#64b5f6").pack(side="left", padx=24, pady=(16, 4), anchor="w")
        ctk.CTkLabel(top, text=subtitle,
                     font=ctk.CTkFont("Segoe UI", 11),
                     text_color=SUBTLE).pack(side="left", padx=4, pady=(20, 0), anchor="w")


if __name__ == "__main__":
    app = InstallerApp()
    app.mainloop()
