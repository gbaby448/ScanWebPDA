"""
publish.py — Script de publication automatique vers GitHub.

Usage :
    python publish.py

Ce script :
  1. Affiche la version actuelle et demande la nouvelle version.
  2. Demande un résumé du changelog.
  3. Met à jour version.py.
  4. Fait git add / commit / tag / push.
  5. Crée la Release GitHub via l'API (nécessite un token PAT).
"""

import os
import sys
import re
import subprocess
import json
import requests
from datetime import datetime

# ── Configuration ──────────────────────────────────────────────────────────────
GITHUB_OWNER = "gbaby448"
GITHUB_REPO  = "ScanWebPDA"
VERSION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "version.py")
CONFIG_FILE  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
TOKEN_FILE   = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".github_token")

# ── Couleurs ANSI (désactivées sur Windows si le terminal ne les supporte pas) ─
import sys as _sys
_USE_COLOR = _sys.platform != "win32" or os.environ.get("WT_SESSION") or os.environ.get("TERM_PROGRAM")
GREEN  = "\033[92m" if _USE_COLOR else ""
YELLOW = "\033[93m" if _USE_COLOR else ""
RED    = "\033[91m" if _USE_COLOR else ""
CYAN   = "\033[96m" if _USE_COLOR else ""
BOLD   = "\033[1m"  if _USE_COLOR else ""
RESET  = "\033[0m"  if _USE_COLOR else ""

def banner():
    print(f"""
{CYAN}{BOLD}╔══════════════════════════════════════════════╗
║   ScanWebPDA — Publication automatique      ║
║   github.com/{GITHUB_OWNER}/{GITHUB_REPO}   ║
╚══════════════════════════════════════════════╝{RESET}
""")

def ok(msg):    print(f"  {GREEN}✔{RESET}  {msg}")
def warn(msg):  print(f"  {YELLOW}⚠{RESET}  {msg}")
def error(msg): print(f"  {RED}✘{RESET}  {msg}")
def step(msg):  print(f"\n{BOLD}{CYAN}▶ {msg}{RESET}")

# ── Helpers ────────────────────────────────────────────────────────────────────

def read_current_version() -> str:
    """Lit la version dans version.py."""
    with open(VERSION_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    m = re.search(r'VERSION\s*=\s*"([^"]+)"', content)
    if not m:
        error("Impossible de lire VERSION dans version.py")
        sys.exit(1)
    return m.group(1)


def write_version(new_version: str):
    """Met à jour la constante VERSION dans version.py."""
    with open(VERSION_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    content = re.sub(r'VERSION\s*=\s*"[^"]+"', f'VERSION = "{new_version}"', content)
    with open(VERSION_FILE, "w", encoding="utf-8") as f:
        f.write(content)


def validate_semver(version: str) -> bool:
    """Vérifie que la version respecte le format X.Y.Z."""
    return bool(re.fullmatch(r"\d+\.\d+\.\d+", version))


def run(cmd: list[str], cwd: str = None) -> tuple[bool, str]:
    """Exécute une commande shell et retourne (succès, output)."""
    result = subprocess.run(
        cmd,
        cwd=cwd or os.path.dirname(os.path.abspath(__file__)),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )
    output = (result.stdout + result.stderr).strip()
    return result.returncode == 0, output


def read_token() -> str:
    """Lit le token GitHub depuis .github_token, ou le demande à l'utilisateur.
    Le token est stocké dans un fichier séparé gitignored, jamais dans config.json.
    """
    # Lire depuis le fichier .github_token (gitignored)
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r", encoding="utf-8") as f:
            token = f.read().strip()
        if token:
            ok(f"Token lu depuis .github_token")
            return token

    print(f"\n{YELLOW}Aucun token GitHub trouvé.{RESET}")
    print(f"  Crée un Personal Access Token sur :")
    print(f"  {CYAN}https://github.com/settings/tokens/new{RESET}")
    print(f"  (Coche uniquement : {BOLD}repo{RESET})\n")
    token = input("  Colle ton token ici : ").strip()
    if not token:
        error("Token requis pour créer une release GitHub.")
        sys.exit(1)
    _save_token(token)
    return token


def _save_token(token: str):
    """Sauvegarde le token dans .github_token (jamais dans config.json)."""
    try:
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(token)
        ok("Token sauvegardé dans .github_token (gitignored).")
    except Exception as e:
        warn(f"Impossible de sauvegarder le token : {e}")


def create_github_release(tag: str, title: str, body: str, token: str) -> bool:
    """Crée la release via l'API GitHub."""
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    payload = {
        "tag_name":         tag,
        "name":             title,
        "body":             body,
        "draft":            False,
        "prerelease":       False,
        "make_latest":      "true"
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        if resp.status_code == 201:
            release_url = resp.json().get("html_url", "")
            ok(f"Release créée : {CYAN}{release_url}{RESET}")
            return True
        else:
            error(f"Erreur API GitHub ({resp.status_code}) : {resp.json().get('message', resp.text)}")
            return False
    except Exception as e:
        error(f"Erreur réseau : {e}")
        return False


def collect_changelog(current_version: str, new_version: str) -> str:
    """Demande à l'utilisateur de saisir les notes de version."""
    print(f"\n  Saisit le changelog pour {BOLD}v{new_version}{RESET}")
    print(f"  (Appuie sur Entrée deux fois pour terminer)\n")

    lines = []
    empty_count = 0
    while empty_count < 1:
        line = input("  > ")
        if line == "":
            empty_count += 1
        else:
            empty_count = 0
            lines.append(line)

    if not lines:
        # Changelog automatique si rien n'est saisi
        lines = [f"Mise à jour de v{current_version} vers v{new_version}."]
        warn("Changelog vide → message automatique utilisé.")

    # Récupérer les commits depuis le dernier tag
    ok_git, commits_raw = run(["git", "log", f"v{current_version}..HEAD", "--oneline", "--no-decorate"])
    recent_commits = ""
    if ok_git and commits_raw:
        commit_lines = commits_raw.strip().splitlines()[:10]  # max 10
        recent_commits = "\n\n### Commits inclus\n" + "\n".join(f"- {c}" for c in commit_lines)

    changelog = "\n".join(lines) + recent_commits
    return changelog


# ── Script principal ───────────────────────────────────────────────────────────

def main():
    os.system("")  # Active les couleurs ANSI sur Windows

    banner()

    # ── 1. Version actuelle ─────────────────────────────────────────────────
    step("Version actuelle")
    current = read_current_version()
    ok(f"Version locale : {BOLD}v{current}{RESET}")

    # Proposer une version patch par défaut
    parts = current.split(".")
    default_new = f"{parts[0]}.{parts[1]}.{int(parts[2]) + 1}"

    # ── 2. Nouvelle version ─────────────────────────────────────────────────
    step("Nouvelle version")
    new_version = input(f"  Nouvelle version [{BOLD}{default_new}{RESET}] : ").strip()
    if not new_version:
        new_version = default_new
    if not validate_semver(new_version):
        error(f"Format invalide '{new_version}' → doit être X.Y.Z (ex: 1.2.0)")
        sys.exit(1)
    if new_version == current:
        error(f"La version '{new_version}' est identique à la version actuelle.")
        sys.exit(1)

    # ── 3. Changelog ────────────────────────────────────────────────────────
    step("Notes de version (changelog)")
    changelog = collect_changelog(current, new_version)

    # ── 4. Token GitHub ─────────────────────────────────────────────────────
    step("Token GitHub")
    token = read_token()

    # ── Récapitulatif ───────────────────────────────────────────────────────
    print(f"""
{BOLD}╔══════ RÉCAPITULATIF ══════════════════════════════╗{RESET}
  Dépôt      : {CYAN}github.com/{GITHUB_OWNER}/{GITHUB_REPO}{RESET}
  Version    : {BOLD}v{current}{RESET}  →  {GREEN}{BOLD}v{new_version}{RESET}
  Release    : v{new_version} - {datetime.now().strftime("%d/%m/%Y")}
{BOLD}╚═══════════════════════════════════════════════════╝{RESET}""")

    confirm = input(f"\n  {BOLD}Confirmer la publication ? [O/n] : {RESET}").strip().lower()
    if confirm in ("n", "non", "no"):
        warn("Publication annulée.")
        sys.exit(0)

    errors_occurred = False

    # ── 5. Mise à jour version.py ───────────────────────────────────────────
    step("Mise à jour de version.py")
    write_version(new_version)
    ok(f"version.py → VERSION = \"{new_version}\"")

    # ── 6. Git add + commit ─────────────────────────────────────────────────
    step("Commit Git")
    success, out = run(["git", "add", "-A"])
    if not success:
        error(f"git add échoué : {out}"); errors_occurred = True

    commit_msg = f"chore: bump version to v{new_version}"
    success, out = run(["git", "commit", "-m", commit_msg])
    if success:
        ok(f"Commit : {commit_msg}")
    elif "nothing to commit" in out:
        warn("Rien à commiter (version.py déjà à jour ?)")
    else:
        error(f"git commit échoué : {out}"); errors_occurred = True

    # ── 7. Git tag ──────────────────────────────────────────────────────────
    step("Tag Git")
    tag = f"v{new_version}"
    success, out = run(["git", "tag", tag])
    if success:
        ok(f"Tag créé : {tag}")
    else:
        error(f"git tag échoué : {out}"); errors_occurred = True

    # ── 8. Git push ─────────────────────────────────────────────────────────
    step("Push vers GitHub")
    success, out = run(["git", "push", "origin", "main"])
    if success:
        ok("Branche main poussée.")
    else:
        error(f"git push main échoué : {out}"); errors_occurred = True

    success, out = run(["git", "push", "origin", tag])
    if success:
        ok(f"Tag {tag} poussé.")
    else:
        error(f"git push tag échoué : {out}"); errors_occurred = True

    if errors_occurred:
        warn("Des erreurs Git sont survenues. La release GitHub ne sera pas créée.")
        sys.exit(1)

    # ── 9. Création de la Release GitHub ────────────────────────────────────
    step("Création de la Release GitHub")
    release_title = f"v{new_version} - {datetime.now().strftime('%d/%m/%Y')}"
    created = create_github_release(tag, release_title, changelog, token)

    if created:
        print(f"""
{GREEN}{BOLD}╔══════════════════════════════════════════════════╗
║   ✅  Publication réussie !                      ║
║   Les utilisateurs verront la mise à jour         ║
║   automatiquement au prochain démarrage.          ║
╚══════════════════════════════════════════════════╝{RESET}
""")
    else:
        error("La release GitHub n'a pas pu être créée.")
        print(f"  Tu peux la créer manuellement sur :")
        print(f"  {CYAN}https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/new?tag={tag}{RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()
