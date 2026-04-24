"use client";

import { LockKeyholeIcon, MailIcon } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";
import { Toaster, toast } from "sonner";

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
      <form className="space-y-5" onSubmit={handleSubmit}>
        <div className="space-y-1.5">
          <label
            className="text-xs font-medium text-white/50"
            htmlFor="login-email"
          >
            {t.auth.emailLabel}
          </label>
          <div className="relative">
            <MailIcon className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-white/25" />
            <input
              id="login-email"
              autoComplete="email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="you@example.com"
              required
              className="h-11 w-full rounded-xl border border-white/10 bg-white/[0.07] pl-10 pr-4 text-sm text-white shadow-sm outline-none transition-all placeholder:text-white/20 hover:border-white/20 focus:border-white/30 focus:bg-white/10 focus:ring-2 focus:ring-white/10"
            />
          </div>
        </div>

        <div className="space-y-1.5">
          <label
            className="text-xs font-medium text-white/50"
            htmlFor="login-password"
          >
            {t.auth.passwordLabel}
          </label>
          <div className="relative">
            <LockKeyholeIcon className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-white/25" />
            <input
              id="login-password"
              autoComplete="current-password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="••••••••"
              required
              className="h-11 w-full rounded-xl border border-white/10 bg-white/[0.07] pl-10 pr-4 text-sm text-white shadow-sm outline-none transition-all placeholder:text-white/20 hover:border-white/20 focus:border-white/30 focus:bg-white/10 focus:ring-2 focus:ring-white/10"
            />
          </div>
        </div>

        <button
          className="flex h-11 w-full items-center justify-center rounded-xl bg-white/90 text-sm font-semibold text-[#0f3d36] shadow-lg shadow-black/10 transition-all hover:bg-white hover:shadow-xl hover:shadow-black/15 focus:outline-none focus:ring-2 focus:ring-white/40 focus:ring-offset-2 focus:ring-offset-transparent active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-60"
          disabled={isSubmitting}
          type="submit"
        >
          {isSubmitting ? (
            <span className="flex items-center gap-2">
              <svg
                className="size-4 animate-spin"
                viewBox="0 0 24 24"
                fill="none"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
              {t.auth.signingIn}
            </span>
          ) : (
            t.auth.signIn
          )}
        </button>
      </form>
      <Toaster position="top-center" />
    </>
  );
}
