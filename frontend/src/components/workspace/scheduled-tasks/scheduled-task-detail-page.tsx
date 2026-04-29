"use client";

import {
  ArrowLeftIcon,
  MessageSquareIcon,
  WrenchIcon,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
  useScheduledTask,
  useScheduledTaskRuns,
  useScheduledTaskThreadState,
} from "@/core/scheduled-tasks";
import type { ScheduledTask } from "@/core/scheduled-tasks";

import { DeleteConfirmDialog, TaskActionDropdown } from "./task-action-dropdown";
import {
  RUN_STATUS_COLORS,
  TASK_STATUS_COLORS,
  formatDateTime,
  messageRole,
  messageText,
  scheduleLabel,
  scheduleTypeName,
} from "./lib";

/* ─── StatusDot (local) ─── */

function StatusDot({ status }: { status: ScheduledTask["status"] }) {
  const colors: Record<ScheduledTask["status"], string> = {
    active: "bg-emerald-500",
    paused: "bg-amber-500",
    completed: "bg-muted-foreground/30",
    disabled: "bg-red-500",
  };
  const labels: Record<ScheduledTask["status"], string> = {
    active: "活跃",
    paused: "已暂停",
    completed: "已完成",
    disabled: "已禁用",
  };
  return (
    <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
      <span className={`size-2 shrink-0 rounded-full ${colors[status]}`} />
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

  if (isLoading) return <main className="p-8 text-sm text-muted-foreground">加载中...</main>;
  if (error || !task) return <main className="p-8 text-sm text-destructive">加载定时任务失败。</main>;

  return (
    <main className="flex h-full min-w-0 flex-col">
      {/* Header */}
      <header className="border-b px-8 py-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <Link
              href="/workspace/scheduled-tasks"
              className="text-muted-foreground hover:text-foreground mb-2 inline-flex items-center gap-1 text-sm transition-colors"
            >
              <ArrowLeftIcon className="size-3.5" />
              返回
            </Link>
            <h1 className="text-2xl font-semibold">{task.title}</h1>
            <div className="text-muted-foreground mt-1 flex items-center gap-2 text-sm">
              <StatusDot status={task.status} />
              <span>·</span>
              <span>{scheduleLabel(task)}</span>
              <span>·</span>
              <span>{task.timezone}</span>
            </div>
          </div>
          <TaskActionDropdown task={task} onDeleteRequest={() => setTaskToDelete(task)} />
        </div>
      </header>

      {/* Tabs */}
      <div className="min-h-0 flex-1 overflow-auto">
        <div className="px-8 pt-6">
          <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as DetailTab)}>
            <TabsList variant="line">
              <TabsTrigger value="overview">概览</TabsTrigger>
              <TabsTrigger value="history">执行历史</TabsTrigger>
              <TabsTrigger value="conversation">执行对话</TabsTrigger>
            </TabsList>

            {/* Overview Tab */}
            <TabsContent value="overview" className="pt-4">
              <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_280px]">
                <div className="space-y-6">
                  {/* Schedule config */}
                  <div>
                    <div className="mb-3 text-sm font-medium">调度配置</div>
                    <div className="grid gap-3 text-sm">
                      <div className="flex items-center justify-between">
                        <span className="text-muted-foreground">调度类型</span>
                        <span>{scheduleTypeName(task)}</span>
                      </div>
                      {task.schedule_type === "cron" && (
                        <div className="flex items-center justify-between">
                          <span className="text-muted-foreground">Cron 表达式</span>
                          <code className="bg-muted rounded px-2 py-0.5 font-mono text-xs">{task.cron_expr}</code>
                        </div>
                      )}
                      {task.schedule_type === "interval" && (
                        <div className="flex items-center justify-between">
                          <span className="text-muted-foreground">间隔时间</span>
                          <span>{Math.round((task.interval_seconds ?? 0) / 60)} 分钟</span>
                        </div>
                      )}
                      {task.schedule_type === "once" && task.run_at && (
                        <div className="flex items-center justify-between">
                          <span className="text-muted-foreground">执行时间</span>
                          <span>{formatDateTime(task.run_at, task.timezone)}</span>
                        </div>
                      )}
                      <div className="flex items-center justify-between">
                        <span className="text-muted-foreground">时区</span>
                        <span>{task.timezone}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-muted-foreground">智能体</span>
                        <span>{task.assistant_id}</span>
                      </div>
                    </div>
                  </div>

                  {/* Prompt */}
                  <div>
                    <div className="mb-3 text-sm font-medium">任务内容</div>
                    <div className="bg-muted/50 rounded-lg p-4 text-sm whitespace-pre-wrap">
                      {task.prompt}
                    </div>
                  </div>
                </div>

                {/* Sidebar summary */}
                <aside>
                  <Card className="rounded-lg">
                    <CardHeader>
                      <CardTitle className="text-sm">执行摘要</CardTitle>
                    </CardHeader>
                    <CardContent className="grid gap-3 text-sm">
                      <div className="flex items-center justify-between">
                        <span className="text-muted-foreground">状态</span>
                        <StatusDot status={task.status} />
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-muted-foreground">下次执行</span>
                        <span>{formatDateTime(task.next_run_at, task.timezone)}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-muted-foreground">上次成功</span>
                        <span>{formatDateTime(task.last_success_at, task.timezone)}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-muted-foreground">失败次数</span>
                        <span>{task.failure_count}</span>
                      </div>
                      {task.last_error && (
                        <div className="text-destructive rounded-md bg-destructive/10 p-2 text-xs">
                          {task.last_error}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </aside>
              </div>
            </TabsContent>

            {/* History Tab */}
            <TabsContent value="history" className="pt-4">
              {runs.length === 0 && (
                <div className="text-muted-foreground py-8 text-center text-sm">还没有执行记录。</div>
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
                          {formatDateTime(run.started_at ?? run.scheduled_for, task.timezone)}
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
                            查看对话
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
                <div className="text-muted-foreground py-8 text-center text-sm">暂无可查看的对话。</div>
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
                        <SelectValue placeholder="选择执行记录" />
                      </SelectTrigger>
                      <SelectContent>
                        {runnableRuns.map((run) => (
                          <SelectItem key={run.id} value={run.id}>
                            {formatDateTime(run.started_at ?? run.scheduled_for, task.timezone)} · {run.status}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  {/* Messages */}
                  {isLoadingThreadState && <div className="text-muted-foreground text-sm">加载对话中...</div>}
                  {threadStateError && <div className="text-destructive text-sm">加载执行对话失败。</div>}
                  {!isLoadingThreadState && !threadStateError && selectedMessages.length === 0 && (
                    <div className="text-muted-foreground py-8 text-center text-sm">这次执行还没有可展示的消息。</div>
                  )}
                  <div className="space-y-3 pb-8">
                    {selectedMessages.map((message, index) => {
                      const text = messageText(message);
                      if (!text) return null;
                      const role = messageRole(message);
                      const isUser = role === "用户";
                      const isTool = role === "工具";

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
      </div>

      <DeleteConfirmDialog taskToDelete={taskToDelete} onClear={() => setTaskToDelete(null)} />
    </main>
  );
}
