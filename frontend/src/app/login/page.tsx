import { redirect } from "next/navigation";

import { LoginForm } from "@/components/auth/login-form";
import { zhCN } from "@/core/i18n/locales/zh-CN";
import { getSession } from "@/server/better-auth/server";

type LoginPageProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
};

function sanitizeNextPath(candidate: string | string[] | undefined) {
  const value = Array.isArray(candidate) ? candidate[0] : candidate;
  if (!value || !value.startsWith("/") || value.startsWith("//")) {
    return "/workspace";
  }
  return value;
}

export default async function LoginPage({ searchParams }: LoginPageProps) {
  const session = await getSession();
  const nextPath = sanitizeNextPath((await searchParams).next);

  if (session?.user) {
    redirect(nextPath);
  }

  return (
    <main className="bg-background flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-md rounded-2xl border p-8 shadow-sm">
        <div className="mb-6 space-y-2 text-center">
          <h1 className="text-2xl font-semibold">{zhCN.auth.loginTitle}</h1>
          <p className="text-muted-foreground text-sm">
            {zhCN.auth.loginDescription}
          </p>
        </div>
        <LoginForm />
      </div>
    </main>
  );
}
