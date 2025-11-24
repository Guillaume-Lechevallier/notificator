# Notificator

Application de notifications Web Push avec un backend Python (FastAPI), un frontend statique et une base MySQL. L'interface d'administration envoie des messages courts à tous les abonnés (titre, contenu optionnel, image et lien d'ouverture). Les utilisateurs s'inscrivent via le lien d'inscription : un service worker affiche la notification même si l'onglet est fermé.

## Aperçu des dossiers

- `backend/` : API FastAPI, modèles SQLAlchemy et configuration de la base de données.
- `frontend/` : pages statiques (inscription et administration).
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

6. Ouvrez `http://localhost:8000/admin.html` pour envoyer des notifications.
7. Ouvrez `http://localhost:8000/index.html` depuis un navigateur autorisant les notifications (HTTPS ou localhost).

## Flux fonctionnel

1. Un utilisateur s'inscrit via la page `index.html` : le navigateur enregistre un abonnement Web Push et l'envoie à `/api/subscribers`.
2. L'administrateur remplit le formulaire (titre, contenu, image, lien) puis clique sur le bouton cloche pour envoyer la notification.
3. L'API crée une notification et une livraison pour chaque abonné, envoie le Web Push via pywebpush et marque la livraison comme livrée (ou failed en cas d'erreur réseau).
4. Le service worker (`/sw.js`) affiche la pop-up native. Au clic, l'utilisateur est redirigé vers le lien saisi ou vers `notification.html` (affichage image + lien) en fallback.

## API (résumé)

- `GET /api/config` : renvoie la clé publique VAPID pour s'abonner.
- `POST /api/subscribers` : enregistre un abonnement Web Push (payload `{ subscription, label?, user_agent? }`).
- `GET /api/subscribers` : liste les abonnés (nom + token) pour l'aperçu admin.
- `GET /api/notifications` : liste les notifications envoyées.
- `POST /api/notifications` : crée une notification (payload `{ title, body?, image_url?, click_url? }`).
- `GET /api/push/{device_token}` et endpoints associés restent disponibles pour compatibilité / suivi de livraisons.

## Base de données

Le schéma MySQL est décrit dans `last_update.sql`. Si le modèle évolue, déplacer l'ancien contenu dans `last_update_old.sql` et mettre le nouveau SQL dans `last_update.sql`.

## Agent

Un fichier `AGENTS.md` n'existait pas à l'origine. Si vous ajoutez des règles de contribution ou des étapes de reprise après incident, créez/éditez `AGENTS.md` à la racine pour documenter les bonnes pratiques.
