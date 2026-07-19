import { redirect } from "next/navigation";
import { auth } from "@/auth";
import MemoryClient from "./MemoryClient";

const API = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8001";

export default async function MemoryPage() {
  const session = await auth();
  if (!session?.user) redirect("/signin");

  const idToken = (session as any).idToken || "";
  const res = await fetch(`${API}/auth/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id_token: idToken }),
    cache: "no-store",
  });
  if (!res.ok) redirect("/signin");

  return <MemoryClient idToken={idToken} />;
}
