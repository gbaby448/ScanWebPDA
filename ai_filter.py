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

def is_mechanical_part(title, reference, ollama_url="http://localhost:11434"):
    """
    Interroge le modèle local qwen2.5-coder:7b pour valider si le titre de l'annonce
    correspond réellement à une pièce mécanique/physique automobile en lien avec la référence.
    Retourne True si OUI, False si NON.
    """
    url = f"{ollama_url}/api/generate"
    
    # Nettoyage anti-injection de prompt avant d'insérer dans le LLM
    safe_title = _sanitize_prompt_input(title, max_length=200)
    safe_reference = _sanitize_prompt_input(reference, max_length=100)

    prompt = (
        f"Tu es un expert en mécanique automobile et en pièces de rechange.\n"
        f"L'utilisateur recherche la référence suivante : '{safe_reference}'.\n"
        f"Un robot de surveillance a trouvé un article sur le web :\n"
        f"Titre de l'annonce : '{safe_title}'\n\n"
        f"Consignes de validation :\n"
        f"1. Détermine si cet article correspond réellement à une pièce détachée physique (neuve ou occasion) compatible ou liée à la recherche.\n"
        f"2. Réponds 'NON' si l'article est un manuel technique, un jouet (miniature), un vêtement, un autocollant, un outil générique, une prestation de service, ou un objet publicitaire sans rapport direct.\n"
        f"3. Réponds 'OUI' s'il s'agit d'une vraie pièce mécanique automobile physique.\n\n"
        f"IMPORTANT : Réponds UNIQUEMENT par le mot 'OUI' ou 'NON'. Ne donne aucune explication ni aucune justification."
    )
    
    payload = {
        "model": "qwen2.5-coder:7b",
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.0  # Pour un comportement déterministe
        }
    }
    
    try:
        response = requests.post(url, json=payload, timeout=15)
        if response.status_code == 200:
            result = response.json().get("response", "").strip().upper()
            
            # Nettoyage minimal au cas où le modèle aurait ajouté de la ponctuation
            if "OUI" in result:
                return True
            elif "NON" in result:
                return False
                
            # Log de secours si la réponse est inattendue
            print(f"Ollama a retourné une réponse inattendue: '{result}'")
            return False
        else:
            print(f"Ollama a retourné une erreur HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"Erreur de connexion à Ollama lors de l'analyse sémantique: {e}")
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
        response = requests.post(url, json=payload, timeout=10)
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
