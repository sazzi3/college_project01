CREATE DATABASE IF NOT EXISTS fantasy_shop
    CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE fantasy_shop;
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS shops (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(24) NOT NULL UNIQUE,
    day INT UNSIGNED NOT NULL DEFAULT 1,
    gold BIGINT UNSIGNED NOT NULL DEFAULT 220,
    level TINYINT UNSIGNED NOT NULL DEFAULT 1,
    reputation SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    goal_reached BOOLEAN NOT NULL DEFAULT FALSE,
    CHECK (day >= 1),
    CHECK (level BETWEEN 1 AND 3),
    CHECK (reputation <= 100)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS products (
    id SMALLINT UNSIGNED NOT NULL PRIMARY KEY,
    name VARCHAR(40) NOT NULL,
    description VARCHAR(100) NOT NULL,
    base_cost SMALLINT UNSIGNED NOT NULL,
    reference_price SMALLINT UNSIGNED NOT NULL,
    supply SMALLINT UNSIGNED NOT NULL,
    demand SMALLINT UNSIGNED NOT NULL,
    required_level TINYINT UNSIGNED NOT NULL,
    starter_quantity SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    CHECK (required_level BETWEEN 1 AND 3)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS inventory (
    shop_id BIGINT UNSIGNED NOT NULL,
    product_id SMALLINT UNSIGNED NOT NULL,
    quantity SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    stock_cost BIGINT UNSIGNED NOT NULL DEFAULT 0,
    price SMALLINT UNSIGNED NOT NULL,
    PRIMARY KEY (shop_id, product_id),
    FOREIGN KEY (shop_id) REFERENCES shops(id),
    FOREIGN KEY (product_id) REFERENCES products(id),
    CHECK (price > 0),
    CHECK (quantity > 0 OR stock_cost = 0)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS trades (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    shop_id BIGINT UNSIGNED NOT NULL,
    day INT UNSIGNED NOT NULL,
    product_id SMALLINT UNSIGNED NOT NULL,
    kind ENUM('buy', 'sale') NOT NULL,
    quantity SMALLINT UNSIGNED NOT NULL,
    unit_price SMALLINT UNSIGNED NOT NULL,
    cost BIGINT UNSIGNED NOT NULL,
    INDEX trades_shop_day_kind (shop_id, day, kind, product_id),
    FOREIGN KEY (shop_id) REFERENCES shops(id),
    FOREIGN KEY (product_id) REFERENCES products(id),
    CHECK (quantity > 0),
    CHECK (unit_price > 0)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS daily_reports (
    shop_id BIGINT UNSIGNED NOT NULL,
    day INT UNSIGNED NOT NULL,
    revenue BIGINT UNSIGNED NOT NULL,
    cost BIGINT UNSIGNED NOT NULL,
    customers SMALLINT UNSIGNED NOT NULL,
    missed SMALLINT UNSIGNED NOT NULL,
    PRIMARY KEY (shop_id, day),
    FOREIGN KEY (shop_id) REFERENCES shops(id),
    CHECK (missed <= customers)
) ENGINE=InnoDB;

INSERT INTO products
    (id, name, description, base_cost, reference_price, supply, demand,
     required_level, starter_quantity)
VALUES
    (1, '회복 물약', '모험가가 들고 다니는 기본 비상약', 12, 23, 16, 5, 1, 6),
    (2, '마나 약초', '마법 물약의 재료로 쓰는 푸른 약초', 7, 15, 20, 5, 1, 6),
    (3, '철제 단검', '여행길을 지키는 튼튼한 단검', 24, 45, 9, 3, 1, 2),
    (4, '은빛 부적', '위험을 피하고 싶은 이들이 찾는 부적', 33, 62, 10, 4, 2, 0),
    (5, '기사 방패', '경비대와 모험가가 쓰는 방패', 47, 85, 7, 3, 2, 0),
    (6, '별빛 지팡이', '숙련된 마법사가 사용하는 지팡이', 71, 125, 7, 3, 3, 0),
    (7, '용비늘 갑옷', '용비늘을 덧댄 희귀한 갑옷', 108, 190, 5, 2, 3, 0)
ON DUPLICATE KEY UPDATE id = products.id;
