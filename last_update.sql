-- Mise à jour 2025-11-28 : nettoyage des abonnés invalides avant l'index d'unicité sur endpoint
-- Idempotent et compatible MySQL 8.0 (ALTER conditionnels via PREPARE/EXECUTE)

-- Tables de base (installation fraîche)
CREATE TABLE IF NOT EXISTS subscribers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    device_token VARCHAR(64) NOT NULL UNIQUE,
    label VARCHAR(120) NULL,
    endpoint TEXT NOT NULL,
    p256dh TEXT NOT NULL,
    auth TEXT NOT NULL,
    user_agent VARCHAR(255) NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_subscriber_endpoint (endpoint(255))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS businesses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    manager_name VARCHAR(255) NULL,
    phone VARCHAR(50) NULL,
    email VARCHAR(255) NULL,
    address VARCHAR(255) NULL,
    subscriber_id INT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_business_subscriber FOREIGN KEY (subscriber_id) REFERENCES subscribers(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    body TEXT NULL,
    image_url TEXT NULL,
    click_url TEXT NULL,
    business_id INT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_notification_business FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS deliveries (
    id INT AUTO_INCREMENT PRIMARY KEY,
    notification_id INT NOT NULL,
    subscriber_id INT NOT NULL,
    status VARCHAR(32) DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    delivered_at DATETIME NULL,
    opened_at DATETIME NULL,
    CONSTRAINT fk_delivery_notification FOREIGN KEY (notification_id) REFERENCES notifications(id) ON DELETE CASCADE,
    CONSTRAINT fk_delivery_subscriber FOREIGN KEY (subscriber_id) REFERENCES subscribers(id) ON DELETE CASCADE,
    CONSTRAINT uq_delivery_notification_subscriber UNIQUE (notification_id, subscriber_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS health_checks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Alignement conditionnel des installations existantes
SET @schema_name := DATABASE();

-- Ajout des colonnes Web Push sur subscribers
SET @sql := (
    SELECT IF(
        EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema=@schema_name AND table_name='subscribers' AND column_name='label'),
        'DO 0',
        'ALTER TABLE subscribers ADD COLUMN label VARCHAR(120) NULL AFTER device_token'
    )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql := (
    SELECT IF(
        EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema=@schema_name AND table_name='subscribers' AND column_name='endpoint'),
        'DO 0',
        'ALTER TABLE subscribers ADD COLUMN endpoint TEXT NOT NULL AFTER label'
    )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql := (
    SELECT IF(
        EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema=@schema_name AND table_name='subscribers' AND column_name='p256dh'),
        'DO 0',
        'ALTER TABLE subscribers ADD COLUMN p256dh TEXT NOT NULL AFTER endpoint'
    )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql := (
    SELECT IF(
        EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema=@schema_name AND table_name='subscribers' AND column_name='auth'),
        'DO 0',
        'ALTER TABLE subscribers ADD COLUMN auth TEXT NOT NULL AFTER p256dh'
    )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql := (
    SELECT IF(
        EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema=@schema_name AND table_name='subscribers' AND column_name='user_agent'),
        'DO 0',
        'ALTER TABLE subscribers ADD COLUMN user_agent VARCHAR(255) NULL AFTER auth'
    )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql := (
    SELECT IF(
        EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema=@schema_name AND table_name='subscribers' AND column_name='created_at'),
        'DO 0',
        'ALTER TABLE subscribers ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP AFTER user_agent'
    )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Harmonisation du type de device_token
SET @sql := (
    SELECT IF(
        EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema=@schema_name AND table_name='subscribers'
              AND column_name='device_token' AND column_type='varchar(64)' AND is_nullable='NO'
        ),
        'DO 0',
        'ALTER TABLE subscribers MODIFY COLUMN device_token VARCHAR(64) NOT NULL'
    )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Nettoyage des endpoints invalides avant création de l'index unique
DELETE FROM subscribers WHERE endpoint IS NULL OR TRIM(endpoint) = '';

-- Suppression des doublons d'endpoint en conservant le premier enregistrement
DELETE s1 FROM subscribers s1
JOIN subscribers s2 ON s1.endpoint = s2.endpoint
WHERE s1.id > s2.id AND s1.endpoint IS NOT NULL AND TRIM(s1.endpoint) <> '';

-- Index d'unicité sur endpoint
SET @sql := (
    SELECT IF(
        EXISTS (
            SELECT 1 FROM information_schema.statistics
            WHERE table_schema=@schema_name AND table_name='subscribers'
              AND index_name='uq_subscriber_endpoint'
        ),
        'DO 0',
        'ALTER TABLE subscribers ADD UNIQUE INDEX uq_subscriber_endpoint (endpoint(255))'
    )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Colonnes et clé étrangère sur notifications
SET @sql := (
    SELECT IF(
        EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema=@schema_name AND table_name='notifications' AND column_name='click_url'),
        'DO 0',
        'ALTER TABLE notifications ADD COLUMN click_url TEXT NULL AFTER image_url'
    )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Harmonisation des anciens schémas utilisant target_url (colonne obligatoire)
-- Étape 1 : rendre la colonne facultative pour éviter les erreurs d'insertion
SET @sql := (
    SELECT IF(
        EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema=@schema_name AND table_name='notifications' AND column_name='target_url'
        ),
        'ALTER TABLE notifications MODIFY COLUMN target_url TEXT NULL',
        'DO 0'
    )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Étape 2 : recopier les valeurs target_url vers click_url si nécessaire
SET @sql := (
    SELECT IF(
        EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema=@schema_name AND table_name='notifications' AND column_name='target_url'
        ) AND EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema=@schema_name AND table_name='notifications' AND column_name='click_url'
        ),
        'UPDATE notifications SET click_url = target_url WHERE (click_url IS NULL OR LENGTH(TRIM(click_url)) = 0) AND target_url IS NOT NULL AND LENGTH(TRIM(target_url)) > 0',
        'DO 0'
    )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Étape 3 : supprimer la colonne obsolète target_url
SET @sql := (
    SELECT IF(
        EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema=@schema_name AND table_name='notifications' AND column_name='target_url'
        ),
        'ALTER TABLE notifications DROP COLUMN target_url',
        'DO 0'
    )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql := (
    SELECT IF(
        EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema=@schema_name AND table_name='notifications' AND column_name='business_id'),
        'DO 0',
        'ALTER TABLE notifications ADD COLUMN business_id INT NULL AFTER click_url'
    )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SET @sql := (
    SELECT IF(
        EXISTS (
            SELECT 1 FROM information_schema.referential_constraints
            WHERE constraint_schema=@schema_name AND constraint_name='fk_notification_business'
        ),
        'DO 0',
        'ALTER TABLE notifications ADD CONSTRAINT fk_notification_business FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE SET NULL'
    )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Clé étrangère sur businesses
SET @sql := (
    SELECT IF(
        EXISTS (
            SELECT 1 FROM information_schema.referential_constraints
            WHERE constraint_schema=@schema_name AND constraint_name='fk_business_subscriber'
        ),
        'DO 0',
        'ALTER TABLE businesses ADD CONSTRAINT fk_business_subscriber FOREIGN KEY (subscriber_id) REFERENCES subscribers(id) ON DELETE SET NULL'
    )
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;
