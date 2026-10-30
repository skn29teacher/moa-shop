-- DESTRUCTIVE: deletes all shop profiles, products, carts, orders, payments, and app sessions.
-- Does not delete Supabase Auth accounts or Supabase-managed schemas.
-- Run only when intentionally resetting this project's shop data.
BEGIN;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
DROP FUNCTION IF EXISTS public.create_auth_profile();

DROP TABLE IF EXISTS public.auth_sessions, public.payments, public.order_items,
    public.orders, public.products, public.users;

COMMIT;
