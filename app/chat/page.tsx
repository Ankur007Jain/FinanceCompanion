import { redirect } from "next/navigation";
import { auth } from "@/auth";
import ChatClient from "./ChatClient";

export default async function ChatPage() {
  const session = await auth();
  if (!session?.user) redirect("/signin");
  return (
    <ChatClient
      userEmail={session.user.email!}
      userName={session.user.name || ""}
      idToken={(session as any).idToken || ""}
    />
  );
}
