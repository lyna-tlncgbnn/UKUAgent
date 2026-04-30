"use client";

import {
  ArrowLeftIcon,
  MessageSquareIcon,
  WrenchIcon,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Item, ItemActions, ItemContent, ItemDescription, ItemMedia, ItemTitle } from "@/components/ui/item";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  WorkspaceBody,
  WorkspaceContainer,
  WorkspaceHeader,
} from "@/components/workspace/workspace-container";
import { useI18n } from "@/core/i18n/hooks";
import {
  useScheduledTask,
  useScheduledTaskRuns,
  useScheduledTaskThreadState,
} from "@/core/scheduled-tasks";
import type { ScheduledTask } from "@/core/scheduled-tasks";

import { DeleteConfirmDialog, TaskActionDropdown } from "./task-action-dropdown";
import {
  RUN_STATUS_COLORS,
  formatDateTime,
  getTaskStatusLabels,
  messageRole,
  messageText,
  scheduleLabel,
  scheduleTypeName,
} from "./lib";

/* ─── StatusDot (local) ─── */

const STATUS_DOT_COLORS: Record<ScheduledTask["status"], string> = {
  active: "bg-emerald-500",
  paused: "bg-amber-500",
  completed: "bg-muted-foreground/30",
  disabled: "bg-red-500",
};

function StatusDot({ status, labels }: { status: ScheduledTask["status"]; labels: Record<ScheduledTask["status"], string> }) {
  return (
    <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
      <span className={`size-2 shrink-0 rounded-full ${STATUS_DOT_COLORS[status]}`} />
      {labels[status]}
    </span>
  );
}

function RunStatusDot({ status }: { status: string }) {
  return (
    <span className={`size-2 shrink-0 rounded-full ${RUN_STATUS_COLORS[status as keyof typeof RUN_STATUS_COLORS] ?? "bg-muted-foreground/30"}`} />
  );
}

/* ─── DetailTab type ─── */

type DetailTab = "overview" | "history" | "conversation";

/* ─── ScheduledTaskDetailPage ─── */

export function ScheduledTaskDetailPage({ taskId }: { taskId: string }) {
  const { t, locale } = useI18n();
  const st = t.scheduledTasks;
  const statusLabels = useMemo(() => getTaskStatusLabels(st), [st]);
  const { task, isLoading, error } = useScheduledTask(taskId);
  const { runs } = useScheduledTaskRuns(taskId);
  const [activeTab, setActiveTab] = useState<DetailTab>("overview");
  const [taskToDelete, setTaskToDelete] = useState<ScheduledTask | null>(null);
  const runnableRuns = useMemo(() => runs.filter((run) => run.thread_id), [runs]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const selectedRun = useMemo(
    () => runs.find((run) => run.id === selectedRunId) ?? runnableRuns[0] ?? null,
    [runnableRuns, runs, selectedRunId],
  );
  const { state: selectedThreadState, isLoading: isLoadingThreadState, error: threadStateError } =
    useScheduledTaskThreadState(selectedRun?.thread_id);
  const selectedMessages = selectedThreadState?.values.messages ?? [];

  useEffect(() => {
    if (!selectedRunId && runnableRuns[0]) {
      setSelectedRunId(runnableRuns[0].id);
    }
  }, [runnableRuns, selectedRunId]);

  if (isLoading) return <main className="p-8 text-sm text-muted-foreground">{st.loading}</main>;
  if (error || !task) return <main className="p-8 text-sm text-destructive">{st.loadError}</main>;

  return (
    <WorkspaceContainer>
      <WorkspaceHeader />
      <WorkspaceBody>
        <div className="flex size-full flex-col">
          {/* Page header */}
          <header className="flex shrink-0 items-center justify-center pt-8">
            <div className="flex w-full max-w-(--container-width-md) items-start justify-between gap-4">
              <div>
                <Link
                  href="/workspace/scheduled-tasks"
                  className="text-muted-foreground hover:text-foreground mb-2 inline-flex items-center gap-1 text-sm transition-colors"
                >
                  <ArrowLeftIcon className="size-3.5" />
                  {st.back}
                </Link>
                <h1 className="text-2xl font-semibold">{task.title}</h1>
                <div className="text-muted-foreground mt-1 flex items-center gap-2 text-sm">
                  <StatusDot status={task.status} labels={statusLabels} />
                  <span>·</span>
                  <span>{scheduleLabel(task, st)}</span>
                  <span>·</span>
                  <span>{task.timezone}</span>
                </div>
              </div>
              <TaskActionDropdown task={task} onDeleteRequest={() => setTaskToDelete(task)} />
            </div>
          </header>

          {/* Content */}
          <main className="min-h-0 flex-1">
            <div className="mx-auto w-full max-w-(--container-width-md) py-4">
              <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as DetailTab)}>
                <TabsList variant="line">
                  <TabsTrigger value="overview">{st.tabOverview}</TabsTrigger>
                  <TabsTrigger value="history">{st.tabHistory}</TabsTrigger>
                  <TabsTrigger value="conversation">{st.tabConversation}</TabsTrigger>
                </TabsList>

                {/* Overview Tab */}
                <TabsContent value="overview" className="pt-4">
                  <div className="grid gap-6 md:grid-cols-[minmax(0,1fr)_240px]">
                    <div className="space-y-6">
                      {/* Schedule config */}
                      <div>
                        <div className="mb-3 text-sm font-medium">{st.scheduleConfig}</div>
                        <div className="grid gap-3 text-sm">
                          <div className="flex items-center justify-between">
                            <span className="text-muted-foreground">{st.scheduleType}</span>
                            <span>{scheduleTypeName(task, st)}</span>
                          </div>
                          {task.schedule_type === "cron" && (
                            <div className="flex items-center justify-between">
                              <span className="text-muted-foreground">{st.cronExpression}</span>
                              <code className="bg-muted rounded px-2 py-0.5 font-mono text-xs">{task.cron_expr}</code>
                            </div>
                          )}
                          {task.schedule_type === "interval" && (
                            <div className="flex items-center justify-between">
                              <span className="text-muted-foreground">{st.intervalTime}</span>
                              <span>{st.minutesShort.replace("{count}", String(Math.round((task.interval_seconds ?? 0) / 60)))}</span>
                            </div>
                          )}
                          {task.schedule_type === "once" && task.run_at && (
                            <div className="flex items-center justify-between">
                              <span className="text-muted-foreground">{st.executionTime}</span>
                              <span>{formatDateTime(task.run_at, task.timezone, locale, st)}</span>
                            </div>
                          )}
                          <div className="flex items-center justify-between">
                            <span className="text-muted-foreground">{st.timezone}</span>
                            <span>{task.timezone}</span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-muted-foreground">{st.agent}</span>
                            <span>{task.assistant_id}</span>
                          </div>
                        </div>
                      </div>

                      {/* Prompt */}
                      <div>
                        <div className="mb-3 text-sm font-medium">{st.taskContent}</div>
                        <div className="bg-muted/50 rounded-lg p-4 text-sm whitespace-pre-wrap">
                          {task.prompt}
                        </div>
                      </div>
                    </div>

                    {/* Sidebar summary */}
                    <aside>
                      <div className="rounded-lg border p-4">
                        <div className="mb-3 text-sm font-medium">{st.executionSummary}</div>
                        <div className="grid gap-3 text-sm">
                          <div className="flex items-center justify-between">
                            <span className="text-muted-foreground">{st.status}</span>
                            <StatusDot status={task.status} labels={statusLabels} />
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-muted-foreground">{st.nextExecution}</span>
                            <span>{formatDateTime(task.next_run_at, task.timezone, locale, st)}</span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-muted-foreground">{st.lastSuccess}</span>
                            <span>{formatDateTime(task.last_success_at, task.timezone, locale, st)}</span>
                          </div>
                          <div className="flex items-center justify-between">
                            <span className="text-muted-foreground">{st.failureCount}</span>
                            <span>{task.failure_count}</span>
                          </div>
                          {task.last_error && (
                            <div className="text-destructive rounded-md bg-destructive/10 p-2 text-xs">
                              {task.last_error}
                            </div>
                          )}
                        </div>
                      </div>
                    </aside>
                  </div>
                </TabsContent>

                {/* History Tab */}
                <TabsContent value="history" className="pt-4">
                  {runs.length === 0 && (
                    <div className="text-muted-foreground py-8 text-center text-sm">{st.noExecutionRecords}</div>
                  )}
                  {runs.length > 0 && (
                    <div className="flex flex-col gap-2">
                      {runs.map((run) => (
                        <Item
                          key={run.id}
                          variant="outline"
                          size="sm"
                          className="w-full rounded-lg transition-colors hover:bg-accent/50"
                        >
                          <ItemMedia>
                            <RunStatusDot status={run.status} />
                          </ItemMedia>
                          <ItemContent>
                            <ItemTitle>
                              {formatDateTime(run.started_at ?? run.scheduled_for, task.timezone, locale, st)}
                            </ItemTitle>
                            <ItemDescription>
                              {run.trigger_type}
                            </ItemDescription>
                          </ItemContent>
                          <ItemActions>
                            {run.thread_id && (
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => {
                                  setSelectedRunId(run.id);
                                  setActiveTab("conversation");
                                }}
                              >
                                <MessageSquareIcon className="size-3.5" />
                                {st.viewConversation}
                              </Button>
                            )}
                          </ItemActions>
                        </Item>
                      ))}
                    </div>
                  )}
                </TabsContent>

                {/* Conversation Tab */}
                <TabsContent value="conversation" className="pt-4">
                  {runnableRuns.length === 0 && (
                    <div className="text-muted-foreground py-8 text-center text-sm">{st.noConversation}</div>
                  )}
                  {runnableRuns.length > 0 && (
                    <>
                      {/* Run selector */}
                      <div className="mb-4">
                        <Select
                          value={selectedRunId ?? undefined}
                          onValueChange={setSelectedRunId}
                        >
                          <SelectTrigger className="w-[260px]">
                            <SelectValue placeholder={st.selectRun} />
                          </SelectTrigger>
                          <SelectContent>
                            {runnableRuns.map((run) => (
                              <SelectItem key={run.id} value={run.id}>
                                {formatDateTime(run.started_at ?? run.scheduled_for, task.timezone, locale, st)} · {run.status}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>

                      {/* Messages */}
                      {isLoadingThreadState && <div className="text-muted-foreground text-sm">{st.loadingConversation}</div>}
                      {threadStateError && <div className="text-destructive text-sm">{st.loadConversationError}</div>}
                      {!isLoadingThreadState && !threadStateError && selectedMessages.length === 0 && (
                        <div className="text-muted-foreground py-8 text-center text-sm">{st.noMessages}</div>
                      )}
                      <div className="space-y-3 pb-8">
                        {selectedMessages.map((message, index) => {
                          const text = messageText(message);
                          if (!text) return null;
                          const role = messageRole(message, st);
                          const isUser = role === st.roleUser;
                          const isTool = role === st.roleTool;

                          if (isTool) {
                            return (
                              <div key={message.id ?? index} className="flex justify-center">
                                <div className="bg-muted/50 max-w-[80%] rounded-lg px-3 py-2 text-sm">
                                  <div className="text-muted-foreground mb-1 flex items-center gap-1 text-xs">
                                    <WrenchIcon className="size-3" />
                                    {role}
                                  </div>
                                  <div className="whitespace-pre-wrap">{text}</div>
                                </div>
                              </div>
                            );
                          }

                          return (
                            <div key={message.id ?? index} className={`flex ${isUser ? "justify-start" : "justify-end"}`}>
                              <div
                                className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm ${
                                  isUser
                                    ? "bg-muted rounded-tl-sm"
                                    : "bg-primary/10 rounded-tr-sm"
                                }`}
                              >
                                <div className="text-muted-foreground mb-1 text-xs">{role}</div>
                                <div className="whitespace-pre-wrap">{text}</div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </>
                  )}
                </TabsContent>
              </Tabs>
            </div>
          </main>

          <DeleteConfirmDialog taskToDelete={taskToDelete} onClear={() => setTaskToDelete(null)} />
        </div>
      </WorkspaceBody>
    </WorkspaceContainer>
  );
}
