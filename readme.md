# Notificator

Application de notifications Web Push avec un backend Python (FastAPI), un frontend statique et une base MySQL. L'interface d'administration envoie des messages courts à tous les abonnés (titre, contenu optionnel, image et lien d'ouverture). Les utilisateurs s'inscrivent via le lien d'inscription : un service worker affiche la notification même si l'onglet est fermé.

## Aperçu des dossiers

- `backend/` : API FastAPI, modèles SQLAlchemy et configuration de la base de données.
- `frontend/` : pages statiques (inscription et administration).
- `admin.html` propose désormais une gestion des commerces (fiche détaillée + envoi ciblé).
- Le formulaire d'envoi accepte des images téléversées localement : elles sont hébergées dans `frontend/uploads/` via `POST
  /api/uploads`.
- `last_update.sql` : script SQL à exécuter sur MySQL pour provisionner les tables (Web Push, abonnés, notifications, livraisons).
- `docker-compose.yml` : lance MySQL et l'API sur le port 8000.

## Prérequis

- Docker et Docker Compose (recommandé pour MySQL)
- Python 3.11+ si vous exécutez l'API sans Docker

## Démarrage rapide avec Docker

```bash
docker compose up --build
```

> Lors du démarrage, l'API applique automatiquement le contenu de `last_update.sql` sur MySQL pour aligner le schéma (colonnes Web Push, `label`, commerces, etc.). Le fichier est idempotent : il peut être exécuté plusieurs fois et garantit que la base correspond aux modèles actuels.

L'API est disponible sur `http://localhost:8000` et sert aussi le frontend :

- `http://localhost:8000/index.html` : inscription / réception
- `http://localhost:8000/admin.html` : panneau d'administration

### Clés VAPID préconfigurées (développement)

Pour faciliter les tests, le fichier `docker-compose.yml` définit déjà les variables
`VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` et `VAPID_CLAIM_EMAIL` avec une paire fournie :

```env
VAPID_PUBLIC_KEY=BFJYF7VW4vjhjTpt9PExNUNHC3Q4VCZ4rN9cvj15IFEK-wM2LoXHzHPja0miVp7EG6FQRyg_MGFMVFV5DAYJUL4
VAPID_PRIVATE_KEY=VBId-1ytbTzWMfpwNolBoEjZ5xUvwLUNIObyVBxxlBE
VAPID_CLAIM_EMAIL=mailto:moilechevallier@gmail.com
```

Elles sont utilisées par défaut au démarrage des conteneurs. Pour un déploiement en
production, remplacez-les par vos propres clés (génération recommandée via
`pywebpush` comme détaillé ci-dessous) afin de ne pas invalider les abonnements existants.

## Exécution locale sans Docker

1. Installez les dépendances :

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Assurez-vous d'avoir une base MySQL accessible, puis exportez l'URL de connexion :

```bash
export DATABASE_URL="mysql+mysqlconnector://notificator:notificator@localhost:3306/notificator"
```

3. Appliquez le schéma (à partir de `last_update.sql`) sur votre base.
4. Renseignez les clés VAPID (générées via `pywebpush`) :

```bash
python - <<'PY'
from cryptography.hazmat.primitives import serialization
from py_vapid import b64urlencode
from pywebpush import Vapid

vapid = Vapid()
vapid.generate_keys()

private_value = vapid.private_key.private_numbers().private_value
private_bytes = private_value.to_bytes(32, byteorder="big")
public_bytes = vapid.public_key.public_bytes(
    encoding=serialization.Encoding.X962,
    format=serialization.PublicFormat.UncompressedPoint,
)

def b64urlencode_text(data: bytes) -> str:
    encoded = b64urlencode(data)
    return encoded if isinstance(encoded, str) else encoded.decode()

print('VAPID_PRIVATE_KEY=', b64urlencode_text(private_bytes))
print('VAPID_PUBLIC_KEY=', b64urlencode_text(public_bytes))
PY

export VAPID_PUBLIC_KEY="<clé publique>"
export VAPID_PRIVATE_KEY="<clé privée>"
export VAPID_CLAIM_EMAIL="mailto:admin@example.com"
```

> À défaut de variables d'environnement, l'API génère automatiquement un jeu de clés de développement et le conserve dans
> `backend/.vapid_keys.json`. Définissez vos propres clés VAPID en production pour garantir la continuité des abonnements.

5. Lancez l'API :

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

6. Ouvrez `http://localhost:8000/admin.html` pour gérer vos commerces et envoyer des notifications (globales ou ciblées).
7. Ouvrez `http://localhost:8000/index.html` depuis un navigateur autorisant les notifications (HTTPS ou localhost).

### Lien d'enrôlement pour un commerce

- Depuis le panneau d'administration (`admin.html`), sélectionnez un commerce puis cliquez sur **« Générer un lien d'enrôlement »** dans le bloc *Informations enregistrées*.
- Le lien généré pointe vers `index.html` et inclut les paramètres `business_id` et `business_name` pour préremplir l'inscription et associer l'abonné au commerce.
- Partagez ce lien avec le gérant : dès qu'il valide les notifications, l'abonnement est relié au commerce et l'ID est mis à jour côté administration.

### Téléverser une image pour une notification

- Depuis `admin.html`, ajoutez une image via le champ « Image (téléversement recommandé) » : le fichier est envoyé en `POST` sur `/api/uploads` et l'URL relative est remplie automatiquement dans le champ « URL de l'image ».
- Les fichiers sont stockés dans `frontend/uploads/` et servis par FastAPI en statique (aucun hotlinking externe nécessaire).
- Si besoin, une URL d'image déjà en ligne peut toujours être saisie manuellement.

## Flux fonctionnel

1. Un utilisateur s'inscrit via la page `index.html` : le navigateur enregistre un abonnement Web Push et l'envoie à `/api/subscribers`.
2. L'administrateur remplit le formulaire (titre, contenu, image, lien) puis clique sur le bouton cloche pour envoyer la notification.
3. L'API crée une notification et une livraison pour chaque abonné, envoie le Web Push via pywebpush et marque la livraison comme livrée (ou failed en cas d'erreur réseau).
4. Le service worker (`/sw.js`) affiche la pop-up native. Au clic, l'utilisateur est redirigé vers le lien saisi ou vers `notification.html` (affichage image + lien) en fallback.

## API (résumé)

- `GET /api/config` : renvoie la clé publique VAPID pour s'abonner.
- `POST /api/subscribers` : enregistre un abonnement Web Push (payload `{ subscription, label?, user_agent?, business_id? }`). Le champ `business_id` associe automatiquement l'abonné au commerce ciblé.
- `GET /api/subscribers` : liste les abonnés (nom + token) pour l'aperçu admin.
- `GET /api/businesses` : liste les commerces et leurs coordonnées (nom, gérant, contact, adresse, abonné associé).
- `POST /api/businesses` : crée un commerce.
- `PUT /api/businesses/{id}` : met à jour un commerce existant.
- `GET /api/notifications` : liste les notifications envoyées.
- `POST /api/notifications` : crée une notification (payload `{ title, body?, image_url?, click_url?, business_id? }`). Si `business_id` est présent, l'envoi est limité à l'abonné du commerce.
- `GET /api/push/{device_token}` et endpoints associés restent disponibles pour compatibilité / suivi de livraisons.

## Base de données

Le schéma MySQL est décrit dans `last_update.sql`. Si le modèle évolue, déplacer l'ancien contenu dans `last_update_old.sql` et mettre le nouveau SQL dans `last_update.sql`.

L'API exécute automatiquement `last_update.sql` au démarrage pour les déploiements MySQL. Cette étape permet notamment d'ajouter la colonne `label` sur `subscribers` et de conserver les index d'unicité nécessaires pour éviter l'erreur `Unknown column 'subscribers.label' in 'field list'` lors de l'inscription. Si vous utilisez SQLite en développement, cette étape est ignorée pour rester compatible avec la syntaxe MySQL du script.

### Mise à jour 2025-11-25

- Ajout de la table `businesses` (nom, gérant, téléphone, email, adresse, abonné associé) pour stocker les commerces.
- Ajout de la colonne `business_id` sur la table `notifications` pour tracer les envois ciblés.
- Exécutez `last_update.sql` sur les bases existantes pour créer la table et la clé étrangère.

### Mise à jour 2025-11-26

- Ajout d'une migration de rattrapage pour la colonne optionnelle `label` de la table `subscribers` (nécessaire pour éviter l'erreur `Unknown column 'subscribers.label' in 'field list'` lors de l'inscription).
- Le script `last_update.sql` aligne désormais la table `subscribers` (colonnes Web Push et index d'unicité sur `endpoint`) en plus des colonnes `click_url` et `business_id`.
- Exécutez `last_update.sql` sur toute base créée avant cette date après avoir archivé l'ancienne version dans `last_update_old.sql`.

### Mise à jour 2025-11-27

- Réécriture des instructions d'alignement MySQL pour éviter l'erreur de syntaxe `ADD COLUMN IF NOT EXISTS` observée au démarrage du conteneur.
- Les ajouts de colonnes, d'index et de clés étrangères sont désormais appliqués via des blocs préparés (`SET @sql := IF(...); PREPARE stmt FROM @sql; EXECUTE stmt;`) qui vérifient l'existence de chaque élément avant d'exécuter l'ALTER.
- Si vous voyez une erreur `You have an error in your SQL syntax; check the manual that corresponds to your MySQL server version for the right syntax to use near 'IF NOT EXISTS label'`, rejouez `last_update.sql` après avoir archivé l'ancienne version dans `last_update_old.sql`.

### Mise à jour 2025-11-28

- Nettoyage automatique des abonnés corrompus avant de (ré)créer l'index unique `uq_subscriber_endpoint` afin d'éviter l'erreur MySQL `Duplicate entry '' for key 'subscribers.uq_subscriber_endpoint'` lors du démarrage.
- Les entrées avec un endpoint vide sont supprimées et les doublons sont dédupliqués en conservant le premier enregistrement avant d'ajouter l'index.
- Rejouez `last_update.sql` sur les bases existantes en cas d'échec de démarrage lié à cette erreur ; le script est idempotent et peut être exécuté plusieurs fois.

### Mise à jour 2025-11-29

- Le script gère désormais les bases MySQL historiques contenant encore une colonne obligatoire `target_url` sur `notifications`.
- Lors de l'alignement, la colonne est rendue facultative, ses valeurs sont copiées dans `click_url` si besoin puis la colonne obsolète est supprimée.
- Cette étape corrige l'erreur `Field 'target_url' doesn't have a default value` observée lors de l'envoi de notifications sur des bases non migrées.

### Mise à jour 2025-11-30

- L'unicité sur `subscribers.endpoint` est supprimée afin de permettre plusieurs inscriptions pour un même navigateur (plusieurs liens d'inscription / commerces). Un index non unique est conservé pour les recherches.
- `POST /api/subscribers` accepte désormais plusieurs enregistrements par endpoint : chaque commerce peut donc être enrôlé avec le même navigateur sans blocage.

### Mise à jour 2025-11-24

- Une colonne `click_url` est désormais obligatoire pour enregistrer les liens de redirection des notifications.
- Exécutez `last_update.sql` sur les bases existantes pour ajouter la colonne manquante et éviter l'erreur `Unknown column 'click_url' in 'field list'` observée lors de l'envoi des notifications.

## Dépannage

- `TypeError: webpush() got an unexpected keyword argument 'vapid_public_key'` : à partir de pywebpush 2.0, la fonction `webpush` n'accepte plus ce paramètre. Assurez-vous que l'appel utilise uniquement `vapid_private_key` et `vapid_claims`.

## Agent

Un fichier `AGENTS.md` n'existait pas à l'origine. Si vous ajoutez des règles de contribution ou des étapes de reprise après incident, créez/éditez `AGENTS.md` à la racine pour documenter les bonnes pratiques.
