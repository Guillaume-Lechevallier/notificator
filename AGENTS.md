# Instructions pour les agents

- L'application est composée d'un backend FastAPI (dossier `backend/`) et d'un frontend statique (dossier `frontend/`).
- Les notifications sont des Web Push (titre + corps + image + lien optionnels) gérés via service worker (`frontend/sw.js`).
- La base de données cible est MySQL ; utilisez la variable d'environnement `DATABASE_URL` (format `mysql+mysqlconnector://user:pass@host:port/db`).
- Renseignez les clés VAPID (`VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_CLAIM_EMAIL`) avant d'appeler `/api/config` ou d'envoyer des notifications.
- Si le schéma SQL change, déplacez l'ancien contenu de `last_update.sql` dans `last_update_old.sql` et écrivez le nouveau SQL dans `last_update.sql`.
- Ne générez pas de fichiers binaires ; privilégiez les assets statiques (HTML/CSS/JS).
- Pour vérifier rapidement le code sans MySQL local, le backend accepte aussi SQLite si `DATABASE_URL` pointe vers `sqlite:///...`.
- Le frontend est servi par FastAPI via `StaticFiles`. Les pages principales : `index.html` (inscription) et `admin.html` (envoi des notifications).
- L'accès à `admin.html` est désormais protégé par une authentification HTTP Basic (variables d'environnement `ADMIN_USERNAME` / `ADMIN_PASSWORD`, valeurs par défaut `admin` / `changeme`).
- Commande de démarrage locale : `uvicorn backend.main:app --host 0.0.0.0 --port 8000` après avoir installé les dépendances (`pip install -r requirements.txt`).
- La pile Docker est définie par `docker-compose.yml` (services `db` et `app`).
- Si l'API retourne `Unknown column 'click_url' in 'field list'`, exécuter le script `last_update.sql` (nouvelle colonne `click_url` dans `notifications`) après avoir archivé l'ancien fichier dans `last_update_old.sql`.
- Si l'API retourne `Unknown column 'subscribers.label' in 'field list'`, exécuter le script `last_update.sql` pour aligner la table `subscribers` (colonne `label` + champs Web Push) après avoir archivé la version précédente dans `last_update_old.sql`.
- Les commerces sont gérés via `/api/businesses` (nom, gérant, contact, adresse, abonné optionnel). Utiliser le champ `subscriber_id` pour lier un commerce à un abonné et permettre les envois ciblés (`business_id` dans `/api/notifications`).
- Mise à jour schéma 2025-11-25 : table `businesses` + colonne `business_id` sur `notifications`. Exécuter `last_update.sql` sur les bases existantes après avoir archivé l'ancienne version dans `last_update_old.sql`.
- Mise à jour schéma 2025-11-27 : les instructions d'alignement MySQL sont désormais séparées (une colonne/contrainte/index par `ALTER TABLE` ou `DROP/ADD`) pour éviter l'erreur de syntaxe `ADD COLUMN IF NOT EXISTS` observée au démarrage. Si vous voyez cette erreur, déplacez l'ancien `last_update.sql` vers `last_update_old.sql` puis rejouez le nouveau script.
- Mise à jour schéma 2025-11-27 (correctif) : `last_update.sql` utilise maintenant des blocs préparés (`SET @sql := IF(...); PREPARE stmt FROM @sql; EXECUTE stmt;`) pour vérifier l'existence des colonnes/index/contraintes avant d'exécuter chaque `ALTER TABLE`. Cette version est compatible MySQL 8.0 sans utiliser `ADD COLUMN IF NOT EXISTS` et reste idempotente.
- Le lien d'inscription dédié à un commerce se génère depuis `admin.html` (bouton « Générer un lien d'enrôlement »). Le lien redirige vers `index.html?business_id=...&business_name=...` et `/api/subscribers` associe automatiquement l'abonné au commerce via `business_id`.
- Si aucune clé VAPID n'est fournie via les variables d'environnement, l'API en génère une paire de développement et la stocke dans `backend/.vapid_keys.json` (ignoré par git). Fournir vos propres clés en production pour éviter de régénérer les abonnements.
- Les clés VAPID de développement sont préremplies dans `docker-compose.yml` avec l'email `mailto:moilechevallier@gmail.com`. Mettez-les à jour si vous remplacez la paire ou si vous voulez tester avec d'autres identifiants.
- Depuis py_vapid 1.9, `b64urlencode` renvoie directement une chaîne : ne pas appeler `.decode()` sur le résultat sous peine d'erreur `AttributeError: 'str' object has no attribute 'decode'`. Utiliser un helper qui gère `str` ou `bytes`.
- Au démarrage, l'API applique automatiquement le script `last_update.sql` sur les bases MySQL (idempotent) afin de garantir la présence des colonnes Web Push (`subscribers.label`, `click_url`, etc.). Ne modifiez pas ce comportement : mettez plutôt à jour le contenu du script si le schéma évolue.
- Si l'ajout de l'index `uq_subscriber_endpoint` échoue avec `Duplicate entry '' for key 'subscribers.uq_subscriber_endpoint'`, rejouez la version 2025-11-28 de `last_update.sql` qui supprime les endpoints vides et déduplique les abonnés avant de recréer l'index.
- Si l'erreur `Field 'target_url' doesn't have a default value` apparaît lors de l'envoi d'une notification, appliquez la version 2025-11-29 de `last_update.sql` : elle rend `target_url` facultative, copie ses données vers `click_url` puis supprime la colonne obsolète.
- Sur pywebpush 2.0 et versions ultérieures, l'appel `webpush` n'accepte plus le paramètre `vapid_public_key`. Utilisez uniquement `vapid_private_key` et `vapid_claims` pour éviter l'exception `TypeError: webpush() got an unexpected keyword argument 'vapid_public_key'`.
- Mise à jour 2025-11-30 : `subscribers.endpoint` n'est plus unique afin d'autoriser plusieurs inscriptions pour un même navigateur (ex. plusieurs liens d'enrôlement). Le script `last_update.sql` supprime l'index unique et crée un index non unique `idx_subscriber_endpoint`.
- L'URL d'inscription (`index.html?business_id=...`) redirige désormais automatiquement les visiteurs déjà enrôlés vers la dernière notification du commerce via `GET /api/businesses/{id}/notifications/latest`. Préservez ce point d'entrée et le calcul de l'URL de fallback (`notification.html?image=...&title=...&body=...`) en cas de modification.
- L'upload d'images passe par `POST /api/uploads` (stockage dans `frontend/uploads/`). Le formulaire admin remplit automatiquement l'URL de l'image après téléversement ; éviter les hotlinks externes.
- L'endpoint `POST /api/notifications` renvoie désormais un récapitulatif d'envoi (destinataires traités, succès/échecs) pour alimenter l'UI admin.
- Si aucun paramètre `image` n'est fourni ou que le fichier ciblé est invalide, la landing `notification.html` doit demander l'URL la plus récente via `/api/uploads/latest` avant d'utiliser un dégradé par défaut.
- L'interface admin propose un thème clair/sombre (persisté via `localStorage`) partagé avec `notification.html`. Ne supprimez pas le sélecteur et privilégiez les variables CSS pour ajuster les couleurs.
- L'interface admin propose un thème clair/sombre (persisté via `localStorage`) partagé avec `notification.html`. Ne supprimez pas le sélecteur et privilégiez les variables CSS pour ajuster les couleurs. La landing `notification.html` reste toutefois en mode unique (fond image sans overlay, carte en bas, boutons côte à côte) conformément au dernier besoin utilisateur : ne réintroduisez pas de toggle de thème sur cette page.
- Les liens de destination sont construits vers `notification.html` avec les paramètres `image`, `title`, `body` et, si les cases sont cochées côté administration, `call` (tel:...) et `address` (Google Maps itinéraire).
- 2026-01-02 : l'admin propose un QR code SVG pour le lien d'inscription (bouton « QR (SVG) »). Le SVG est généré via l'endpoint `/api/qrcodes/enrollment` (librairie Python `segno`). Préservez le téléchargement et l'aperçu côté admin lorsque vous touchez à cette zone.
- 2026-12-05 : pour éviter l'erreur de génération du QR code (`TypeError` selon les versions de `segno`), capturez le SVG dans un buffer binaire (`io.BytesIO`) puis décoder en UTF-8 avant de répondre. Cette approche reste compatible avec les sorties bytes/bytearray de `segno`.

- 2025-12-10 : la largeur du panneau admin est plafonnée à `min(1080px, calc(100vw - 36px))` avec une grille plus étroite pour éviter tout débordement horizontal. Préservez cette limite lors des ajustements UI.

- 2025-12-14 : pour éviter les débordements liés aux champs (URL longues, coordonnées détaillées), gardez le wrapping forcé sur les cartes, badges, listes, historiques et sur les conteneurs flex/grille (min-width: 0 + overflow-wrap:anywhere).

- 2025-12-04 : Refonte front complète (admin/index/notification). Conserver les identifiants de formulaire/sections afin de garder la compatibilité avec le JS inline et les routes existantes.
- Prévisualisation rapide sans MySQL : `DATABASE_URL=sqlite:///./dev.db uvicorn backend.main:app --host 0.0.0.0 --port 8000` (le script `last_update.sql` est ignoré en SQLite, utile pour les captures d'écran front).
- Les pages admin/index partagent le même thème clair/sombre (clé `notificator-theme`) : toute évolution UI doit continuer à synchroniser ce stockage local avec `notification.html`.
- 2025-12-05 : Le front admin/index utilise désormais une largeur fluide (`min(..., calc(100vw - 32px))`) pour éviter tout contenu rogné sur les petits écrans. Ne réintroduisez pas de valeurs fixes > viewport sans garde-fous (minmax + media queries).
- 2025-12-06 : Le lien d'inscription affiche une étape Oui/Non (« Accepter les notifications de votre commerçant ? ») et mémorise l'acceptation dans le `localStorage` (`notificator-accepted-businesses`, `notificator-accepted-pages`, `notificator-last-business`). Préserver cette mémorisation pour éviter de redemander l'autorisation sur un appareil déjà validé.
- 2025-12-18 : le texte d'enrôlement est géré via la table `settings` (clé `enrollment_prompt`) et l'endpoint `/api/settings/enrollment_prompt`. La page `index.html` se limite à cette question avec deux boutons : Oui déclenche l'inscription Web Push, Non redirige vers google.com.
- 2025-12-19 : `last_update.sql` insère désormais le paramètre `enrollment_prompt` via un `INSERT ... WHERE NOT EXISTS` (idempotent, sans SQL dynamique) pour éviter les erreurs MySQL au démarrage. Rejouez le script si le message d'enrôlement manque dans la table `settings`.

## Note de déploiement (2025-12-21)

- Le `readme.md` documente désormais une démo pas-à-pas de déploiement via Docker Compose (MySQL + backend + frontend). Gardez ce walkthrough en phase avec `docker-compose.yml` (ports, variables VAPID, commande `docker compose logs -f app`).
- Un script `deploy.sh` automatise l'installation sur Ubuntu (Apache + Certbot + MySQL + systemd + synchronisation du dépôt dans `/opt/notificator`). Mettez-le à jour en même temps que les instructions du `readme.md` et vérifiez qu'il reste idempotent.
- Le script `deploy.sh` stoppe les conteneurs Docker en cours (via `docker compose down` + `docker stop`) avant de continuer l'installation pour éviter les conflits de ports.
- Si `deploy.sh` s'arrête sur une erreur `dpkg returned an error code (1)` lors de l'installation des paquets, lancer `dpkg --configure -a && apt-get -f install` puis relancer le script. Cette réparation est désormais tentée automatiquement avant l'arrêt.
- Pour tester rapidement le front/back après une modification, lancez `DATABASE_URL=sqlite:///./dev.db uvicorn backend.main:app --host 0.0.0.0 --port 8000` depuis la racine : le frontend statique est servi par FastAPI. Les captures d'écran peuvent être faites à partir de `http://localhost:8000/index.html`.
