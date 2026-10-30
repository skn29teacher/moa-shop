/* Supabase confirms the email; the app still requires its regular server login. */
function consumeAuthConfirmation(location, history) {
  const fragment = new URLSearchParams(location.hash.slice(1));
  const query = new URLSearchParams(location.search);
  const errorKeys = ["error", "error_code", "error_description"];
  const failed = errorKeys.some((key) => fragment.has(key) || query.has(key));
  const confirmed = fragment.has("access_token");
  const callback = location.pathname === "/auth/confirm" || failed
    || confirmed || fragment.has("refresh_token");
  if (!callback) return null;
  // Canonical same-origin destination. Drop the fragment, query, and any token values.
  history.replaceState(null, "", "/#/login");
  return failed ? "error" : confirmed ? "confirmed" : "pending";
}
