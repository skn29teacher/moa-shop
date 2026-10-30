-- Historical PostgreSQL schema. Not used by the SQLite app.
-- STEP 1: Supabase SQL Editor에서 실행할 신규 프로젝트용 스키마입니다.
-- 기존 동명 테이블이 있으면 오류로 중단합니다. 기존 데이터를 삭제하지 않습니다.
BEGIN;

CREATE TABLE public.users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email varchar(254) NOT NULL UNIQUE,
    password_hash text NOT NULL,
    name varchar(100) NOT NULL,
    phone varchar(30),
    address varchar(500),
    deleted_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT users_email_normalized CHECK (
        email = lower(btrim(email)) AND email <> ''
    ),
    CONSTRAINT users_name_not_blank CHECK (btrim(name) <> ''),
    CONSTRAINT users_password_hash_not_blank CHECK (btrim(password_hash) <> '')
);

CREATE TABLE public.products (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name varchar(200) NOT NULL,
    description text NOT NULL DEFAULT '',
    price numeric(12, 0) NOT NULL,
    stock integer NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT products_name_not_blank CHECK (btrim(name) <> ''),
    CONSTRAINT products_price_positive CHECK (price > 0),
    CONSTRAINT products_stock_nonnegative CHECK (stock >= 0)
);

CREATE TABLE public.orders (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
    status varchar(20) NOT NULL DEFAULT 'cart',
    total_amount numeric(14, 0) NOT NULL DEFAULT 0,
    recipient_name varchar(100),
    recipient_phone varchar(30),
    shipping_address varchar(500),
    ordered_at timestamptz,
    paid_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT orders_status_valid CHECK (status IN ('cart', 'pending', 'paid')),
    CONSTRAINT orders_total_nonnegative CHECK (total_amount >= 0),
    -- 장바구니는 배송정보가 없어도 되지만 주문 생성 이후에는 필수입니다.
    CONSTRAINT orders_checkout_fields CHECK (
        (status = 'cart' AND ordered_at IS NULL AND paid_at IS NULL)
        OR
        (status IN ('pending', 'paid') AND ordered_at IS NOT NULL
            AND total_amount > 0
            AND recipient_name IS NOT NULL AND btrim(recipient_name) <> ''
            AND recipient_phone IS NOT NULL AND btrim(recipient_phone) <> ''
            AND shipping_address IS NOT NULL AND btrim(shipping_address) <> '')
    ),
    CONSTRAINT orders_paid_timestamp CHECK (
        (status = 'paid' AND paid_at IS NOT NULL)
        OR (status <> 'paid' AND paid_at IS NULL)
    )
);

-- 장바구니가 주문으로 전환되면 새 장바구니를 만들 수 있습니다.
CREATE UNIQUE INDEX orders_one_cart_per_user
    ON public.orders(user_id) WHERE status = 'cart';
CREATE INDEX orders_user_created_idx ON public.orders(user_id, created_at DESC);

CREATE TABLE public.order_items (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id uuid NOT NULL REFERENCES public.orders(id) ON DELETE CASCADE,
    product_id uuid NOT NULL REFERENCES public.products(id) ON DELETE RESTRICT,
    product_name varchar(200) NOT NULL,
    quantity integer NOT NULL,
    unit_price numeric(12, 0) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT order_items_order_product_unique UNIQUE (order_id, product_id),
    CONSTRAINT order_items_quantity_positive CHECK (quantity > 0),
    CONSTRAINT order_items_unit_price_positive CHECK (unit_price > 0),
    CONSTRAINT order_items_product_name_not_blank CHECK (btrim(product_name) <> '')
);
CREATE INDEX order_items_product_idx ON public.order_items(product_id);

CREATE TABLE public.payments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id uuid NOT NULL REFERENCES public.orders(id) ON DELETE RESTRICT,
    amount numeric(14, 0) NOT NULL,
    status varchar(20) NOT NULL,
    failure_reason varchar(500),
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT payments_amount_positive CHECK (amount > 0),
    CONSTRAINT payments_status_valid CHECK (status IN ('success', 'failed')),
    CONSTRAINT payments_result_fields CHECK (
        (status = 'success' AND failure_reason IS NULL)
        OR (status = 'failed' AND failure_reason IS NOT NULL
            AND btrim(failure_reason) <> '')
    )
);
CREATE INDEX payments_order_created_idx ON public.payments(order_id, created_at DESC);
-- 실패 후 재시도는 허용하되 한 주문의 성공 기록은 하나만 허용합니다.
CREATE UNIQUE INDEX payments_one_success_per_order
    ON public.payments(order_id) WHERE status = 'success';

-- 브라우저에서 Supabase 테이블로 직접 접근하지 않습니다.
-- anon/authenticated 역할의 테이블 접근을 차단하고 RLS 정책도 만들지 않습니다.
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.products ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.order_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.payments ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.users, public.products, public.orders,
    public.order_items, public.payments FROM anon, authenticated;

COMMIT;

-- updated_at은 후속 단계의 UPDATE 문에서 명시적으로 갱신합니다.
-- 테이블 간 합계/상태 일치와 재고 동시성은 후속 API의 트랜잭션으로 보장합니다.
