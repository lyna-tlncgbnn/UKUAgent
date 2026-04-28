"use client";

import { useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowRight, LoaderCircle, LockKeyhole, Mail } from "lucide-react";
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
      <form className="space-y-5" onSubmit={handleSubmit}>
        <div className="space-y-2">
          <label
            className="text-sm font-medium text-[#263b34]"
            htmlFor="login-email"
          >
            {t.auth.emailLabel}
          </label>
          <div className="relative">
            <Mail className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-[#7f968e]" />
            <Input
              id="login-email"
              autoComplete="email"
              className="h-11 rounded-lg border-[#d5e2dd] bg-[#fbfdfc] pr-4 pl-10 text-[#10231d] shadow-none placeholder:text-[#9caea8] focus-visible:border-[#159b85] focus-visible:ring-[#159b85]/16"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="请输入内部邮箱"
              required
            />
          </div>
        </div>
        <div className="space-y-2">
          <label
            className="text-sm font-medium text-[#263b34]"
            htmlFor="login-password"
          >
            {t.auth.passwordLabel}
          </label>
          <div className="relative">
            <LockKeyhole className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-[#7f968e]" />
            <Input
              id="login-password"
              autoComplete="current-password"
              className="h-11 rounded-lg border-[#d5e2dd] bg-[#fbfdfc] pr-4 pl-10 text-[#10231d] shadow-none placeholder:text-[#9caea8] focus-visible:border-[#159b85] focus-visible:ring-[#159b85]/16"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="请输入登录密码"
              required
            />
          </div>
        </div>
        <Button
          className="h-11 w-full rounded-lg bg-[#159b85] text-sm font-semibold text-white shadow-lg shadow-[#159b85]/20 hover:bg-[#0f8974] focus-visible:ring-[#159b85]/25"
          disabled={isSubmitting}
          type="submit"
        >
          {isSubmitting ? (
            <>
              <LoaderCircle className="size-4 animate-spin" />
              {t.auth.signingIn}
            </>
          ) : (
            <>
              {t.auth.signIn}
              <ArrowRight className="size-4" />
            </>
          )}
        </Button>
      </form>
      <Toaster position="top-center" richColors />
    </>
  );
}
