# Notificator

Application de notifications avec un backend Python (FastAPI), un frontend statique et une base MySQL. Une interface d'administration permet d'envoyer des notifications illustrées à tous les abonnés. Les utilisateurs s'inscrivent via le lien d'inscription et reçoivent une pop-up avec une image et un lien de destination.

## Aperçu des dossiers

- `backend/` : API FastAPI, modèles SQLAlchemy et configuration de la base de données.
- `frontend/` : pages statiques (inscription, administration et affichage d'image).
- `last_update.sql` : script SQL à exécuter sur MySQL pour provisionner les tables.
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
4. Lancez l'API :

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

5. Ouvrez `http://localhost:8000/admin.html` pour envoyer des notifications.

## Flux fonctionnel

1. Un utilisateur s'inscrit via la page `index.html`, qui enregistre l'email (optionnel) et récupère un `device_token`.
2. L'administrateur remplit le formulaire (titre, texte, URL d'image, URL cible) et clique sur le bouton cloche pour envoyer la notification.
3. L'API crée une notification et une livraison pour chaque abonné.
4. Les abonnés pollent `/api/push/{device_token}` pour récupérer les notifications en attente. Une pop-up s'affiche avec le visuel et un bouton pour ouvrir la page image (`notification.html`).

## API (résumé)

- `POST /api/subscribers` : crée un abonné (payload `{ email?: string }`).
- `GET /api/notifications` : liste les notifications envoyées.
- `POST /api/notifications` : crée une notification (payload `{ title, body?, image_url, target_url }`).
- `GET /api/push/{device_token}` : récupère les livraisons associées au token.
- `POST /api/push/{delivery_id}/delivered` : marque une livraison comme livrée.
- `POST /api/push/{delivery_id}/opened` : marque une livraison comme ouverte.

## Base de données

Le schéma MySQL est décrit dans `last_update.sql`. Si le modèle évolue, déplacer l'ancien contenu dans `last_update_old.sql` et mettre le nouveau SQL dans `last_update.sql`.

## Agent

Un fichier `AGENTS.md` n'existait pas à l'origine. Si vous ajoutez des règles de contribution ou des étapes de reprise après incident, créez/éditez `AGENTS.md` à la racine pour documenter les bonnes pratiques.
