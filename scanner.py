import re
import random
import requests
from urllib.parse import urlparse, quote
from bs4 import BeautifulSoup

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15"
]

def _extract_price(text):
    """Extrait heuristiquement un prix depuis un texte."""
    match = re.search(r'(\d+[\s,\.]?\d*)\s*(?:€|EUR|\$|PLN|zł)', text, re.IGNORECASE)
    if match:
        return match.group(0).strip()
    return "N/D"

def search_duckduckgo(query):
    """
    Point d'entrée principal du scanner.
    Essaie d'abord via la bibliothèque DDGS (DuckDuckGo),
    puis bascule sur Bing en fallback si aucun résultat.
    Retourne une liste de dict : [{'title': str, 'url': str, 'price': str}]
    """
    results = _search_via_ddgs(query)

    if not results:
        print(f"[Scanner] DDGS sans résultat, tentative via Bing...")
        results = _search_via_bing(query)

    if not results:
        print(f"[Scanner] Aucun résultat trouvé via tous les moteurs pour : '{query}'")

    return results


def _search_via_ddgs(query):
    """
    Utilise la bibliothèque 'ddgs' (anciennement duckduckgo-search).
    Gère les challenges anti-bots nativement via primp.
    """
    try:
        # Support des deux noms de paquet (ancien et nouveau)
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS

        results = []
        with DDGS() as ddgs:
            # On met la requête entre guillemets pour forcer la recherche exacte
            # et on cible la région française
            raw = list(ddgs.text(
                f'"{query}"',
                max_results=20,
                region="fr-fr",
                safesearch="off"
            ))

        for r in raw:
            title = r.get("title", "").strip()
            url = r.get("href", "").strip()
            snippet = r.get("body", "").strip()
            price = _extract_price(f"{title} {snippet}")

            if title and url and url.startswith("http"):
                results.append({"title": title, "url": url, "price": price, "snippet": snippet})

        return results

    except Exception as e:
        print(f"[Scanner] Erreur DDGS: {e}")
        return []


def _search_via_bing(query):
    """
    Fallback : scraping Bing HTML (très stable, pas de JS challenge).
    La requête est mise entre guillemets pour une recherche exacte.
    """
    try:
        # Requête entre guillemets pour forcer l'exact match
        encoded_query = quote(f'"{query}"')
        url = f"https://www.bing.com/search?q={encoded_query}&count=20&setlang=fr&cc=FR&mkt=fr-FR"

        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "fr,fr-FR;q=0.9,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }

        # stream=True + lecture limitée à 1 Mo pour éviter une saturation RAM
        MAX_RESPONSE_BYTES = 1_000_000  # 1 Mo
        response = requests.get(url, headers=headers, timeout=15, stream=True)
        if response.status_code != 200:
            print(f"[Scanner] Bing a retourné HTTP {response.status_code}")
            response.close()
            return []

        raw_content = response.raw.read(MAX_RESPONSE_BYTES, decode_content=True)
        response.close()
        soup = BeautifulSoup(raw_content, "html.parser")
        results = []

        for li in soup.select("li.b_algo"):
            title_tag = li.find("h2")
            if not title_tag:
                continue
            link_tag = title_tag.find("a")
            if not link_tag:
                continue

            title = link_tag.get_text(strip=True)
            href = link_tag.get("href", "")
            if not href.startswith("http"):
                continue

            snippet_tag = li.find("p")
            snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""
            price = _extract_price(f"{title} {snippet}")

            results.append({"title": title, "url": href, "price": price, "snippet": snippet})

        print(f"[Scanner] Bing a retourné {len(results)} résultats.")
        return results

    except Exception as e:
        print(f"[Scanner] Erreur Bing fallback: {e}")
        return []
