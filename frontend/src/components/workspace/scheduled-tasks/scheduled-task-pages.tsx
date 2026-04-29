"use client";

import {
  CalendarClockIcon,
  CirclePauseIcon,
  CirclePlayIcon,
  ClockIcon,
  MessageSquareIcon,
  PlusIcon,
  RefreshCwIcon,
  Trash2Icon,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  useCreateScheduledTask,
  useDeleteScheduledTask,
  usePauseScheduledTask,
  useResumeScheduledTask,
  useRunScheduledTaskNow,
  useScheduledTask,
  useScheduledTaskRuns,
  useScheduledTaskThreadState,
  useScheduledTasks,
} from "@/core/scheduled-tasks";
import type { CreateScheduledTaskRequest, ScheduledTask } from "@/core/scheduled-tasks";
import type { Message } from "@langchain/langgraph-sdk";

function formatDateTime(value: string | null, timeZone = "Asia/Shanghai") {
  if (!value) return "未安排";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "未知时间";
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone,
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function messageRole(message: Message) {
  const type = "type" in message ? message.type : undefined;
  if (type === "human") return "用户";
  if (type === "ai") return "Agent";
  if (type === "tool") return "工具";
  return type ?? "消息";
}

function messageText(message: Message) {
  const content = message.content;
  if (typeof content === "string") return content;
  if (Array.isArray(content)) {
    return content
      .map((part) => {
        if (typeof part === "string") return part;
        if (part && typeof part === "object" && "text" in part && typeof part.text === "string") return part.text;
        return "";
      })
      .filter(Boolean)
      .join("\n");
  }
  return "";
}

function scheduleLabel(task: ScheduledTask) {
  if (task.schedule_type === "cron") return task.cron_expr ?? "Cron";
  if (task.schedule_type === "interval") return `每 ${Math.round((task.interval_seconds ?? 0) / 60)} 分钟`;
  return task.run_at ? `一次性 ${formatDateTime(task.run_at, task.timezone)}` : "一次性";
}

function statusVariant(status: ScheduledTask["status"]) {
  if (status === "active") return "default";
  if (status === "paused") return "secondary";
  if (status === "completed") return "outline";
  return "destructive";
}

function NewTaskDialog() {
  const [open, setOpen] = useState(false);
  const [scheduleType, setScheduleType] = useState<CreateScheduledTaskRequest["schedule_type"]>("cron");
  const createTask = useCreateScheduledTask();

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const payload: CreateScheduledTaskRequest = {
      title: String(form.get("title") ?? ""),
      assistant_id: String(form.get("assistant_id") || "lead_agent"),
      prompt: String(form.get("prompt") ?? ""),
      schedule_type: scheduleType,
      timezone: String(form.get("timezone") || "Asia/Shanghai"),
      cron_expr: scheduleType === "cron" ? String(form.get("cron_expr") ?? "") : null,
      interval_seconds: scheduleType === "interval" ? Number(form.get("interval_seconds") ?? 0) : null,
      run_at: scheduleType === "once" ? String(form.get("run_at") ?? "") : null,
    };
    try {
      await createTask.mutateAsync(payload);
      toast.success("定时任务已创建");
      setOpen(false);
      event.currentTarget.reset();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "创建定时任务失败");
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <PlusIcon className="size-4" />
          新建任务
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>新建定时任务</DialogTitle>
          <DialogDescription>设置自动触发的 agent 任务。</DialogDescription>
        </DialogHeader>
        <form className="grid gap-4" onSubmit={handleSubmit}>
          <Input name="title" placeholder="任务标题" required />
          <Input name="assistant_id" defaultValue="lead_agent" placeholder="智能体 ID" />
          <Textarea name="prompt" placeholder="每次执行时发送给 agent 的内容" required className="min-h-28" />
          <div className="grid gap-3 sm:grid-cols-3">
            <select
              className="border-input bg-background h-9 rounded-md border px-3 text-sm"
              value={scheduleType}
              onChange={(event) => setScheduleType(event.target.value as CreateScheduledTaskRequest["schedule_type"])}
            >
              <option value="cron">Cron</option>
              <option value="interval">间隔</option>
              <option value="once">一次性</option>
            </select>
            <Input name="timezone" defaultValue="Asia/Shanghai" />
            {scheduleType === "cron" && <Input name="cron_expr" defaultValue="0 9 * * *" placeholder="0 9 * * *" />}
            {scheduleType === "interval" && <Input name="interval_seconds" type="number" min={60} defaultValue={3600} />}
            {scheduleType === "once" && <Input name="run_at" type="datetime-local" required />}
          </div>
          <DialogFooter>
            <Button type="submit" disabled={createTask.isPending}>
              创建
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function TaskActions({ task }: { task: ScheduledTask }) {
  const pauseTask = usePauseScheduledTask();
  const resumeTask = useResumeScheduledTask();
  const deleteTask = useDeleteScheduledTask();
  const runNow = useRunScheduledTaskNow();

  async function action(label: string, fn: () => Promise<unknown>) {
    try {
      await fn();
      toast.success(label);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "操作失败");
    }
  }

  return (
    <div className="flex flex-wrap gap-2">
      {task.status === "active" ? (
        <Button size="sm" variant="outline" onClick={() => action("任务已暂停", () => pauseTask.mutateAsync(task.id))}>
          <CirclePauseIcon className="size-4" />
          暂停
        </Button>
      ) : (
        <Button size="sm" variant="outline" onClick={() => action("任务已恢复", () => resumeTask.mutateAsync(task.id))}>
          <CirclePlayIcon className="size-4" />
          恢复
        </Button>
      )}
      <Button size="sm" variant="outline" onClick={() => action("已触发立即运行", () => runNow.mutateAsync(task.id))}>
        <RefreshCwIcon className="size-4" />
        立即运行
      </Button>
      <Button size="sm" variant="outline" onClick={() => action("任务已删除", () => deleteTask.mutateAsync(task.id))}>
        <Trash2Icon className="size-4" />
        删除
      </Button>
    </div>
  );
}

export function ScheduledTasksPage() {
  const { tasks, isLoading, error } = useScheduledTasks();

  return (
    <main className="flex h-full min-w-0 flex-col">
      <header className="border-b px-8 py-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold">定时任务</h1>
            <p className="text-muted-foreground mt-1 text-sm">管理自动运行的 agent 任务。</p>
          </div>
          <NewTaskDialog />
        </div>
      </header>
      <div className="min-h-0 flex-1 overflow-auto p-8">
        {isLoading && <div className="text-muted-foreground text-sm">加载中...</div>}
        {error && <div className="text-destructive text-sm">加载定时任务失败。</div>}
        {!isLoading && tasks.length === 0 && (
          <div className="border-border bg-muted/20 rounded-lg border p-8 text-sm text-muted-foreground">
            还没有定时任务。
          </div>
        )}
        <div className="grid gap-4 xl:grid-cols-2">
          {tasks.map((task) => (
            <Card key={task.id} className="rounded-lg">
              <CardHeader>
                <CardTitle>
                  <Link href={`/workspace/scheduled-tasks/${task.id}`}>{task.title}</Link>
                </CardTitle>
                <CardDescription>{task.prompt}</CardDescription>
                <CardAction>
                  <Badge variant={statusVariant(task.status)}>{task.status}</Badge>
                </CardAction>
              </CardHeader>
              <CardContent className="grid gap-4">
                <div className="grid gap-2 text-sm sm:grid-cols-3">
                  <div className="flex items-center gap-2">
                    <CalendarClockIcon className="text-muted-foreground size-4" />
                    {scheduleLabel(task)}
                  </div>
                  <div className="flex items-center gap-2">
                    <ClockIcon className="text-muted-foreground size-4" />
                    {formatDateTime(task.next_run_at, task.timezone)}
                  </div>
                  <div className="text-muted-foreground">{task.assistant_id}</div>
                </div>
                {task.last_error && <div className="text-destructive text-sm">{task.last_error}</div>}
                <TaskActions task={task} />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </main>
  );
}

export function ScheduledTaskDetailPage({ taskId }: { taskId: string }) {
  const { task, isLoading, error } = useScheduledTask(taskId);
  const { runs } = useScheduledTaskRuns(taskId);
  const latestRun = useMemo(() => runs[0], [runs]);
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
      <header className="border-b px-8 py-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold">{task.title}</h1>
            <p className="text-muted-foreground mt-1 text-sm">{scheduleLabel(task)} · {task.timezone}</p>
          </div>
          <TaskActions task={task} />
        </div>
      </header>
      <div className="min-h-0 flex-1 overflow-auto p-8">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
          <section className="grid gap-4">
            <Card className="rounded-lg">
              <CardHeader>
                <CardTitle>任务内容</CardTitle>
                <CardDescription>{task.assistant_id}</CardDescription>
              </CardHeader>
              <CardContent className="whitespace-pre-wrap text-sm">{task.prompt}</CardContent>
            </Card>
            <Card className="rounded-lg">
              <CardHeader>
                <CardTitle>执行历史</CardTitle>
                <CardDescription>点击有对话线程的记录进入对应聊天。</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-2">
                {runs.length === 0 && <div className="text-muted-foreground text-sm">还没有执行记录。</div>}
                {runs.map((run) => (
                  <button
                    key={run.id}
                    className="hover:bg-muted data-[selected=true]:bg-muted flex w-full items-center justify-between gap-4 rounded-md border px-4 py-3 text-left text-sm"
                    onClick={() => {
                      if (run.thread_id) {
                        setSelectedRunId(run.id);
                      }
                    }}
                    disabled={!run.thread_id}
                    data-selected={selectedRun?.id === run.id}
                  >
                    <span>{formatDateTime(run.started_at ?? run.scheduled_for, task.timezone)}</span>
                    <span className="text-muted-foreground">{run.trigger_type}</span>
                    <Badge variant={run.status === "success" ? "default" : run.status === "error" ? "destructive" : "secondary"}>
                      {run.status}
                    </Badge>
                  </button>
                ))}
              </CardContent>
            </Card>
            <Card className="rounded-lg">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <MessageSquareIcon className="size-5" />
                  执行对话
                </CardTitle>
                <CardDescription>
                  {selectedRun?.thread_id ? formatDateTime(selectedRun.started_at ?? selectedRun.scheduled_for, task.timezone) : "暂无可查看的对话"}
                </CardDescription>
              </CardHeader>
              <CardContent className="grid gap-3">
                {isLoadingThreadState && <div className="text-muted-foreground text-sm">加载对话中...</div>}
                {threadStateError && <div className="text-destructive text-sm">加载执行对话失败。</div>}
                {!isLoadingThreadState && !threadStateError && selectedMessages.length === 0 && (
                  <div className="text-muted-foreground text-sm">这次执行还没有可展示的消息。</div>
                )}
                {selectedMessages.map((message, index) => {
                  const text = messageText(message);
                  if (!text) return null;
                  return (
                    <div key={message.id ?? index} className="rounded-md border p-3 text-sm">
                      <div className="text-muted-foreground mb-1 text-xs">{messageRole(message)}</div>
                      <div className="whitespace-pre-wrap">{text}</div>
                    </div>
                  );
                })}
              </CardContent>
            </Card>
          </section>
          <aside className="grid content-start gap-4">
            <Card className="rounded-lg">
              <CardHeader>
                <CardTitle>最近一次执行</CardTitle>
                <CardDescription>{latestRun ? formatDateTime(latestRun.started_at ?? latestRun.scheduled_for, task.timezone) : "暂无"}</CardDescription>
              </CardHeader>
              <CardContent className="grid gap-2 text-sm">
                <div>状态：{latestRun?.status ?? "无"}</div>
                <div>下次执行：{formatDateTime(task.next_run_at, task.timezone)}</div>
                {task.last_error && <div className="text-destructive">{task.last_error}</div>}
              </CardContent>
            </Card>
          </aside>
        </div>
      </div>
    </main>
  );
}
