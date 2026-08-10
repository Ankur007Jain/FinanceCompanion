/**
 * A 401 from any id_token-authenticated backend call means the session's Google ID
 * token is invalid/expired. idToken is passed down as a static prop from the
 * server-rendered session at page load — nothing client-side can refresh it, so a
 * mid-session 401 (the token going stale while a tab stays open, as opposed to being
 * stale already at load, which the server-side RefreshTokenError checks in page.tsx
 * catch) has to be handled here: force a full re-auth rather than silently no-op'ing,
 * which previously left users looking at a chat/dashboard that just stopped responding
 * with no explanation.
 *
 * Full navigation (not router.push) is deliberate — it forces a fresh server round
 * trip through auth.ts's jwt callback, so a session that's actually still refreshable
 * gets a real chance to recover instead of just bouncing to /signin unconditionally.
 */
export function handleUnauthorized(status: number): boolean {
  if (status === 401) {
    window.location.href = "/signin?reason=session_expired";
    return true;
  }
  return false;
}
