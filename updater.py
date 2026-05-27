"""
updater.py — Système de mise à jour automatique via GitHub Releases.

Fonctionnement :
- Interroge l'API GitHub pour récupérer la dernière release.
- Compare la version distante à la version locale (version.py).
- Télécharge le .zip de la release et l'extrait en remplaçant les fichiers du projet.
- Les fichiers sensibles (config.json, data.db, proxies.json) ne sont jamais écrasés.
"""

import os
import sys
import json
import zipfile
import shutil
import tempfile
import threading
import requests
from packaging.version import Version

from version import VERSION

# ── Configuration ──────────────────────────────────────────────────────────────
GITHUB_OWNER = "gbaby448"
GITHUB_REPO  = "ScanWebPDA"
API_URL      = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"

# Ces fichiers ne seront JAMAIS écrasés lors d'une mise à jour
PROTECTED_FILES = {"config.json", "data.db", "proxies.json"}

# ── Fonctions publiques ─────────────────────────────────────────────────────────

def get_latest_release(token: str = "") -> dict | None:
    """
    Interroge l'API GitHub et retourne les infos de la dernière release,
    ou None en cas d'erreur.

    Retourne un dict avec les clés :
        - tag_name  : ex. "v1.2.0"
        - version   : ex. "1.2.0"  (sans le 'v')
        - body      : notes de version (changelog)
        - zip_url   : URL du zip source code
    """
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        resp = requests.get(API_URL, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        tag = data.get("tag_name", "")
        version_str = tag.lstrip("v")
        zip_url = data.get("zipball_url", "")
        return {
            "tag_name": tag,
            "version":  version_str,
            "body":     data.get("body", ""),
            "zip_url":  zip_url,
        }
    except Exception:
        return None


def is_update_available(latest_version: str) -> bool:
    """Retourne True si la version distante est plus récente que la locale."""
    try:
        return Version(latest_version) > Version(VERSION)
    except Exception:
        return False


def download_and_install(
    zip_url: str,
    install_dir: str,
    progress_callback=None,
    token: str = ""
) -> tuple[bool, str]:
    """
    Télécharge le zip de la release et remplace les fichiers du projet.

    Args:
        zip_url          : URL du zipball GitHub.
        install_dir      : Dossier racine de l'application (d:\\ScanWebPDA).
        progress_callback: Appelé avec (valeur_float 0.0-1.0, message_str).
        token            : GitHub PAT optionnel (dépôt privé).

    Returns:
        (True, "") en cas de succès, (False, "message d'erreur") sinon.
    """
    def _progress(val, msg):
        if progress_callback:
            progress_callback(val, msg)

    try:
        _progress(0.05, "Connexion à GitHub...")
        headers = {"Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        # ── Téléchargement ──────────────────────────────────────────────────
        resp = requests.get(zip_url, headers=headers, timeout=30, stream=True)
        resp.raise_for_status()

        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        tmp_zip = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")

        _progress(0.1, "Téléchargement en cours...")
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                tmp_zip.write(chunk)
                downloaded += len(chunk)
                if total > 0:
                    pct = 0.1 + 0.5 * (downloaded / total)
                    _progress(pct, f"Téléchargement... {downloaded // 1024} Ko")
        tmp_zip.close()

        _progress(0.65, "Extraction de l'archive...")

        # ── Extraction dans un dossier temporaire ──────────────────────────
        tmp_dir = tempfile.mkdtemp()
        with zipfile.ZipFile(tmp_zip.name, "r") as zf:
            zf.extractall(tmp_dir)

        # GitHub crée un sous-dossier du type "gbaby448-ScanWebPDA-<hash>/"
        extracted_root = None
        for entry in os.listdir(tmp_dir):
            candidate = os.path.join(tmp_dir, entry)
            if os.path.isdir(candidate):
                extracted_root = candidate
                break

        if not extracted_root:
            raise RuntimeError("Structure du zip inattendue.")

        _progress(0.75, "Installation des fichiers...")

        # ── Copie en écrasant (sauf fichiers protégés) ────────────────────
        for root, dirs, files in os.walk(extracted_root):
            # Chemin relatif dans l'archive
            rel_root = os.path.relpath(root, extracted_root)
            dest_dir = os.path.join(install_dir, rel_root)
            os.makedirs(dest_dir, exist_ok=True)

            for fname in files:
                # Ne jamais écraser les fichiers sensibles
                if fname in PROTECTED_FILES and rel_root == ".":
                    continue
                src = os.path.join(root, fname)
                dst = os.path.join(dest_dir, fname)
                shutil.copy2(src, dst)

        # ── Nettoyage ─────────────────────────────────────────────────────
        _progress(0.95, "Nettoyage...")
        shutil.rmtree(tmp_dir, ignore_errors=True)
        os.unlink(tmp_zip.name)

        _progress(1.0, "Mise à jour installée avec succès !")
        return True, ""

    except Exception as exc:
        return False, str(exc)


def check_for_updates_async(callback, token: str = ""):
    """
    Lance la vérification en arrière-plan (thread daemon).
    Appelle callback(release_info_dict | None) une fois terminé.
    release_info_dict vaut None si aucune mise à jour n'est disponible.
    """
    def _worker():
        release = get_latest_release(token)
        if release and is_update_available(release["version"]):
            callback(release)
        else:
            callback(None)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
