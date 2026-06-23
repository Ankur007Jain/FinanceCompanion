import NextAuth from "next-auth";
import Google from "next-auth/providers/google";
import Credentials from "next-auth/providers/credentials";

const testProviders = process.env.AUTH_TEST_MODE === "true"
  ? [Credentials({
      id: "test-credentials",
      name: "Test",
      credentials: { email: { label: "Email", type: "email" } },
      async authorize(credentials) {
        const allowed = process.env.TEST_USER_EMAIL || "test@financecompanion.dev";
        if (credentials?.email === allowed) {
          return { id: "test-user", email: allowed, name: "Test User" };
        }
        return null;
      },
    })]
  : [];

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers: [
    Google({ authorization: { params: { access_type: "offline" } } }),
    ...testProviders,
  ],
  session: { maxAge: 60 * 60 * 24 * 30 },  // 30 days for the session cookie
  callbacks: {
    async jwt({ token, account, user }) {
      // First login via Google — store all tokens
      if (account) {
        return {
          ...token,
          idToken: account.id_token,
          accessToken: account.access_token,
          refreshToken: account.refresh_token,
          expiresAt: account.expires_at,  // seconds since epoch
        };
      }

      // First login via test credentials — fabricate a test idToken
      if (user?.email && !(token as any).idToken) {
        return {
          ...token,
          idToken: `test-token-${user.email}`,
          expiresAt: Math.floor(Date.now() / 1000) + 86400,
        };
      }

      // Token still valid — return as-is
      if (Date.now() < ((token.expiresAt as number) ?? 0) * 1000 - 60_000) {
        return token;
      }

      // Token expired — refresh via Google
      try {
        const res = await fetch("https://oauth2.googleapis.com/token", {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: new URLSearchParams({
            client_id: process.env.AUTH_GOOGLE_ID!,
            client_secret: process.env.AUTH_GOOGLE_SECRET!,
            grant_type: "refresh_token",
            refresh_token: token.refreshToken as string,
          }),
        });
        const refreshed = await res.json();
        if (!res.ok) throw refreshed;
        return {
          ...token,
          idToken: refreshed.id_token ?? token.idToken,
          accessToken: refreshed.access_token,
          expiresAt: Math.floor(Date.now() / 1000) + (refreshed.expires_in ?? 3600),
        };
      } catch {
        return { ...token, error: "RefreshTokenError" };
      }
    },
    async session({ session, token }) {
      (session as any).idToken = (token as any).idToken;
      (session as any).error = (token as any).error;
      return session;
    },
  },
  pages: { signIn: "/signin" },
});
