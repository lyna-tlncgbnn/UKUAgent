import type { Message } from "@langchain/langgraph-sdk";
import type { ScheduledTask, ScheduledTaskRun } from "@/core/scheduled-tasks";

/* ─── helpers ─── */

export function formatDateTime(value: string | null, timeZone = "Asia/Shanghai") {
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

export function messageRole(message: Message) {
  const type = "type" in message ? message.type : undefined;
  if (type === "human") return "用户";
  if (type === "ai") return "Agent";
  if (type === "tool") return "工具";
  return type ?? "消息";
}

export function messageText(message: Message) {
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

export function scheduleLabel(task: ScheduledTask) {
  if (task.schedule_type === "cron") return task.cron_expr ?? "Cron";
  if (task.schedule_type === "interval") return `每 ${Math.round((task.interval_seconds ?? 0) / 60)} 分钟`;
  return "一次性";
}

export function scheduleTypeName(task: ScheduledTask) {
  if (task.schedule_type === "cron") return "Cron";
  if (task.schedule_type === "interval") return "间隔";
  return "一次性";
}

/** Smart time label: shows "下次 xxx" for active tasks, "上次 xxx" for completed/disabled, or nothing */
export function taskTimeHint(task: ScheduledTask): string | null {
  if (task.next_run_at) {
    return `下次 ${formatDateTime(task.next_run_at, task.timezone)}`;
  }
  if (task.last_run_at) {
    return `上次 ${formatDateTime(task.last_run_at, task.timezone)}`;
  }
  return null;
}

/* ─── Status constants & components ─── */

export const TASK_STATUS_COLORS: Record<ScheduledTask["status"], string> = {
  active: "bg-emerald-500",
  paused: "bg-amber-500",
  completed: "bg-muted-foreground/30",
  disabled: "bg-red-500",
};

export const TASK_STATUS_LABELS: Record<ScheduledTask["status"], string> = {
  active: "活跃",
  paused: "已暂停",
  completed: "已完成",
  disabled: "已禁用",
};

export const RUN_STATUS_COLORS: Record<ScheduledTaskRun["status"], string> = {
  success: "bg-emerald-500",
  error: "bg-red-500",
  running: "bg-blue-500 animate-pulse",
  queued: "bg-muted-foreground/30",
  skipped: "bg-muted-foreground/30",
  cancelled: "bg-muted-foreground/30",
};
