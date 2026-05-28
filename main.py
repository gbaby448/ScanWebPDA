import time
import threading
import json
import os
import re
import ipaddress
import database
import scanner
import ai_filter
import notifier
import requests
import random
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# Mots-clés pour la détection du stock dans les titres/snippets
STOCK_OUT_KEYWORDS = [
    "rupture", "indisponible", "out of stock", "épuisé", "sold out",
    "nicht verfügbar", "brak", "non disponibile", "wyprzedany"
]

def _parse_price_value(price_str):
    """Extrait la valeur numérique d'un prix formaté (ex: '150€' → 150.0)."""
    if not price_str or price_str == "N/D":
        return None
    price_str = str(price_str).replace("\u00a0", "").replace(" ", "").replace(",", ".")
    match = re.search(r'(\d+(?:\.\d+)?)', price_str)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return None

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
]

def _is_safe_url(url):
    """
    Vérifie qu'une URL est sûre à récupérer (anti-SSRF) :
    - Doit être http ou https
    - Ne doit pas pointer vers localhost ou une IP privée/lien-local
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        host = parsed.hostname
        if not host:
            return False
        # Bloquer les noms d'hôte locaux
        if host in ("localhost", "localhost.localdomain"):
            return False
        # Bloquer les IPs privées, loopback, lien-local
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved:
                return False
        except ValueError:
            pass  # Ce n'est pas une IP (c'est un nom de domaine), on accepte
        return True
    except Exception:
        return False


def extract_og_metadata(url):
    """
    Tente de récupérer le domaine source et le lien de l'image d'illustration (og:image).
    """
    domain = ""
    image_url = None
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "")
    except Exception:
        pass

    # Guard anti-SSRF : on ne fait la requête que si l'URL est sûre
    if not _is_safe_url(url):
        return domain, image_url

    try:
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        # Timeout très court (3s) pour ne pas ralentir le cycle de surveillance
        response = requests.get(url, headers=headers, timeout=3)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            og_img = soup.find("meta", property="og:image")
            if og_img and og_img.get("content"):
                image_url = og_img.get("content").strip()
    except Exception:
        pass  # Erreur ignorée silencieusement pour plus de robustesse

    return domain, image_url

def get_country_badge(url):
    """Identifie le pays d'origine d'un article à partir de son URL."""
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        
        # Plateformes et sites connus
        if "leboncoin" in netloc or "oscaro" in netloc or "opisto" in netloc:
            if netloc.endswith(".fr"):
                return "🇫🇷 France"
            return "🇪🇺 Europe"
        elif "ovoko" in netloc or "rrr.lt" in netloc:
            if netloc.endswith(".fr"):
                return "🇫🇷 France"
            elif netloc.endswith(".lt") or ".lt/" in url:
                return "🇱🇹 Lituanie"
            return "🇪🇺 Europe"
        elif "allegro" in netloc:
            return "🇵🇱 Pologne"
        elif "b-parts" in netloc:
            return "🇪🇺 Europe"
        elif "mister-auto" in netloc or "auto-doc" in netloc:
            if netloc.endswith(".fr"):
                return "🇫🇷 France"
            elif netloc.endswith(".pl"):
                return "🇵🇱 Pologne"
            elif netloc.endswith(".de"):
                return "🇩🇪 Allemagne"
            return "🇪🇺 Europe"
        elif "ebay" in netloc:
            if ".fr" in netloc:
                return "🇫🇷 France"
            elif ".de" in netloc:
                return "🇩🇪 Allemagne"
            elif ".pl" in netloc:
                return "🇵🇱 Pologne"
            elif ".co.uk" in netloc or ".uk" in netloc:
                return "🇬🇧 Royaume-Uni"
            elif ".it" in netloc:
                return "🇮🇹 Italie"
            elif ".es" in netloc:
                return "🇪🇸 Espagne"
            return "🇪🇺 Europe"
            
        # Par extension générale de domaine
        if netloc.endswith(".fr"):
            return "🇫🇷 France"
        elif netloc.endswith(".pl"):
            return "🇵🇱 Pologne"
        elif netloc.endswith(".de"):
            return "🇩🇪 Allemagne"
        elif netloc.endswith(".lt"):
            return "🇱🇹 Lituanie"
        elif netloc.endswith(".co.uk") or netloc.endswith(".uk"):
            return "🇬🇧 Royaume-Uni"
        elif netloc.endswith(".it"):
            return "🇮🇹 Italie"
        elif netloc.endswith(".es"):
            return "🇪🇸 Espagne"
        elif netloc.endswith(".be"):
            return "🇧🇪 Belgique"
        elif netloc.endswith(".nl"):
            return "🇳🇱 Pays-Bas"
        elif netloc.endswith(".ch"):
            return "🇨🇭 Suisse"
    except Exception:
        pass
    return "🌐 International"

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

class SurveillanceEngine:
    def __init__(self):
        self.running = False
        self.thread = None
        self.log_callback = None

    def start(self, log_callback):
        """Démarre la boucle de surveillance dans un thread séparé."""
        if self.running:
            return
            
        self.running = True
        self.log_callback = log_callback
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        self._log("Moteur de surveillance démarré.")

    def stop(self):
        """Arrête proprement le moteur de surveillance."""
        if not self.running:
            return
            
        self.running = False
        self._log("Arrêt du moteur de surveillance demandé...")
        # Le thread s'arrêtera à sa prochaine vérification
        self.thread = None

    def _log(self, message):
        """Envoie un log à la console et à l'interface graphique."""
        timestamp = time.strftime("%H:%M:%S")
        formatted_msg = f"[{timestamp}] {message}"
        print(formatted_msg)
        if self.log_callback:
            self.log_callback(formatted_msg)

    def _load_config(self):
        """Charge la configuration la plus récente."""
        try:
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            self._log(f"Erreur de lecture config: {e}")
        return {"references": [], "ntfy_url": ""}

    def _passes_filters(self, item, filters, country):
        """
        Vérifie si un article passe les filtres de résultats configurés.
        Retourne (True, "") si l'article passe, ou (False, "raison") sinon.
        """
        if not filters:
            return True, ""

        title = item.get("title", "")
        snippet = item.get("snippet", "")
        price_str = item.get("price", "N/D")
        combined_text = f"{title} {snippet}".lower()

        # --- Filtre par prix ---
        price_min = filters.get("price_min") or 0
        price_max = filters.get("price_max") or 0
        if price_min > 0 or price_max > 0:
            price_val = _parse_price_value(price_str)
            if price_val is not None:
                if price_min > 0 and price_val < price_min:
                    return False, f"Prix {price_val:.0f}€ < minimum {price_min:.0f}€"
                if price_max > 0 and price_val > price_max:
                    return False, f"Prix {price_val:.0f}€ > maximum {price_max:.0f}€"

        # --- Filtre stock (exclure les articles explicitement hors stock) ---
        if filters.get("stock_only", False):
            if any(kw in combined_text for kw in STOCK_OUT_KEYWORDS):
                return False, "Article signalé hors stock"

        # --- Filtre par pays ---
        allowed_countries = filters.get("allowed_countries", [])
        if allowed_countries and country:
            country_lower = country.lower()
            if not any(ac.lower() in country_lower for ac in allowed_countries):
                return False, f"Pays '{country}' non autorisé"

        return True, ""

    def _build_precise_query(self, ref, targets):
        """Construit une requête de recherche ciblée (pointue)."""
        if not targets or targets.get("all_web", False):
            return ref
            
        site_operators = []
        for site, active in targets.items():
            if site != "all_web" and active:
                if site == "ovoko.fr":
                    site_operators.append("site:ovoko.fr OR site:ovoko.com OR site:rrr.lt")
                elif site == "opisto.fr":
                    site_operators.append("site:opisto.fr OR site:opisto.com")
                else:
                    site_operators.append(f"site:{site}")
                
        if not site_operators:
            return ref  # Recherche globale par défaut si aucun site n'est sélectionné
            
        sites_str = " OR ".join(site_operators)
        return f"{ref} ({sites_str})"

    def _run_loop(self):
        """Boucle d'exécution du thread d'arrière-plan."""
        while self.running:
            config = self._load_config()
            references = config.get("references", [])
            ntfy_url = config.get("ntfy_url", "")

            if not references:
                self._log("Aucune pièce dans la liste de surveillance. En attente...")
                self._sleep_responsive(15)
                continue

            self._log(f"Début du cycle de scan pour {len(references)} référence(s)...")

            for ref in references:
                if not self.running:
                    break

                targets = config.get("search_targets", {})
                search_query = self._build_precise_query(ref, targets)
                
                if search_query != ref:
                    self._log(f"Recherche web (ciblée) : '{search_query}'...")
                else:
                    self._log(f"Recherche web globale pour : '{ref}'...")
                    
                results = scanner.search_duckduckgo(search_query)
                
                if not results:
                    self._log(f"Aucun résultat trouvé pour : '{ref}'")
                    continue
                    
                self._log(f"Trouvé {len(results)} résultats potentiels pour : '{ref}'")
                
                new_items_count = 0
                for item in results:
                    if not self.running:
                        break

                    url = item["url"]
                    title = item["title"]
                    price = item["price"]

                    # Vérification double : URL exacte + titre normalisé/domaine
                    try:
                        parsed_domain = urlparse(url).netloc.replace("www.", "")
                    except Exception:
                        parsed_domain = ""

                    if database.item_exists(url, title=title, source_domain=parsed_domain):
                        continue

                    # Récupérer le pays en amont (nécessaire pour les filtres)
                    country = get_country_badge(url)

                    # Appliquer les filtres de résultats
                    result_filters = config.get("result_filters", {})
                    passes, reason = self._passes_filters(item, result_filters, country)
                    if not passes:
                        self._log(f"   [FILTRÉ] '{title[:50]}' → {reason}")
                        continue

                    new_items_count += 1
                    self._log(f"Analyse IA de l'article : '{title}' (Prix: {price})...")
                    
                    # Validation IA via Ollama qwen2.5-coder:7b (pre-filtre + prompt strict)
                    is_part = ai_filter.is_mechanical_part(title, ref, url=url)
                    
                    if is_part:
                        self._log(f"-> [VALIDÉ par l'IA] C'est bien une pièce mécanique !")
                        
                        # Extraire le pays d'origine (déjà récupéré avant filtres)
                        self._log(f"   Pays d'origine : {country}")
                        
                        # Traduire le titre en français si nécessaire via l'Ollama local
                        self._log("   Traduction du titre via l'IA locale...")
                        translated_title = ai_filter.translate_to_french(title)
                        if translated_title != title:
                            self._log(f"   Titre traduit : '{translated_title}'")
                        else:
                            translated_title = None

                        # Extraction de l'image et du domaine source
                        domain, image_url = extract_og_metadata(url)
                        # S'assurer que domain est coherent avec parsed_domain
                        if not domain:
                            domain = parsed_domain
                        self._log(f"   Source : {domain} | Apercu Image : {image_url is not None}")
                        
                        # Enregistrer en BDD avec image, domaine, pays et traduction
                        database.add_item(
                            reference=ref, 
                            title=title, 
                            url=url, 
                            price=price, 
                            is_part=1, 
                            image_url=image_url, 
                            source_domain=domain,
                            country=country,
                            translated_title=translated_title
                        )
                        
                        # Envoyer la notification ntfy (une seule fois par annonce)
                        # On verifie avec LES DEUX cles possibles (url + title/domain)
                        if ntfy_url:
                            already_notified = database.has_been_notified(
                                url, title=title, source_domain=domain
                            )
                            if not already_notified:
                                notifier.send_notification(
                                    ntfy_url,
                                    ref,
                                    title,
                                    price,
                                    url,
                                    country=country,
                                    translated_title=translated_title
                                )
                                # Marquer immediatement AVANT le prochain cycle
                                database.mark_as_notified(url)
                                self._log("---> Notification ntfy envoyee.")
                            else:
                                self._log("---> Notification deja envoyee pour cette annonce, ignoree.")
                        else:
                            self._log("---> Alerte non envoyee (lien ntfy non configure)")
                    else:
                        self._log(f"-> [REJETE] Pas une annonce de vente de piece detachee.")
                        # country est deja calcule avant les filtres (pas de double appel)
                        database.add_item(ref, title, url, price, is_part=0, source_domain=parsed_domain, country=country)

                    # Pause courte entre les analyses pour éviter de saturer Ollama
                    self._sleep_responsive(2)

                self._log(f"Scan de '{ref}' terminé. ({new_items_count} nouveau(x) traité(s))")
                # Petite pause entre les requêtes de recherche
                self._sleep_responsive(5)

            if self.running:
                self._log("Cycle de scan complet terminé. Prochain scan dans 60 secondes...")
                self._sleep_responsive(60)

        self._log("Moteur de surveillance arrêté.")

    def _sleep_responsive(self, seconds):
        """Dort pendant un certain nombre de secondes tout en restant réactif à l'arrêt."""
        for _ in range(int(seconds)):
            if not self.running:
                break
            time.sleep(1)
            
# Instance globale utilisable
engine = SurveillanceEngine()
