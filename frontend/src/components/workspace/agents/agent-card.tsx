"use client";

import {
  BotIcon,
  MessageSquareIcon,
  ShieldIcon,
  Trash2Icon,
  UsersIcon,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useDeleteAgent } from "@/core/agents";
import type { Agent } from "@/core/agents";
import { useI18n } from "@/core/i18n/hooks";

interface AgentCardProps {
  agent: Agent;
}

// Generate a deterministic accent color from agent slug
function getAccentColor(slug: string) {
  const palette = [
    { bg: "from-blue-500/12 to-blue-500/4", text: "text-blue-600 dark:text-blue-400", ring: "ring-blue-500/10" },
    { bg: "from-emerald-500/12 to-emerald-500/4", text: "text-emerald-600 dark:text-emerald-400", ring: "ring-emerald-500/10" },
    { bg: "from-violet-500/12 to-violet-500/4", text: "text-violet-600 dark:text-violet-400", ring: "ring-violet-500/10" },
    { bg: "from-amber-500/12 to-amber-500/4", text: "text-amber-600 dark:text-amber-400", ring: "ring-amber-500/10" },
    { bg: "from-rose-500/12 to-rose-500/4", text: "text-rose-600 dark:text-rose-400", ring: "ring-rose-500/10" },
    { bg: "from-cyan-500/12 to-cyan-500/4", text: "text-cyan-600 dark:text-cyan-400", ring: "ring-cyan-500/10" },
  ];
  let hash = 0;
  for (let i = 0; i < slug.length; i++) {
    hash = (hash * 31 + slug.charCodeAt(i)) | 0;
  }
  return palette[Math.abs(hash) % palette.length]!;
}

export function AgentCard({ agent }: AgentCardProps) {
  const { t } = useI18n();
  const router = useRouter();
  const deleteAgent = useDeleteAgent();
  const [deleteOpen, setDeleteOpen] = useState(false);
  const accent = getAccentColor(agent.slug);

  function handleChat() {
    router.push(`/workspace/agents/${agent.slug}/chats/new`);
  }

  async function handleDelete() {
    try {
      await deleteAgent.mutateAsync(agent.slug);
      toast.success(t.agents.deleteSuccess);
      setDeleteOpen(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <>
      <div className="group relative flex flex-col overflow-hidden rounded-2xl border border-border/50 bg-card transition-all duration-200 hover:border-border hover:shadow-lg hover:shadow-black/[0.03]">
        {/* ── Card body ────────────────────────────────────────────── */}
        <div className="flex flex-1 flex-col gap-3 p-5">
          {/* Icon + name row */}
          <div className="flex items-start gap-3">
            <div
              className={`flex size-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ${accent.bg} ring-1 ${accent.ring}`}
            >
              <BotIcon className={`size-5 ${accent.text}`} />
            </div>
            <div className="min-w-0 flex-1">
              <h3 className="truncate text-[15px] font-semibold leading-snug">
                {agent.name}
              </h3>
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                <Badge
                  variant="secondary"
                  className="rounded-full px-2 py-0.5 text-[10px] font-medium"
                >
                  {agent.visibility === "org_shared" ? (
                    <>
                      <UsersIcon className="mr-1 size-2.5" />
                      {t.agents.visibilityOrgShared}
                    </>
                  ) : (
                    <>
                      <ShieldIcon className="mr-1 size-2.5" />
                      {t.agents.visibilityPrivate}
                    </>
                  )}
                </Badge>
                {agent.model && (
                  <Badge
                    variant="outline"
                    className="rounded-full px-2 py-0.5 text-[10px] font-medium"
                  >
                    {agent.model}
                  </Badge>
                )}
              </div>
            </div>
          </div>

          {/* Description */}
          {agent.description && (
            <p className="text-muted-foreground line-clamp-2 text-[13px] leading-relaxed">
              {agent.description}
            </p>
          )}

          {/* Tool groups */}
          {agent.tool_groups && agent.tool_groups.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {agent.tool_groups.map((group) => (
                <span
                  key={group}
                  className="bg-muted/60 text-muted-foreground inline-flex rounded-md px-2 py-0.5 text-[10px] font-medium"
                >
                  {group}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* ── Card footer ──────────────────────────────────────────── */}
        <div className="flex items-center gap-2 border-t border-border/40 px-4 py-3">
          <Button
            size="sm"
            variant="ghost"
            className="h-8 flex-1 rounded-lg text-xs font-medium hover:bg-primary/5 hover:text-primary"
            onClick={handleChat}
          >
            <MessageSquareIcon className="mr-1.5 size-3.5" />
            {t.agents.chat}
          </Button>
          {agent.is_owner && (
            <Button
              size="icon"
              variant="ghost"
              className="text-muted-foreground hover:text-destructive size-8 shrink-0 rounded-lg"
              onClick={() => setDeleteOpen(true)}
              title={t.agents.delete}
            >
              <Trash2Icon className="size-3.5" />
            </Button>
          )}
        </div>
      </div>

      {/* Delete Confirm */}
      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t.agents.delete}</DialogTitle>
            <DialogDescription>{t.agents.deleteConfirm}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteOpen(false)}
              disabled={deleteAgent.isPending}
            >
              {t.common.cancel}
            </Button>
            <Button
              variant="destructive"
              onClick={handleDelete}
              disabled={deleteAgent.isPending}
            >
              {deleteAgent.isPending ? t.common.loading : t.common.delete}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
