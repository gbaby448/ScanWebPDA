# ScanWebPDA

## Description

ScanWebPDA est un assistant conçu pour automatiser la recherche d'annonces auto en utilisant diverses sources, incluant Opisto, Ovoko, B-Parts Allegro et d'autres sites web. Il permet de paramétrer la fréquence de recherche, gérer le multilingue de l'IA, utiliser des proxies/user-agent pour éviter les limites, améliorer la performance du scraper DuckDuckGo, ajouter des fonctionnalités à une interface utilisateur personnalisée et sauvegarder automatiquement les données dans un service de stockage cloud.

## Comment utiliser ScanWebPDA

### Installation

1. Clonez le dépôt :
   ```bash
   git clone https://github.com/votre-nom-de-repo/scanwebpda.git
   cd scanwebpda
   ```

2. Installez les dépendances :
   ```bash
   pip install -r requirements.txt
   ```

3. Configurez le fichier `config.json` avec les paramètres appropriés.

### Configuration

Le fichier `config.json` doit être configuré comme suit :

```json
{
  "frequency": "5m",  // Fréquence de recherche (ex: 5m, 1h)
  "multilingual_support": true,
  "proxy_rotation": true
}
```

### Lancement

Lancez le script principal :
```bash
python main.py
```

## Assistant en Tutoiement

ScanWebPDA s'adresse en tutoiement pour une interaction plus personnalisée et conviviale.

## Mémoire Persistante

Le assistant a une mémoire persistante qui permet de garder les informations entre les sessions. Cela facilite le suivi des recherches, des statistiques et d'autres données importantes.

---

**TODO List** :
- [ ] Paramétrage de la fréquence de scan
- [ ] Gestion multilingue de l'IA
- [ ] Rotation de proxies/user-agent
- [ ] Amélioration de la performance du scraper DuckDuckGo
- [ ] Ajout de fonctionnalités à l'interface utilisateur
- [ ] Intégration avec des services de stockage cloud