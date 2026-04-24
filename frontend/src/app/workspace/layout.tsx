import { redirect } from "next/navigation";

import { WorkspaceLayoutShell } from "@/components/workspace/workspace-layout-shell";
import { getSession } from "@/server/better-auth/server";

export default async function WorkspaceLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const session = await getSession();

  if (!session?.user) {
    redirect("/login?next=/workspace");
  }

  return <WorkspaceLayoutShell>{children}</WorkspaceLayoutShell>;
}

