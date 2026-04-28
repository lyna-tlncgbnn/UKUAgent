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

const capabilityCards = [
  ["知识沉淀", "集中管理可复用的内部业务上下文。"],
  ["流程协同", "连接需求、工具与任务推进链路。"],
  ["交付辅助", "让重复工作更快进入可评审状态。"],
];

export default async function LoginPage({ searchParams }: LoginPageProps) {
  const session = await getSession();
  const nextPath = sanitizeNextPath((await searchParams).next);

  if (session?.user) {
    redirect(nextPath);
  }

  return (
    <main className="min-h-screen bg-[#f4f8f6] text-[#10231d]">
      <div className="grid min-h-screen lg:grid-cols-[1.05fr_0.95fr]">
        <section className="relative hidden overflow-hidden bg-[#0e8f78] px-10 py-12 text-white lg:flex lg:flex-col lg:justify-between">
          <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(255,255,255,0.18),transparent_28%),radial-gradient(circle_at_78%_14%,rgba(10,77,60,0.32),transparent_30%),linear-gradient(150deg,#1fa58e_0%,#0b7f6c_48%,#0b4b3d_100%)]" />
          <div className="absolute right-[-8rem] bottom-[-8rem] h-80 w-80 rounded-full border border-white/15" />
          <div className="absolute right-20 bottom-24 h-44 w-44 rounded-full border border-white/10" />

          <div className="relative z-10 flex items-center gap-4">
            <div className="flex h-16 w-16 items-center justify-center rounded-[1.35rem] bg-white text-2xl font-bold tracking-wide text-[#159b85] shadow-2xl shadow-[#07382f]/20">
              UKU
            </div>
            <div>
              <p className="text-sm font-medium text-white/72">
                内部 Agent 工作台
              </p>
              <p className="text-lg font-semibold">UKUBot</p>
            </div>
          </div>

          <div className="relative z-10 max-w-2xl">
            <p className="mb-5 inline-flex rounded-full border border-white/20 bg-white/10 px-3 py-1 text-sm font-medium text-white/86 backdrop-blur">
              内部工作协助提效 Agent
            </p>
            <h1 className="max-w-xl text-5xl font-semibold leading-tight">
              把知识检索、分析判断和交付协作集中到一个工作入口。
            </h1>
            <p className="mt-6 max-w-lg text-base leading-7 text-white/76">
              UKUBot 面向内部团队，帮助处理重复的信息整理、任务分析和文档协作，让日常工作更快进入可交付状态。
            </p>
          </div>

          <div className="relative z-10 grid grid-cols-3 gap-3">
            {capabilityCards.map(([title, description]) => (
              <div
                className="rounded-xl border border-white/14 bg-white/10 p-4 backdrop-blur"
                key={title}
              >
                <p className="text-sm font-semibold">{title}</p>
                <p className="mt-2 text-xs leading-5 text-white/68">
                  {description}
                </p>
              </div>
            ))}
          </div>
        </section>

        <section className="flex min-h-screen items-center justify-center px-5 py-10 sm:px-8">
          <div className="w-full max-w-[27rem]">
            <div className="mb-8 flex items-center gap-3 lg:hidden">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#159b85] text-lg font-bold tracking-wide text-white shadow-lg shadow-[#159b85]/25">
                UKU
              </div>
              <div>
                <p className="text-sm font-medium text-[#53665f]">
                  内部 Agent 工作台
                </p>
                <p className="text-base font-semibold text-[#10231d]">
                  UKUBot
                </p>
              </div>
            </div>

            <div className="rounded-2xl border border-[#dce8e3] bg-white px-6 py-7 shadow-[0_24px_80px_rgba(17,58,48,0.12)] sm:px-8 sm:py-9">
              <div className="mb-7">
                <p className="mb-3 text-sm font-semibold text-[#159b85]">
                  安全登录
                </p>
                <h2 className="text-3xl font-semibold tracking-tight text-[#10231d]">
                  {zhCN.auth.loginTitle}
                </h2>
                <p className="mt-3 text-sm leading-6 text-[#60756e]">
                  使用内部账号进入 UKUBot 工作区，继续处理知识检索、任务分析和交付协作。
                </p>
              </div>
              <LoginForm />
            </div>

            <p className="mt-6 text-center text-xs leading-5 text-[#789087]">
              UKU 内部系统，仅限已授权团队成员访问。
            </p>
          </div>
        </section>
      </div>
    </main>
  );
}
