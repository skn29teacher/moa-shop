-- SQLite schema v1. Applied atomically by SQLiteDatabase.open(), not Supabase SQL Editor.
-- UUIDs are generated in Python. All timestamps are UTC ISO-8601 strings; money is integer KRW.
CREATE TABLE users (
    id TEXT PRIMARY KEY NOT NULL,
    auth_user_id TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE CHECK (email = lower(trim(email)) AND length(email) BETWEEN 1 AND 254),
    name TEXT NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 100),
    phone TEXT CHECK (phone IS NULL OR length(phone) <= 30),
    address TEXT CHECK (address IS NULL OR length(address) <= 500),
    role TEXT NOT NULL DEFAULT 'customer' CHECK (role IN ('customer', 'admin')),
    deleted_at TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE TABLE products (
    id TEXT PRIMARY KEY NOT NULL,
    name TEXT NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 200),
    description TEXT NOT NULL DEFAULT '',
    price INTEGER NOT NULL CHECK (typeof(price) = 'integer' AND price > 0 AND price <= 999999999999),
    stock INTEGER NOT NULL DEFAULT 0 CHECK (typeof(stock) = 'integer' AND stock BETWEEN 0 AND 2147483647),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE TABLE orders (
    id TEXT PRIMARY KEY NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    status TEXT NOT NULL DEFAULT 'cart' CHECK (status IN ('cart', 'pending', 'paid')),
    total_amount INTEGER NOT NULL DEFAULT 0 CHECK (typeof(total_amount) = 'integer' AND total_amount BETWEEN 0 AND 99999999999999),
    recipient_name TEXT,
    recipient_phone TEXT,
    shipping_address TEXT,
    ordered_at TEXT,
    paid_at TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK ((status = 'cart' AND ordered_at IS NULL AND paid_at IS NULL)
        OR (status IN ('pending', 'paid') AND ordered_at IS NOT NULL AND total_amount > 0
            AND recipient_name IS NOT NULL AND trim(recipient_name) <> ''
            AND recipient_phone IS NOT NULL AND trim(recipient_phone) <> ''
            AND shipping_address IS NOT NULL AND trim(shipping_address) <> '')),
    CHECK ((status = 'paid' AND paid_at IS NOT NULL) OR (status <> 'paid' AND paid_at IS NULL))
);
CREATE UNIQUE INDEX orders_one_cart_per_user ON orders(user_id) WHERE status = 'cart';
CREATE INDEX orders_user_created_idx ON orders(user_id, created_at DESC);
CREATE TABLE order_items (
    id TEXT PRIMARY KEY NOT NULL,
    order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id TEXT NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    product_name TEXT NOT NULL CHECK (trim(product_name) <> ''),
    quantity INTEGER NOT NULL CHECK (typeof(quantity) = 'integer' AND quantity BETWEEN 1 AND 2147483647),
    unit_price INTEGER NOT NULL CHECK (typeof(unit_price) = 'integer' AND unit_price BETWEEN 1 AND 999999999999),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    UNIQUE (order_id, product_id)
);
CREATE INDEX order_items_product_idx ON order_items(product_id);
CREATE TABLE payments (
    id TEXT PRIMARY KEY NOT NULL,
    order_id TEXT NOT NULL REFERENCES orders(id) ON DELETE RESTRICT,
    amount INTEGER NOT NULL CHECK (typeof(amount) = 'integer' AND amount BETWEEN 1 AND 99999999999999),
    status TEXT NOT NULL CHECK (status IN ('success', 'failed')),
    failure_reason TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    CHECK ((status = 'success' AND failure_reason IS NULL)
        OR (status = 'failed' AND failure_reason IS NOT NULL AND trim(failure_reason) <> ''))
);
CREATE INDEX payments_order_created_idx ON payments(order_id, created_at DESC);
CREATE UNIQUE INDEX payments_one_success_per_order ON payments(order_id) WHERE status = 'success';
CREATE TABLE auth_sessions (
    token_hash TEXT PRIMARY KEY NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    encrypted_tokens TEXT NOT NULL,
    expires_at INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX auth_sessions_user_idx ON auth_sessions(user_id);
CREATE INDEX auth_sessions_expiry_idx ON auth_sessions(expires_at);
