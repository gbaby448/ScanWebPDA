import requests
import json
import re


def _sanitize_prompt_input(text, max_length=200):
    """
    Nettoie une valeur utilisateur avant injection dans un prompt LLM.
    - Tronque à max_length caractères
    - Supprime les caractères de contrôle (newlines, tabs, etc.)
    """
    if not text:
        return ""
    # Supprimer les caractères de contrôle (hors espace normal)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    # Normaliser les sauts de ligne en espace (empêche l'injection multi-ligne)
    text = text.replace('\n', ' ').replace('\r', ' ')
    return text[:max_length]

# Domaines de forums, blogs et sources non-commerciales a exclure systematiquement
_NON_COMMERCIAL_DOMAINS = [
    "forum", "forums", "community", "reddit", "quora", "stackoverflow",
    "wikipedia", "wiki", "howto", "blog", "blogspot", "wordpress",
    "youtube", "dailymotion", "vimeo",
    "trafic-amenage", "auto-evasion", "passion-ford", "forum-auto",
    "l-argus", "caradisiac", "autoplus", "turbo.fr",
    "techniques", "repair", "manual", "fiche-technique",
]

# Mots-cles de titres indiquant qu'il ne s'agit PAS d'une annonce de vente
_REJECT_TITLE_KEYWORDS = [
    "forum", "discussion", "topic", "thread", "question", "reponse",
    "avis", "conseil", "aide", "probleme", "tuto", "tutoriel", "guide",
    "fiche technique", "catalogue", "documentation", "manuel",
    "youtube", "video", "photo", "image", "actualite", "news",
    "wikipedia", "wikimeca",
    "location", "louez", "louer", "prestation", "service", "reparation",
    "diagnostic", "entretien",
]

# Mots-cles commerciaux qui confirment qu'il s'agit d'une vraie annonce de vente
_SALE_TITLE_KEYWORDS = [
    "vente", "vends", "vendre", "vend ", "occasion", "neuf", "neuve",
    "achat", "acheter", "prix", "euro", "eur", "€",
    "annonce", "leboncoin", "ebay", "ovoko", "oscaro", "opisto",
    "b-parts", "mister-auto", "auto-doc", "allegro", "picclick",
    "disponible", "stock", "livraison", "shipping", "buy", "sale", "sell",
    "for sale", "zu verkaufen", "na sprzedaz", "kup", "acheter maintenant",
]

def _pre_filter_is_sale_listing(title: str, url: str) -> bool:
    """
    Filtre rapide (sans IA) pour eliminer les sources non-commerciales evidentes.
    Retourne True si l'annonce semble etre une vraie offre de vente.
    Retourne False si c'est clairement un forum, blog, tuto ou article de presse.
    """
    title_lower = title.lower()
    url_lower = url.lower()

    # 1. Rejeter si le titre contient des mots de forum/discussion
    for kw in _REJECT_TITLE_KEYWORDS:
        if kw in title_lower:
            return False

    # 2. Rejeter si l'URL contient un indicateur de forum/blog
    for domain_kw in _NON_COMMERCIAL_DOMAINS:
        if domain_kw in url_lower:
            return False

    # 3. Valider si le titre contient au moins un indicateur commercial
    for kw in _SALE_TITLE_KEYWORDS:
        if kw in title_lower:
            return True

    # 4. Validation neutre : on laisse l'IA trancher si on ne sait pas
    return True


def is_mechanical_part(title, reference, url="", ollama_url="http://localhost:11434"):
    """
    Valide en 2 etapes si un titre d'annonce correspond a une vraie offre de vente
    d'une piece mecanique automobile correspondant a la reference recherchee.
    
    Etape 1 : pre-filtre rapide sans IA (forums, blogs, manuels -> rejetes instantanement)
    Etape 2 : validation IA stricte (doit etre une annonce de vente de la piece exacte)
    
    Retourne True si valide, False sinon.
    """
    # --- Etape 1 : Pre-filtre rapide (sans appel reseau) ---
    if not _pre_filter_is_sale_listing(title, url):
        print(f"[Pre-filtre] Rejete (source non-commerciale): '{title[:80]}'")
        return False

    # --- Etape 2 : Validation IA avec prompt strict ---
    api_url = f"{ollama_url}/api/generate"
    
    # Nettoyage anti-injection de prompt avant d'inserer dans le LLM
    safe_title = _sanitize_prompt_input(title, max_length=200)
    safe_reference = _sanitize_prompt_input(reference, max_length=100)

    prompt = (
        f"Tu es un expert en vente de pieces detachees automobiles.\n"
        f"L'utilisateur cherche a ACHETER la piece suivante : '{safe_reference}'.\n"
        f"Un robot a trouve ce titre sur internet : '{safe_title}'\n\n"
        f"Reponds OUI uniquement si TOUTES ces conditions sont reunies :\n"
        f"- C'est une annonce de VENTE (pas un forum, blog, tuto, video, article de presse)\n"
        f"- La piece proposee est bien une PIECE DETACHEE PHYSIQUE (neuve ou d'occasion)\n"
        f"- La piece correspond a ce que recherche l'utilisateur (meme type de piece ou meme reference)\n\n"
        f"Reponds NON dans TOUS les autres cas (forum, discussion, service, reparation, miniature, accessoire, etc.)\n\n"
        f"IMPORTANT : Reponds UNIQUEMENT par le mot OUI ou NON. Aucune explication."
    )
    
    payload = {
        "model": "qwen2.5-coder:7b",
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.0
        }
    }
    
    try:
        response = requests.post(api_url, json=payload, timeout=60)
        if response.status_code == 200:
            result = response.json().get("response", "").strip().upper()
            if "OUI" in result:
                return True
            elif "NON" in result:
                return False
            print(f"Ollama a retourne une reponse inattendue: '{result}'")
            return False
        else:
            print(f"Ollama a retourne une erreur HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"Erreur de connexion a Ollama lors de l'analyse semantique: {e}")
        return False

def translate_to_french(text, ollama_url="http://localhost:11434"):
    """
    Demande à l'Ollama local de traduire le titre en Français si ce n'est pas déjà le cas.
    Répond uniquement par le titre traduit en français, sans commentaire.
    """
    # Heuristique rapide : si le texte contient déjà des mots typiques en français, on évite
    french_words = {"injecteur", "boite", "vitesse", "moteur", "embrayage", "alternateur", "démarreur", "phare", "feu", "pare-chocs"}
    lower_text = text.lower()
    if any(word in lower_text for word in french_words) and "kasne" not in lower_text:
        return text

    url = f"{ollama_url}/api/generate"
    safe_text = _sanitize_prompt_input(text, max_length=200)
    prompt = (
        "Tu es un traducteur automobile professionnel bilingue.\n"
        f"Traduis le titre d'annonce automobile suivant en français.\n"
        "Conserve les références de pièces et les nombres inchangés.\n"
        "Répond UNIQUEMENT avec le titre traduit en français, sans commentaire, sans explications et sans guillemets.\n\n"
        f"Titre : {safe_text}"
    )
    
    payload = {
        "model": "qwen2.5-coder:7b",
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.0,
            "num_predict": 100
        }
    }
    
    try:
        response = requests.post(url, json=payload, timeout=60)
        if response.status_code == 200:
            translation = response.json().get("response", "").strip()
            if translation:
                # Retirer les éventuels guillemets
                translation = translation.replace('"', '').replace("'", "")
                return translation
    except Exception as e:
        print(f"Erreur de traduction avec Ollama: {e}")
    return text

def check_ollama_status(ollama_url="http://localhost:11434"):
    """
    Vérifie si Ollama est joignable sur l'adresse et le port configurés.
    """
    try:
        # On interroge la racine ou l'endpoint d'état d'Ollama
        response = requests.get(ollama_url, timeout=2)
        return response.status_code == 200
    except Exception:
        return False
