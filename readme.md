# Notificator

Application de notifications Web Push avec un backend Python (FastAPI), un frontend statique et une base MySQL. L'interface d'administration envoie des messages courts à tous les abonnés (titre, contenu optionnel, image et lien d'ouverture). Les utilisateurs s'inscrivent via le lien d'inscription : un service worker affiche la notification même si l'onglet est fermé.

## Aperçu des dossiers

- `backend/` : API FastAPI, modèles SQLAlchemy et configuration de la base de données.
- `frontend/` : pages statiques (inscription et administration).
- `admin.html` propose désormais une gestion des commerces (fiche détaillée + envoi ciblé).
- `last_update.sql` : script SQL à exécuter sur MySQL pour provisionner les tables (Web Push, abonnés, notifications, livraisons).
- `docker-compose.yml` : lance MySQL et l'API sur le port 8000.

## Prérequis

- Docker et Docker Compose (recommandé pour MySQL)
- Python 3.11+ si vous exécutez l'API sans Docker

## Démarrage rapide avec Docker

```bash
docker compose up --build
```

L'API est disponible sur `http://localhost:8000` et sert aussi le frontend :

- `http://localhost:8000/index.html` : inscription / réception
- `http://localhost:8000/admin.html` : panneau d'administration

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
from pywebpush import generate_vapid_key
private, public = generate_vapid_key()
print('VAPID_PRIVATE_KEY=', private)
print('VAPID_PUBLIC_KEY=', public)
PY

export VAPID_PUBLIC_KEY="<clé publique>"
export VAPID_PRIVATE_KEY="<clé privée>"
export VAPID_CLAIM_EMAIL="mailto:admin@example.com"
```

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

### Mise à jour 2025-11-25

- Ajout de la table `businesses` (nom, gérant, téléphone, email, adresse, abonné associé) pour stocker les commerces.
- Ajout de la colonne `business_id` sur la table `notifications` pour tracer les envois ciblés.
- Exécutez `last_update.sql` sur les bases existantes pour créer la table et la clé étrangère.

### Mise à jour 2025-11-24

- Une colonne `click_url` est désormais obligatoire pour enregistrer les liens de redirection des notifications.
- Exécutez `last_update.sql` sur les bases existantes pour ajouter la colonne manquante et éviter l'erreur `Unknown column 'click_url' in 'field list'` observée lors de l'envoi des notifications.

## Agent

Un fichier `AGENTS.md` n'existait pas à l'origine. Si vous ajoutez des règles de contribution ou des étapes de reprise après incident, créez/éditez `AGENTS.md` à la racine pour documenter les bonnes pratiques.
