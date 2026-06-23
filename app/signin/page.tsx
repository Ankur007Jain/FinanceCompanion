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
  const testMode = process.env.AUTH_TEST_MODE === "true";
  const testEmail = process.env.TEST_USER_EMAIL || "test@financecompanion.dev";
  return (
    <SignInClient
      sessionExpired={reason === "session_expired"}
      testMode={testMode}
      testEmail={testEmail}
    />
  );
}
