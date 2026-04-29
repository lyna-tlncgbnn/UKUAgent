import type { Message } from "@langchain/langgraph-sdk";

export type ScheduledTaskStatus = "active" | "paused" | "completed" | "disabled";
export type ScheduledTaskScheduleType = "once" | "interval" | "cron";

export type ScheduledTask = {
  id: string;
  user_id: string;
  title: string;
  description: string | null;
  assistant_id: string;
  prompt: string;
  schedule_type: ScheduledTaskScheduleType;
  timezone: string;
  cron_expr: string | null;
  interval_seconds: number | null;
  run_at: string | null;
  next_run_at: string | null;
  status: ScheduledTaskStatus;
  concurrency_policy: string;
  thread_policy: string;
  thread_id: string | null;
  last_run_at: string | null;
  last_success_at: string | null;
  last_error: string | null;
  failure_count: number;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type ScheduledTaskRun = {
  id: string;
  task_id: string;
  user_id: string;
  thread_id: string | null;
  run_id: string | null;
  scheduled_for: string | null;
  started_at: string | null;
  finished_at: string | null;
  status: "queued" | "running" | "success" | "error" | "skipped" | "cancelled";
  trigger_type: "schedule" | "manual" | "conversation";
  error: string | null;
  result_summary: string | null;
  created_at: string;
  updated_at: string;
};

export type CreateScheduledTaskRequest = {
  title: string;
  description?: string | null;
  assistant_id?: string;
  prompt: string;
  schedule_type: ScheduledTaskScheduleType;
  timezone?: string;
  cron_expr?: string | null;
  interval_seconds?: number | null;
  run_at?: string | null;
  metadata?: Record<string, unknown>;
};

export type UpdateScheduledTaskRequest = Partial<CreateScheduledTaskRequest>;

export type ScheduledTaskThreadState = {
  values: {
    messages?: Message[];
    title?: string;
  };
};
