"use client";

import { BotIcon, PlusIcon, SparklesIcon } from "lucide-react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { useAgents } from "@/core/agents";
import { useI18n } from "@/core/i18n/hooks";

import { AgentCard } from "./agent-card";

export function AgentGallery() {
  const { t } = useI18n();
  const { agents, isLoading } = useAgents();
  const router = useRouter();
  const ownedAgents = agents.filter((agent) => agent.is_owner);
  const sharedAgents = agents.filter(
    (agent) => !agent.is_owner && agent.visibility === "org_shared",
  );

  const handleNewAgent = () => {
    router.push("/workspace/agents/new");
  };

  return (
    <div className="flex size-full flex-col">
      {/* ── Page header ──────────────────────────────────────────────── */}
      <div className="shrink-0 border-b border-border/60 px-8 py-6">
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <h1 className="flex items-center gap-2 text-xl font-bold tracking-tight">
              <SparklesIcon className="text-primary size-5" />
              {t.agents.title}
            </h1>
            <p className="text-muted-foreground text-sm">
              {t.agents.description}
            </p>
          </div>
          <Button
            onClick={handleNewAgent}
            className="rounded-full shadow-sm"
            size="sm"
          >
            <PlusIcon className="mr-1.5 size-4" />
            {t.agents.newAgent}
          </Button>
        </div>
      </div>

      {/* ── Content ──────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-8 py-6">
        {isLoading ? (
          <div className="text-muted-foreground flex h-40 items-center justify-center text-sm">
            {t.common.loading}
          </div>
        ) : agents.length === 0 ? (
          /* ── Empty state ────────────────────────────────────────── */
          <div className="flex h-72 flex-col items-center justify-center gap-4 text-center">
            <div className="flex size-16 items-center justify-center rounded-2xl bg-gradient-to-br from-primary/10 to-primary/5 ring-1 ring-primary/10">
              <BotIcon className="text-primary/60 size-7" />
            </div>
            <div className="space-y-1">
              <p className="text-base font-semibold">{t.agents.emptyTitle}</p>
              <p className="text-muted-foreground mx-auto max-w-xs text-sm">
                {t.agents.emptyDescription}
              </p>
            </div>
            <Button
              variant="outline"
              className="mt-1 rounded-full"
              onClick={handleNewAgent}
            >
              <PlusIcon className="mr-1.5 size-4" />
              {t.agents.newAgent}
            </Button>
          </div>
        ) : (
          /* ── Agents list ────────────────────────────────────────── */
          <div className="space-y-10">
            {/* My Agents */}
            <section className="space-y-4">
              <div className="flex items-center gap-3">
                <h2 className="text-sm font-semibold tracking-wide uppercase text-foreground/80">
                  {t.agents.myAgentsTitle}
                </h2>
                <div className="bg-border/60 h-px flex-1" />
              </div>
              {ownedAgents.length === 0 ? (
                <div className="text-muted-foreground flex items-center justify-center rounded-2xl border border-dashed border-border/60 bg-muted/20 px-6 py-8 text-sm">
                  {t.agents.myAgentsEmpty}
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
                  {ownedAgents.map((agent) => (
                    <AgentCard key={agent.slug} agent={agent} />
                  ))}
                </div>
              )}
            </section>

            {/* Shared Agents */}
            <section className="space-y-4">
              <div className="flex items-center gap-3">
                <h2 className="text-sm font-semibold tracking-wide uppercase text-foreground/80">
                  {t.agents.sharedAgentsTitle}
                </h2>
                <div className="bg-border/60 h-px flex-1" />
              </div>
              {sharedAgents.length === 0 ? (
                <div className="text-muted-foreground flex items-center justify-center rounded-2xl border border-dashed border-border/60 bg-muted/20 px-6 py-8 text-sm">
                  {t.agents.sharedAgentsEmpty}
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
                  {sharedAgents.map((agent) => (
                    <AgentCard key={agent.slug} agent={agent} />
                  ))}
                </div>
              )}
            </section>
          </div>
        )}
      </div>
    </div>
  );
}
