-- SQLite schema. Timestamps are validated ISO text; currency is integer BRL cents.
CREATE TABLE customers (
    customer_id TEXT NOT NULL PRIMARY KEY,
    customer_unique_id TEXT NOT NULL,
    customer_zip_code_prefix TEXT NOT NULL,
    customer_city TEXT NOT NULL,
    customer_state TEXT NOT NULL CHECK(length(customer_state) = 2)
);
CREATE TABLE sellers (
    seller_id TEXT NOT NULL PRIMARY KEY,
    seller_zip_code_prefix TEXT NOT NULL,
    seller_city TEXT NOT NULL,
    seller_state TEXT NOT NULL CHECK(length(seller_state) = 2)
);
CREATE TABLE category_translations (
    product_category_name TEXT NOT NULL PRIMARY KEY,
    product_category_name_english TEXT NOT NULL
);
CREATE TABLE products (
    product_id TEXT NOT NULL PRIMARY KEY,
    -- Not a foreign key: two observed categories have no supplied translation.
    product_category_name TEXT,
    product_name_length INTEGER,
    product_description_length INTEGER,
    product_photos_qty INTEGER,
    product_weight_g INTEGER,
    product_length_cm INTEGER,
    product_height_cm INTEGER,
    product_width_cm INTEGER
);
CREATE TABLE orders (
    order_id TEXT NOT NULL PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    order_status TEXT NOT NULL,
    order_purchase_timestamp TEXT NOT NULL,
    order_approved_at TEXT,
    order_delivered_carrier_date TEXT,
    order_delivered_customer_date TEXT,
    order_estimated_delivery_date TEXT NOT NULL
);
CREATE TABLE order_items (
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    order_item_id INTEGER NOT NULL CHECK(order_item_id > 0),
    product_id TEXT NOT NULL REFERENCES products(product_id),
    seller_id TEXT NOT NULL REFERENCES sellers(seller_id),
    shipping_limit_date TEXT NOT NULL,
    price_cents INTEGER NOT NULL CHECK(price_cents >= 0),
    freight_value_cents INTEGER NOT NULL CHECK(freight_value_cents >= 0),
    PRIMARY KEY(order_id, order_item_id)
);
CREATE TABLE payments (
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    payment_sequential INTEGER NOT NULL CHECK(payment_sequential > 0),
    payment_type TEXT NOT NULL,
    payment_installments INTEGER NOT NULL CHECK(payment_installments >= 0),
    payment_value_cents INTEGER NOT NULL CHECK(payment_value_cents >= 0),
    PRIMARY KEY(order_id, payment_sequential)
);
CREATE TABLE reviews (
    review_id TEXT NOT NULL,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    review_score INTEGER NOT NULL CHECK(review_score BETWEEN 1 AND 5),
    review_comment_title TEXT,
    review_comment_message TEXT,
    review_creation_date TEXT NOT NULL,
    review_answer_timestamp TEXT NOT NULL,
    PRIMARY KEY(review_id, order_id)
);
CREATE TABLE geolocation (
    -- 1-based CSV data-record ordinal, stable for this exact input file.
    geolocation_row_id INTEGER NOT NULL PRIMARY KEY,
    geolocation_zip_code_prefix TEXT NOT NULL,
    geolocation_lat REAL NOT NULL CHECK(geolocation_lat BETWEEN -90 AND 90),
    geolocation_lng REAL NOT NULL CHECK(geolocation_lng BETWEEN -180 AND 180),
    geolocation_city TEXT NOT NULL,
    geolocation_state TEXT NOT NULL CHECK(length(geolocation_state) = 2)
);
CREATE INDEX idx_customers_identity ON customers(customer_unique_id);
CREATE INDEX idx_customers_state ON customers(customer_state);
CREATE INDEX idx_customers_zip ON customers(customer_zip_code_prefix);
CREATE INDEX idx_sellers_zip ON sellers(seller_zip_code_prefix);
CREATE INDEX idx_sellers_state ON sellers(seller_state);
CREATE INDEX idx_products_category ON products(product_category_name);
CREATE INDEX idx_orders_customer ON orders(customer_id);
CREATE INDEX idx_orders_purchase ON orders(order_purchase_timestamp);
CREATE INDEX idx_orders_status ON orders(order_status);
-- Composite primary keys already index order_id on items and payments.
CREATE INDEX idx_items_product ON order_items(product_id);
CREATE INDEX idx_items_seller ON order_items(seller_id);
CREATE INDEX idx_reviews_order ON reviews(order_id);
CREATE INDEX idx_geolocation_zip ON geolocation(geolocation_zip_code_prefix);
