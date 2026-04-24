import { redirect } from "next/navigation";

import { getSession } from "@/server/better-auth/server";

export default async function HomePage() {
  const session = await getSession();
  if (!session?.user) {
    redirect("/login");
  }
  redirect("/workspace");
}
