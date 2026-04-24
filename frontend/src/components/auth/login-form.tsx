"use client";

import { useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Toaster, toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { signInWithPassword } from "@/core/auth/api";
import { useI18n } from "@/core/i18n/hooks";

function sanitizeNextPath(candidate: string | null) {
  if (!candidate || !candidate.startsWith("/")) {
    return "/workspace";
  }
  if (candidate.startsWith("//")) {
    return "/workspace";
  }
  return candidate;
}

export function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { t } = useI18n();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const nextPath = useMemo(
    () => sanitizeNextPath(searchParams.get("next")),
    [searchParams],
  );

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      await signInWithPassword({
        email: email.trim(),
        password,
      });
      router.replace(nextPath);
      router.refresh();
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : t.auth.invalidCredentials,
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <>
      <form className="space-y-4" onSubmit={handleSubmit}>
        <div className="space-y-2">
          <label className="text-sm font-medium" htmlFor="login-email">
            {t.auth.emailLabel}
          </label>
          <Input
            id="login-email"
            autoComplete="email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@example.com"
            required
          />
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium" htmlFor="login-password">
            {t.auth.passwordLabel}
          </label>
          <Input
            id="login-password"
            autoComplete="current-password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="********"
            required
          />
        </div>
        <Button className="w-full" disabled={isSubmitting} type="submit">
          {isSubmitting ? t.auth.signingIn : t.auth.signIn}
        </Button>
      </form>
      <Toaster position="top-center" />
    </>
  );
}
