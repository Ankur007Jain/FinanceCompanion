import NextAuth from "next-auth";
import Google from "next-auth/providers/google";

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers: [Google({
    authorization: { params: { access_type: "offline", prompt: "consent" } },
  })],
  session: { maxAge: 60 * 60 * 24 * 30 },  // 30 days for the session cookie
  callbacks: {
    async jwt({ token, account }) {
      // First login — store all tokens and expiry
      if (account) {
        return {
          ...token,
          idToken: account.id_token,
          accessToken: account.access_token,
          refreshToken: account.refresh_token,
          expiresAt: account.expires_at,  // seconds since epoch
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
