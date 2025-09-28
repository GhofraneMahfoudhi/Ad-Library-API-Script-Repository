# README — Ad-Library-API-Script-Repository

Résumé
- Projet Python pour collecter des annonces depuis la Facebook Ads Library (UI publique et endpoint async).
- Entrée principale : `python/fb_ads_library_public.py`
- Deux modes de collecte : requêtes "async" automatisées (rapide) et fetch via navigateur headless (Playwright) pour capturer les XHR / DOM rendu.
- Résultats peuvent être sauvegardés en CSV via l'opérateur `save_to_csv`.

Prérequis
- Python 3.8+
- pip
- Dépendances Python (installer dans le repo) :
  - requests
  - playwright (optionnel, nécessaire si `--use-public-fetch` est utilisé)
- Pour Playwright (si utilisé) :
  - pip install playwright
  - playwright install

Fichiers principaux (emplacement : python/)
- fb_ads_library_public.py
  - CLI principal. Parse les arguments, construit `FbAdsLibraryTraversal`, choisit la méthode de fetch, exécute l'action (ex : save_to_csv).
- fb_ads_library_api.py
  - Contient `FbAdsLibraryTraversal` : logique de génération/itération des résultats d'annonces.
  - Méthodes importantes (exemples observés dans le code et la conversation) :
    - __init__(search_term, country, retry_limit=..., ...): initialise la traversal.
    - get_public_search_url(): retourne l'URL publique (ex. `https://www.facebook.com/ads/library/?...q=...&search_type=keyword_unordered`).
    - generate_ad_archives(): generator qui utilise l'endpoint async (`/ads/library/async/search_ads/`) pour obtenir JSON par batch.
    - generate_ad_archives_from_public_page(): generator qui utilise Playwright (headless) pour charger la page publique, capturer XHR JSON ; si aucun XHR JSON n'est trouvé, fallback DOM scraping pour extraire des éléments d'annonce.
    - _get_ad_archives_from_url(...): fonction interne qui effectue la requête HTTP/XHR (utilise headers navigateur, retries/backoff).
    - default_url_pattern / public_url_pattern : formats pour construire les URLs.
- fb_ads_library_api_operators.py
  - get_operators(): retourne le dictionnaire d'actions (ex. `save_to_csv`).
  - save_to_csv(generator, args, fields, is_verbose=False): consomme le generator et écrit un CSV avec les champs demandés. Note : `--fields` est requis pour `save_to_csv`.
- fb_ads_library_api_utils.py
  - get_country_code(x): normalise/valide codes pays.
  - is_valid_fields(x): valide si un champ est supporté.
  - Autres utilitaires de validation et parsing.

Rôle des fonctions (détail)
- get_parser() (fb_ads_library_public.py)
  - Construit l'ArgumentParser avec options :
    - -s / --search-term : terme de recherche (ex. "medicure.tn")
    - -c / --country : code(s) pays (ex. "TN"), required
    - --search-page-ids : rechercher par page id(s)
    - --retry-limit : nombre d'essais sur erreurs répétées
    - -v / --verbose : verbose logging
    - action (positionnel, optionnel si --print-public-url/--open-public-url) : nom de l'opération (ex. save_to_csv)
    - args (positionnel, argparse.REMAINDER) : paramètres pour l'action (ex. output filename)
    - -f / --fields : liste de champs comma-separated (requise pour save_to_csv)
    - --print-public-url / --open-public-url : afficher / ouvrir l'URL publique et exit
    - --use-public-fetch : utiliser Playwright pour récupérer les données depuis la page publique
- main() (fb_ads_library_public.py)
  - Valide présence de `--search-term` ou `--search-page-ids`.
  - Crée `FbAdsLibraryTraversal(search_term, opts.country)`.
  - Si `--print-public-url` / `--open-public-url` : affiche/ouvre `get_public_search_url()` et exit.
  - Sinon exige `action`.
  - Choisit generator : `generate_ad_archives_from_public_page()` si `--use-public-fetch`, sinon `generate_ad_archives()`.
  - Appelle l'opérateur correspondant (ex. save_to_csv).
- FbAdsLibraryTraversal.generate_ad_archives()
  - Itérateur qui effectue des requêtes vers l'endpoint async pour obtenir batches JSON.
  - Utilise headers (User-Agent, Referer), retries et backoff pour augmenter chance de succès.
  - Peut renvoyer erreurs de décodage JSON si la réponse n'est pas JSON (cas fréquent si serveur bloque).
- FbAdsLibraryTraversal.generate_ad_archives_from_public_page()
  - Lance Playwright headless, charge l'URL publique, écoute les réponses réseau XHR, capture celles contenant JSON d'annonces.
  - Fallback DOM scraping si aucun XHR JSON n'est capturé : parse le HTML rendu pour extraire liens/éléments d'annonce visibles.
  - Yield des batches de dictionnaires compatibles avec les opérateurs.
- save_to_csv(generator, args, fields, is_verbose=False)
  - Consomme le generator ; écrit le header CSV avec les champs demandés.
  - Pour chaque item, écrit une ligne CSV.
  - Si CSV vide (seulement header), cela signifie que le generator n'a retourné aucun item.

Exemples d'utilisation (PowerShell)
- Afficher l'URL publique (vérificationdans navigateur) :
  ```powershell
  python python\fb_ads_library_public.py -s "medicure.tn" -c "TN" --print-public-url
  ```
- Ouvrir l'URL publique dans le navigateur par défaut :
  ```powershell
  python python\fb_ads_library_public.py -s "medicure.tn" -c "TN" --open-public-url
  ```
- Collecte avec endpoint async (rapide) et sauvegarde CSV :
  - Champs requis : vérifiez `fb_ads_library_api_utils.is_valid_fields` pour la liste exacte.
  ```powershell
  python python\fb_ads_library_public.py -s "medicure.tn" -c "TN" -f "page_name,ad_snapshot_url" save_to_csv output.csv
  ```
- Collecte via le fetch public (Playwright — plus fiable si async renvoie HTML) :
  ```powershell
  pip install playwright
  playwright install
  python python\fb_ads_library_public.py -s "medicure.tn" -c "TN" -f "page_name,ad_snapshot_url" --use-public-fetch save_to_csv output.csv
  ```

Dépannage fréquent
- CSV généré mais vide (header seulement)
  - Cause probable : le generator n'a retourné aucun item.
  - Actions :
    1. Relancer avec `-v` / `--verbose` pour voir logs et erreurs.
    2. Si vous avez `Failed to decode JSON from ...` : utilisez `--use-public-fetch` (Playwright) ou vérifiez que vos headers/referer sont appliqués.
    3. Vérifiez que `-f` (fields) contient au moins un champ valide ; `save_to_csv` nécessite `--fields`.
    4. Inspectez la sortie console pour les messages de fallback DOM (le script peut logguer le nombre d'items extraits).
- Erreur JSON decode sur endpoint async
  - Facebook peut retourner HTML (page de blocage, login) à l'endpoint async. Solutions :
    - Utiliser `--use-public-fetch` (headless browser) pour reproduire les XHR de l'UI.
    - Ajouter/revoir headers (User-Agent, Referer) ou augmenter retry/backoff.
- Playwright non installé mais `--use-public-fetch` utilisé
  - Script lèvera RuntimeError avec instructions d'installation.
  - Installer : `pip install playwright` puis `playwright install`.

Sécurité et légalité
- Vérifier les conditions d'utilisation de Facebook avant d'automatiser la collecte.
- Respecter la charge sur les serveurs (respecter rate-limits, backoff).
- Si vous collectez à grande échelle, gérer les quotas et la conformité légale.

Extension et développement
- Ajouter extraction de champs supplémentaires :
  - Vérifier/étendre `is_valid_fields` dans `fb_ads_library_api_utils.py`.
  - Adapter `generate_ad_archives_from_public_page()` pour extraire ces champs soit depuis XHR JSON, soit depuis le DOM rendu.
- Améliorer robustesse fetch async :
  - Capturer cookies de session si nécessaire.
  - Reproduire exactement les headers XHR observés dans le devtools réseau de la page UI.
- Tests unitaires :
  - Ajouter tests pour fonctions utilitaires (country code, validation fields).
  - Simuler generator en unit test avec fixtures JSON pour `save_to_csv`.

Que fournir pour aide supplémentaire
- La commande exacte utilisée et la sortie console (logs/errors).
- Extrait de la réponse renvoyée (lorsque script affiche un fragment de HTML/JSON) pour diagnostiquer.
- Contenu d’un exemple CSV vide (pour confirmer header et fields utilisés).

Notes pratiques rapides
- Le script principal est `python\fb_ads_library_public.py`.
- Toujours exécuter en fournissant `-c` (country) ; la validation normalize les codes.
- Pour voir les actions disponibles (opérateurs) : ouvrir `fb_ads_library_api_operators.py` et appeler `get_operators()`.

Licence
- Conserver la licence fournie dans le dépôt (fichier LICENSE à la racine).

Support
- Si vous voulez que j'ajoute :
  - un README.md fichier dans le repo (avec ce contenu),  
  - un petit script de debug pour afficher les XHR capturés par Playwright,  
  - ou un exemple complet d'extraction + mapping des champs — dites lequel, je l'ajoute.
