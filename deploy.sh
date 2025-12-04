#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  echo "Ce script doit être exécuté en tant que root." >&2
  exit 1
fi

DOMAIN=${1:-}
if [[ -z "${DOMAIN}" ]]; then
  echo "Usage : $0 <domaine> (ex. ./deploy.sh exemple.com)" >&2
  exit 1
fi

APP_NAME="notificator"
APP_USER="notificator"
APP_DIR="/opt/${APP_NAME}"
SERVICE_NAME="${APP_NAME}.service"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DB_NAME="${DB_NAME:-notificator}"
DB_USER="${DB_USER:-notificator}"
DB_PASSWORD="${DB_PASSWORD:-$(openssl rand -hex 16)}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-3306}"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@${DOMAIN}}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
ENV_FILE="/etc/${APP_NAME}.env"

log() {
  echo -e "[deploy] $1"
}

install_packages() {
  log "Installation des paquets système (Apache, Certbot, Python, MySQL)..."
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y
  apt-get install -y apache2 python3-venv python3-pip git mysql-server python3-certbot-apache rsync
  a2enmod proxy proxy_http headers rewrite ssl >/dev/null
}

sync_sources() {
  log "Synchronisation du code source dans ${APP_DIR}..."
  id -u "${APP_USER}" >/dev/null 2>&1 || useradd --system --home "${APP_DIR}" --shell /usr/sbin/nologin "${APP_USER}"
  mkdir -p "${APP_DIR}"
  rsync -a --delete \
    --exclude "venv" \
    --exclude ".git" \
    --exclude "__pycache__" \
    "${REPO_DIR}/" "${APP_DIR}/"
  chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"
}

setup_venv() {
  log "Création de l'environnement virtuel Python..."
  cd "${APP_DIR}"
  if [[ ! -d venv ]]; then
    "${PYTHON_BIN}" -m venv venv
  fi
  source venv/bin/activate
  pip install --upgrade pip
  pip install -r requirements.txt
  deactivate
  chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}/venv"
}

configure_database() {
  log "Provisionnement MySQL (${DB_NAME})..."
  mysql -uroot <<SQL
CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '${DB_USER}'@'${DB_HOST}' IDENTIFIED BY '${DB_PASSWORD}';
ALTER USER '${DB_USER}'@'${DB_HOST}' IDENTIFIED BY '${DB_PASSWORD}';
GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO '${DB_USER}'@'${DB_HOST}';
FLUSH PRIVILEGES;
SQL
}

write_env_file() {
  log "Mise à jour du fichier d'environnement (${ENV_FILE})..."
  cat >"${ENV_FILE}" <<EOF_ENV
DATABASE_URL=mysql+mysqlconnector://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}
VAPID_PUBLIC_KEY=${VAPID_PUBLIC_KEY:-}
VAPID_PRIVATE_KEY=${VAPID_PRIVATE_KEY:-}
VAPID_CLAIM_EMAIL=${VAPID_CLAIM_EMAIL:-mailto:${ADMIN_EMAIL}}
PORT=8000
EOF_ENV
  chown "${APP_USER}:${APP_USER}" "${ENV_FILE}"
  chmod 640 "${ENV_FILE}"
}

create_systemd_service() {
  log "Configuration du service systemd (${SERVICE_NAME})..."
  cat >/etc/systemd/system/${SERVICE_NAME} <<EOF_SERVICE
[Unit]
Description=Notificator (FastAPI)
After=network.target mysql.service

[Service]
Type=simple
User=${APP_USER}
Group=${APP_USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${APP_DIR}/venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF_SERVICE
  systemctl daemon-reload
  systemctl enable --now ${SERVICE_NAME}
}

configure_apache() {
  log "Configuration d'Apache pour ${DOMAIN}..."
  cat >/etc/apache2/sites-available/${APP_NAME}.conf <<EOF_VHOST
<VirtualHost *:80>
    ServerName ${DOMAIN}

    ProxyPreserveHost On
    ProxyPass / http://127.0.0.1:8000/
    ProxyPassReverse / http://127.0.0.1:8000/

    ErrorLog \${APACHE_LOG_DIR}/${APP_NAME}_error.log
    CustomLog \${APACHE_LOG_DIR}/${APP_NAME}_access.log combined
</VirtualHost>
EOF_VHOST
  a2ensite ${APP_NAME}.conf >/dev/null
  a2dissite 000-default.conf >/dev/null || true
  apachectl configtest
  systemctl reload apache2
}

obtain_certificate() {
  log "Obtention/renouvellement du certificat Let's Encrypt..."
  certbot --apache \
    --non-interactive \
    --agree-tos \
    --redirect \
    -m "${ADMIN_EMAIL}" \
    -d "${DOMAIN}" || log "Certbot n'a pas pu générer de certificat : vérifiez que le DNS pointe vers ce serveur."
}

final_message() {
  log "Déploiement terminé !"
  echo "- Service : systemctl status ${SERVICE_NAME}"
  echo "- Logs API : journalctl -u ${SERVICE_NAME} -f"
  echo "- Site : http://${DOMAIN} (sera redirigé en HTTPS si le certificat est actif)"
}

install_packages
sync_sources
setup_venv
configure_database
write_env_file
create_systemd_service
configure_apache
obtain_certificate
final_message

