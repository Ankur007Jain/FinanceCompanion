import { redirect } from "next/navigation";
import { auth } from "@/auth";
import AdminClient from "./AdminClient";

const API = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8001";

export default async function AdminPage() {
  const session = await auth();
  if (!session?.user) redirect("/signin");

  const idToken = (session as any).idToken || "";
  const res = await fetch(`${API}/auth/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id_token: idToken }),
    cache: "no-store",
  });
  if (!res.ok) redirect("/dashboard");
  const user = await res.json();
  if (!user.is_admin) redirect("/dashboard");

  return <AdminClient idToken={idToken} />;
}
