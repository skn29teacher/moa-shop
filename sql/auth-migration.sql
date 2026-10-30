-- Schema/auth integration only; this does not migrate or link existing member accounts.
-- Run once AFTER schema.sql on new databases, or on an existing shop database.
-- Back up first. Preserves existing users.id and all order/payment references.
BEGIN;

ALTER TABLE public.users ADD COLUMN auth_user_id uuid UNIQUE REFERENCES auth.users(id) ON DELETE RESTRICT;
ALTER TABLE public.users ADD COLUMN role text NOT NULL DEFAULT 'customer'
    CHECK (role IN ('customer', 'admin'));
-- Legacy hashes are retained for rollback/migration only, never read by the app.
ALTER TABLE public.users ALTER COLUMN password_hash DROP NOT NULL;
ALTER TABLE public.users ALTER COLUMN password_hash DROP DEFAULT;

CREATE TABLE public.auth_sessions (
    token_hash text PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    encrypted_tokens text NOT NULL,
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX auth_sessions_user_idx ON public.auth_sessions(user_id);
CREATE INDEX auth_sessions_expiry_idx ON public.auth_sessions(expires_at);
ALTER TABLE public.auth_sessions ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.auth_sessions FROM PUBLIC, anon, authenticated;

-- Only profile fields come from untrusted user_metadata. Role always defaults to customer.
CREATE FUNCTION public.create_auth_profile() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
BEGIN
    INSERT INTO public.users (id, auth_user_id, email, name, phone, address)
    VALUES (NEW.id, NEW.id, lower(btrim(NEW.email)),
        left(coalesce(nullif(btrim(NEW.raw_user_meta_data ->> 'name'), ''), '회원'), 100),
        left(NEW.raw_user_meta_data ->> 'phone', 30),
        left(NEW.raw_user_meta_data ->> 'address', 500))
    -- Existing emails require explicit, verified account linking by an operator.
    ON CONFLICT (email) DO NOTHING;
    RETURN NEW;
END;
$$;
REVOKE ALL ON FUNCTION public.create_auth_profile() FROM PUBLIC, anon, authenticated;
CREATE TRIGGER on_auth_user_created AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.create_auth_profile();

-- The browser uses Flask APIs exclusively. No direct Data API access is granted.
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.products ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.order_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.payments ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.users, public.products, public.orders, public.order_items,
    public.payments FROM PUBLIC, anon, authenticated;

COMMIT;

-- Existing Auth accounts are NOT automatically linked by email.
-- After verifying ownership, link explicit IDs in the SQL Editor:
-- UPDATE public.users SET auth_user_id = '<verified auth.users.id>'::uuid
-- WHERE id = '<existing public.users.id>'::uuid AND auth_user_id IS NULL;
-- Grant the first admin explicitly (never from signup metadata):
-- UPDATE public.users SET role = 'admin' WHERE auth_user_id = '<verified auth.users.id>'::uuid;
