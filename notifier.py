import requests
import socket

def send_notification(ntfy_url, reference, title, price, url, country=None, translated_title=None):
    """
    Envoie une notification d'alerte vers le topic ntfy configuré avec pays et traduction.
    """
    if not ntfy_url:
        print("Erreur: URL ntfy non configurée.")
        return False
        
    title_section = f"Titre : {title}"
    if translated_title:
        title_section = f"Titre (FR) : {translated_title}\nTitre (Original) : {title}"
        
    payload = (
        f"Nouvelle pièce auto trouvée !\n\n"
        f"Référence recherchée : {reference}\n"
        f"{title_section}\n"
        f"Prix : {price}\n"
    )
    
    if country:
        payload += f"Provenance : {country}\n"
        
    payload += f"Lien : {url}"
    
    title_header = f"Pièce trouvée : {reference}"
    if country:
        flag = country.split(" ")[0] if " " in country else "🚗"
        title_header = f"[{flag}] Pièce trouvée : {reference}"
    
    headers = {
        # Encodage en bytes UTF-8 pour supporter les emojis (drapeaux, etc.)
        # requests encode les headers en latin-1 par défaut, ce qui échoue avec les emojis
        "Title": title_header.encode("utf-8"),
        "Priority": "high",
        "Tags": "car,wrench,bell",
        "Content-Type": "text/plain; charset=utf-8"
    }
    
    try:
        response = requests.post(
            ntfy_url,
            data=payload.encode('utf-8'),
            headers=headers,
            timeout=10
        )
        if response.status_code == 200:
            print("Notification envoyée avec succès via ntfy.")
            return True
        else:
            print(f"Erreur lors de l'envoi de la notification: Code {response.status_code}")
            return False
    except Exception as e:
        print(f"Exception lors de la notification ntfy: {e}")
        return False


def test_ntfy_diagnostic(ntfy_url, log_callback):
    """
    Effectue un diagnostic complet de la connexion ntfy et retourne les résultats
    étape par étape via log_callback(message).
    Retourne True si le test a réussi, False sinon.
    """
    log = log_callback  # alias court

    log("=" * 50)
    log("🔎 DIAGNOSTIC NTFY — Début du test")
    log("=" * 50)

    # ── ÉTAPE 1 : Vérification de l'URL ─────────────────
    log(f"\n[1/5] Vérification de l'URL saisie...")
    if not ntfy_url:
        log("  ❌ ÉCHEC : Aucune URL ntfy n'est configurée.")
        log("       → Renseignez une URL comme : https://ntfy.sh/mon_topic")
        return False
    log(f"  URL : {ntfy_url}")

    if not ntfy_url.startswith("http"):
        log("  ❌ ÉCHEC : L'URL ne commence pas par 'http://' ou 'https://'.")
        log("       → Corrigez l'URL, ex: https://ntfy.sh/ScanWebPDA")
        return False

    # Extraire le domaine pour le test DNS
    try:
        from urllib.parse import urlparse
        parsed = urlparse(ntfy_url)
        host = parsed.hostname
        scheme = parsed.scheme
        path = parsed.path.strip("/")
        log(f"  ✅ URL valide — Hôte: {host} | Topic: {path} | Protocole: {scheme}")
    except Exception as e:
        log(f"  ❌ ÉCHEC parsing URL : {e}")
        return False

    # ── ÉTAPE 2 : Résolution DNS ─────────────────────────
    log(f"\n[2/5] Résolution DNS de '{host}'...")
    try:
        ip = socket.gethostbyname(host)
        log(f"  ✅ DNS résolu — IP : {ip}")
    except socket.gaierror as e:
        log(f"  ❌ ÉCHEC DNS : Impossible de résoudre '{host}'")
        log(f"       Erreur système : {e}")
        log("       → Vérifiez votre connexion Internet ou que l'URL est correcte.")
        return False

    # ── ÉTAPE 3 : Connexion TCP (ping réseau) ────────────
    log(f"\n[3/5] Test de connexion TCP vers {host}:443...")
    port = 443 if scheme == "https" else 80
    try:
        sock = socket.create_connection((host, port), timeout=5)
        sock.close()
        log(f"  ✅ Connexion TCP réussie sur le port {port}")
    except Exception as e:
        log(f"  ❌ ÉCHEC connexion TCP sur le port {port}")
        log(f"       Erreur : {e}")
        log("       → Le serveur est peut-être bloqué par un pare-feu ou hors ligne.")
        return False

    # ── ÉTAPE 4 : Requête GET sur le topic ──────────────
    log(f"\n[4/5] Vérification du topic ntfy (GET)...")
    try:
        headers_get = {"Accept": "application/json"}
        r = requests.get(f"{ntfy_url.rstrip('/')}/json?poll=1", headers=headers_get, timeout=8)
        log(f"  Réponse GET : HTTP {r.status_code}")
        if r.status_code in (200, 204):
            log("  ✅ Topic accessible en lecture")
        elif r.status_code == 401:
            log("  ⚠️  Topic protégé par authentification (401 Unauthorized)")
            log("       → Si votre topic est privé, ajoutez un token dans l'URL.")
        elif r.status_code == 403:
            log("  ❌ Accès interdit (403 Forbidden)")
            log("       → Ce topic est peut-être réservé ou votre IP est bloquée.")
        elif r.status_code == 404:
            log("  ⚠️  Topic non trouvé (404) — il sera créé automatiquement à l'envoi.")
        else:
            log(f"  ⚠️  Réponse inattendue : {r.status_code} — {r.text[:100]}")
    except Exception as e:
        log(f"  ⚠️  Impossible de faire le GET de vérification : {e}")

    # ── ÉTAPE 5 : Envoi de la notification de test ──────
    log(f"\n[5/5] Envoi de la notification de test...")
    test_payload = "🔧 Test ScanWebPDA\n\nCeci est un message de test pour vérifier que les alertes ntfy fonctionnent correctement."
    test_headers = {
        "Title": "ScanWebPDA - Test de connexion".encode("utf-8"),
        "Priority": "default",
        "Tags": "white_check_mark,car",
        "Content-Type": "text/plain; charset=utf-8"
    }
    try:
        response = requests.post(
            ntfy_url,
            data=test_payload.encode("utf-8"),
            headers=test_headers,
            timeout=10
        )
        log(f"  Réponse POST : HTTP {response.status_code}")

        if response.status_code == 200:
            log("  ✅ SUCCÈS ! Notification de test envoyée avec succès.")
            log("       → Vérifiez votre application ntfy, vous devriez avoir reçu un message.")
            log("\n✅ DIAGNOSTIC COMPLET — ntfy est opérationnel !")
            return True
        elif response.status_code == 400:
            log("  ❌ ÉCHEC (400 Bad Request) — Le format de la requête est invalide.")
            log(f"       Réponse : {response.text[:200]}")
        elif response.status_code == 401:
            log("  ❌ ÉCHEC (401 Unauthorized) — Authentification requise.")
            log("       → Ajoutez un token d'accès dans l'URL ou les headers.")
        elif response.status_code == 403:
            log("  ❌ ÉCHEC (403 Forbidden) — Publication interdite sur ce topic.")
            log("       → Vérifiez que le topic est public ou que vous avez les droits.")
        elif response.status_code == 429:
            log("  ❌ ÉCHEC (429 Too Many Requests) — Limite de débit atteinte.")
            log("       → Attendez quelques minutes avant de réessayer.")
            log("       → Sur ntfy.sh gratuit, la limite est de 250 messages/jour.")
        else:
            log(f"  ❌ ÉCHEC inattendu (HTTP {response.status_code})")
            log(f"       Réponse serveur : {response.text[:200]}")

        log("\n❌ DIAGNOSTIC — ntfy n'a pas pu envoyer la notification.")
        return False

    except requests.exceptions.ConnectionError as e:
        log(f"  ❌ ÉCHEC — Erreur de connexion réseau : {e}")
        log("       → Vérifiez votre connexion Internet.")
        return False
    except requests.exceptions.Timeout:
        log("  ❌ ÉCHEC — Timeout : le serveur ntfy n'a pas répondu en 10 secondes.")
        log("       → Serveur peut-être surchargé. Réessayez plus tard.")
        return False
    except Exception as e:
        log(f"  ❌ ÉCHEC — Exception inattendue : {e}")
        return False
