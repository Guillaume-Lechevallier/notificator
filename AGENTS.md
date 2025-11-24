# Instructions pour les agents

- L'application est composée d'un backend FastAPI (dossier `backend/`) et d'un frontend statique (dossier `frontend/`).
- Les notifications sont des Web Push (titre + corps + image + lien optionnels) gérés via service worker (`frontend/sw.js`).
- La base de données cible est MySQL ; utilisez la variable d'environnement `DATABASE_URL` (format `mysql+mysqlconnector://user:pass@host:port/db`).
- Renseignez les clés VAPID (`VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_CLAIM_EMAIL`) avant d'appeler `/api/config` ou d'envoyer des notifications.
- Si le schéma SQL change, déplacez l'ancien contenu de `last_update.sql` dans `last_update_old.sql` et écrivez le nouveau SQL dans `last_update.sql`.
- Ne générez pas de fichiers binaires ; privilégiez les assets statiques (HTML/CSS/JS).
- Pour vérifier rapidement le code sans MySQL local, le backend accepte aussi SQLite si `DATABASE_URL` pointe vers `sqlite:///...`.
- Le frontend est servi par FastAPI via `StaticFiles`. Les pages principales : `index.html` (inscription) et `admin.html` (envoi des notifications).
- Commande de démarrage locale : `uvicorn backend.main:app --host 0.0.0.0 --port 8000` après avoir installé les dépendances (`pip install -r requirements.txt`).
- La pile Docker est définie par `docker-compose.yml` (services `db` et `app`).
