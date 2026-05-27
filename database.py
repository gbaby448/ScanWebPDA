import sqlite3
import os
import re

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.db")

def _normalize_title(title):
    """Normalise un titre pour la comparaison : minuscules, sans espaces superflus ni ponctuation."""
    title = title.lower().strip()
    title = re.sub(r'[^\w\s]', '', title)   # Supprime la ponctuation
    title = re.sub(r'\s+', ' ', title)       # Normalise les espaces
    return title

def init_db():
    """Initialise la base de données SQLite et crée la table si elle n'existe pas, avec migrations."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scanned_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reference TEXT NOT NULL,
            title TEXT NOT NULL,
            title_normalized TEXT,
            url TEXT UNIQUE NOT NULL,
            price TEXT,
            found_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_part INTEGER DEFAULT 0
        )
    """)
    
    # Migrations de colonnes sécurisées
    migrations = [
        "ALTER TABLE scanned_items ADD COLUMN image_url TEXT",
        "ALTER TABLE scanned_items ADD COLUMN source_domain TEXT",
        "ALTER TABLE scanned_items ADD COLUMN country TEXT",
        "ALTER TABLE scanned_items ADD COLUMN translated_title TEXT",
        "ALTER TABLE scanned_items ADD COLUMN title_normalized TEXT",
        "ALTER TABLE scanned_items ADD COLUMN notified INTEGER DEFAULT 0",
    ]
    for sql in migrations:
        try:
            cursor.execute(sql)
        except sqlite3.OperationalError:
            pass  # Colonne déjà existante

    # Index pour accélérer les lookups fréquents (item_exists, has_been_notified)
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_url ON scanned_items (url)",
        "CREATE INDEX IF NOT EXISTS idx_title_domain ON scanned_items (title_normalized, source_domain)",
        "CREATE INDEX IF NOT EXISTS idx_notified ON scanned_items (url, notified)",
    ]
    for sql in indexes:
        try:
            cursor.execute(sql)
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()

def item_exists(url, title=None, source_domain=None):
    """
    Vérifie si un article a déjà été scanné.
    Double vérification :
      1. Par URL exacte (le plus fiable)
      2. Par titre normalisé + domaine (pour les URLs avec paramètres variables)
    Retourne True si l'article est déjà connu.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Vérification 1 : URL exacte
    cursor.execute("SELECT 1 FROM scanned_items WHERE url = ?", (url,))
    if cursor.fetchone():
        conn.close()
        return True

    # Vérification 2 : titre normalisé + même domaine (évite les doublons d'URL variables)
    if title and source_domain:
        norm = _normalize_title(title)
        cursor.execute(
            "SELECT 1 FROM scanned_items WHERE title_normalized = ? AND source_domain = ?",
            (norm, source_domain)
        )
        if cursor.fetchone():
            conn.close()
            return True

    conn.close()
    return False

def has_been_notified(url, title=None, source_domain=None):
    """
    Vérifie si une notification a déjà été envoyée pour cet article.
    Utilisé pour éviter les doublons de notifications ntfy.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Par URL exacte
    cursor.execute("SELECT notified FROM scanned_items WHERE url = ? AND notified = 1", (url,))
    if cursor.fetchone():
        conn.close()
        return True

    # Par titre normalisé + domaine
    if title and source_domain:
        norm = _normalize_title(title)
        cursor.execute(
            "SELECT 1 FROM scanned_items WHERE title_normalized = ? AND source_domain = ? AND notified = 1",
            (norm, source_domain)
        )
        if cursor.fetchone():
            conn.close()
            return True

    conn.close()
    return False

def mark_as_notified(url):
    """Marque un article comme ayant reçu une notification ntfy."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE scanned_items SET notified = 1 WHERE url = ?", (url,))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Erreur mark_as_notified: {e}")
    finally:
        conn.close()

def add_item(reference, title, url, price, is_part=0, image_url=None, source_domain=None, country=None, translated_title=None):
    """Ajoute un nouvel article scanné dans la base de données."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    title_normalized = _normalize_title(title) if title else ""
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO scanned_items
              (reference, title, title_normalized, url, price, is_part, image_url, source_domain, country, translated_title)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (reference, title, title_normalized, url, price, int(is_part), image_url, source_domain, country, translated_title))
        conn.commit()
        success = True
    except sqlite3.Error as e:
        print(f"Erreur d'insertion SQLite: {e}")
        success = False
    finally:
        conn.close()
    return success

def get_valid_items():
    """Récupère toutes les pièces validées par l'IA dans l'ordre antéchronologique."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, reference, title, url, price, found_date, image_url, source_domain, country, translated_title
        FROM scanned_items
        WHERE is_part = 1
        ORDER BY found_date DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def delete_item(item_id):
    """Supprime un article validé de la base de données."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM scanned_items WHERE id = ?", (item_id,))
        conn.commit()
        success = True
    except sqlite3.Error as e:
        print(f"Erreur de suppression SQLite: {e}")
        success = False
    finally:
        conn.close()
    return success

# Initialisation automatique de la base à l'import
init_db()
