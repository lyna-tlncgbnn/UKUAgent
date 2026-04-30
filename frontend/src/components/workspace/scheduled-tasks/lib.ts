import type { Message } from "@langchain/langgraph-sdk";
import type { ScheduledTask, ScheduledTaskRun } from "@/core/scheduled-tasks";
import type { Translations } from "@/core/i18n/locales/types";

type ST = Translations["scheduledTasks"];

/* ─── helpers ─── */

export function formatDateTime(value: string | null, timeZone = "Asia/Shanghai", locale = "zh-CN", t?: ST) {
  if (!value) return t?.notScheduled ?? "未安排";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return t?.unknownTime ?? "未知时间";
  return new Intl.DateTimeFormat(locale, {
    timeZone,
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function messageRole(message: Message, t: ST) {
  const type = "type" in message ? message.type : undefined;
  if (type === "human") return t.roleUser;
  if (type === "ai") return "Agent";
  if (type === "tool") return t.roleTool;
  return t.roleMessage;
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

export function scheduleLabel(task: ScheduledTask, t: ST) {
  if (task.schedule_type === "cron") return task.cron_expr ?? "Cron";
  if (task.schedule_type === "interval") return t.scheduleLabelInterval.replace("{minutes}", String(Math.round((task.interval_seconds ?? 0) / 60)));
  return t.scheduleLabelOnce;
}

export function scheduleTypeName(task: ScheduledTask, t: ST) {
  if (task.schedule_type === "cron") return t.scheduleTypeNameCron;
  if (task.schedule_type === "interval") return t.scheduleTypeNameInterval;
  return t.scheduleTypeNameOnce;
}

/** Smart time label: shows "下次 xxx" for active tasks, "上次 xxx" for completed/disabled, or nothing */
export function taskTimeHint(task: ScheduledTask, t: ST, locale = "zh-CN"): string | null {
  if (task.next_run_at) {
    return t.nextRunAt.replace("{time}", formatDateTime(task.next_run_at, task.timezone, locale, t));
  }
  if (task.last_run_at) {
    return t.lastRunAt.replace("{time}", formatDateTime(task.last_run_at, task.timezone, locale, t));
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

export function getTaskStatusLabels(t: ST): Record<ScheduledTask["status"], string> {
  return {
    active: t.statusActive,
    paused: t.statusPaused,
    completed: t.statusCompleted,
    disabled: t.statusDisabled,
  };
}

export const RUN_STATUS_COLORS: Record<ScheduledTaskRun["status"], string> = {
  success: "bg-emerald-500",
  error: "bg-red-500",
  running: "bg-blue-500 animate-pulse",
  queued: "bg-muted-foreground/30",
  skipped: "bg-muted-foreground/30",
  cancelled: "bg-muted-foreground/30",
};
