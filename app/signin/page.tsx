import { redirect } from "next/navigation";
import { auth } from "@/auth";
import SignInClient from "./SignInClient";

export default async function SignInPage({
  searchParams,
}: {
  searchParams: Promise<{ reason?: string }>;
}) {
  const session = await auth();
  if (session?.user && !(session as any).error) redirect("/dashboard");
  const { reason } = await searchParams;
  return <SignInClient sessionExpired={reason === "session_expired"} />;
}
