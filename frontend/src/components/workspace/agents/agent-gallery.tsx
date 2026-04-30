"use client";

import { BotIcon, PlusIcon } from "lucide-react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import {
  WorkspaceBody,
  WorkspaceContainer,
  WorkspaceHeader,
} from "@/components/workspace/workspace-container";
import { useAgents } from "@/core/agents";
import { useI18n } from "@/core/i18n/hooks";

import { AgentCard } from "./agent-card";

export function AgentGallery() {
  const { t } = useI18n();
  const { agents, isLoading } = useAgents();
  const router = useRouter();

  const handleNewAgent = () => {
    router.push("/workspace/agents/new");
  };

  return (
    <WorkspaceContainer>
      <WorkspaceHeader />
      <WorkspaceBody>
        <div className="flex size-full flex-col">
          {/* Page header */}
          <header className="flex shrink-0 items-center justify-center pt-8">
            <div className="flex w-full max-w-(--container-width-md) items-center justify-between">
              <div>
                <h1 className="text-2xl font-semibold">{t.agents.title}</h1>
                <p className="text-muted-foreground mt-1 text-sm">
                  {t.agents.description}
                </p>
              </div>
              <Button onClick={handleNewAgent}>
                <PlusIcon className="mr-1.5 h-4 w-4" />
                {t.agents.newAgent}
              </Button>
            </div>
          </header>

          {/* Content */}
          <main className="min-h-0 flex-1">
            <div className="mx-auto w-full max-w-(--container-width-md) py-6">
              {isLoading ? (
                <div className="text-muted-foreground flex h-40 items-center justify-center text-sm">
                  {t.common.loading}
                </div>
              ) : agents.length === 0 ? (
                <Empty>
                  <EmptyHeader>
                    <EmptyMedia variant="icon">
                      <BotIcon />
                    </EmptyMedia>
                    <EmptyTitle>{t.agents.emptyTitle}</EmptyTitle>
                    <EmptyDescription>{t.agents.emptyDescription}</EmptyDescription>
                  </EmptyHeader>
                  <EmptyContent>
                    <Button variant="outline" onClick={handleNewAgent}>
                      <PlusIcon className="mr-1.5 h-4 w-4" />
                      {t.agents.newAgent}
                    </Button>
                  </EmptyContent>
                </Empty>
              ) : (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {agents.map((agent) => (
                    <AgentCard key={agent.name} agent={agent} />
                  ))}
                </div>
              )}
            </div>
          </main>
        </div>
      </WorkspaceBody>
    </WorkspaceContainer>
  );
}
