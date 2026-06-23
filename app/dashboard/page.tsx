import { redirect } from "next/navigation";
import { auth } from "@/auth";
import DashboardClient from "./DashboardClient";

export default async function DashboardPage() {
  const session = await auth();
  if (!session?.user) redirect("/signin");
  // Token refresh failed server-side — force re-auth
  if ((session as any).error === "RefreshTokenError") redirect("/signin?reason=session_expired");
  return (
    <DashboardClient
      userName={session.user.name || ""}
      idToken={(session as any).idToken || ""}
    />
  );
}
