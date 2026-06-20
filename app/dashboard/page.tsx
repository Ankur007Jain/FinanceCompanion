import { redirect } from "next/navigation";
import { auth } from "@/auth";
import DashboardClient from "./DashboardClient";

export default async function DashboardPage() {
  const session = await auth();
  if (!session?.user) redirect("/signin");
  return (
    <DashboardClient
      userEmail={session.user.email!}
      userName={session.user.name || ""}
      idToken={(session as any).idToken || ""}
    />
  );
}
