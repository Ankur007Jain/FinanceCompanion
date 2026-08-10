import { redirect } from "next/navigation";
import { auth } from "@/auth";
import ChatClient from "./ChatClient";

export default async function ChatPage() {
  const session = await auth();
  if (!session?.user) redirect("/signin");
  // Token refresh failed server-side — force re-auth (same guard as dashboard/page.tsx)
  if ((session as any).error === "RefreshTokenError") redirect("/signin?reason=session_expired");
  return (
    <ChatClient
      userEmail={session.user.email!}
      userName={session.user.name || ""}
      idToken={(session as any).idToken || ""}
    />
  );
}
