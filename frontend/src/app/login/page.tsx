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
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-gradient-to-br from-[#0f3d36] via-[#1a6b5e] to-[#1a9e8f]">
      {/* ── Background decorative elements ──────────────────────────────── */}
      {/* Radial glow top-right */}
      <div className="pointer-events-none absolute -top-[30%] -right-[10%] size-[800px] rounded-full bg-[#1a9e8f]/30 blur-[120px]" />
      {/* Radial glow bottom-left */}
      <div className="pointer-events-none absolute -bottom-[20%] -left-[15%] size-[600px] rounded-full bg-[#0d7a6e]/40 blur-[100px]" />
      {/* Subtle grid pattern */}
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.04]"
        style={{
          backgroundImage:
            "linear-gradient(rgba(255,255,255,.3) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.3) 1px, transparent 1px)",
          backgroundSize: "60px 60px",
        }}
      />

      {/* ── Content container ───────────────────────────────────────────── */}
      <div className="relative z-10 mx-4 flex w-full max-w-[920px] overflow-hidden rounded-3xl bg-white/[0.07] shadow-2xl shadow-black/20 ring-1 ring-white/10 backdrop-blur-xl sm:mx-8">
        {/* ── Left branding area ──────────────────────────────────────── */}
        <div className="hidden w-[52%] flex-col justify-between p-10 lg:flex xl:p-12">
          <div>
            {/* Logo */}
            <div className="mb-10 flex items-center gap-3">
              <div className="flex size-11 items-center justify-center rounded-xl bg-white/15 ring-1 ring-white/20">
                <span className="text-base font-bold tracking-tight text-white">
                  UKU
                </span>
              </div>
              <span className="text-xl font-bold tracking-tight text-white">
                UKUBot
              </span>
            </div>

            {/* Tagline */}
            <h1 className="text-[1.75rem] font-bold leading-snug tracking-tight text-white/95">
              你的智能
              <br />
              金融工作助手
            </h1>
            <p className="mt-3 max-w-[280px] text-sm leading-relaxed text-white/50">
              AI 驱动的企业级智能助手，
              <br />
              助力团队高效决策与协作。
            </p>
          </div>

          {/* Feature pills */}
          <div className="space-y-2.5">
            {[
              { icon: "📊", text: "智能分析与深度研究" },
              { icon: "🔒", text: "企业级数据隔离与权限" },
              { icon: "⚡", text: "自定义技能与工具扩展" },
            ].map((item) => (
              <div
                key={item.text}
                className="flex items-center gap-3 rounded-xl bg-white/[0.06] px-4 py-2.5 ring-1 ring-white/[0.06]"
              >
                <span className="text-sm">{item.icon}</span>
                <span className="text-[13px] font-medium text-white/70">
                  {item.text}
                </span>
              </div>
            ))}
          </div>

          {/* Footer */}
          <p className="mt-8 text-[11px] text-white/25">
            © {new Date().getFullYear()} Mindigital Group · Internal Use Only
          </p>
        </div>

        {/* ── Right login card ───────────────────────────────────────── */}
        <div className="flex w-full flex-col justify-center bg-white/[0.06] px-8 py-12 backdrop-blur-sm sm:px-12 lg:w-[48%] lg:bg-white/[0.04]">
          {/* Mobile-only logo */}
          <div className="mb-8 flex items-center gap-2.5 lg:hidden">
            <div className="flex size-9 items-center justify-center rounded-lg bg-white/15 ring-1 ring-white/20">
              <span className="text-xs font-bold text-white">UKU</span>
            </div>
            <span className="text-lg font-bold tracking-tight text-white">
              UKUBot
            </span>
          </div>

          {/* Header */}
          <div className="mb-7 space-y-1.5">
            <h2 className="text-xl font-bold tracking-tight text-white">
              {zhCN.auth.loginTitle}
            </h2>
            <p className="text-[13px] text-white/40">
              {zhCN.auth.loginDescription}
            </p>
          </div>

          {/* Form */}
          <LoginForm />

          {/* Bottom note */}
          <p className="mt-8 text-center text-xs text-white/25">
            如需开通账号，请联系系统管理员
          </p>
        </div>
      </div>
    </main>
  );
}
