import { getBackendBaseURL } from "@/core/config";

import type {
  ScheduledTaskThreadState,
  CreateScheduledTaskRequest,
  ScheduledTask,
  ScheduledTaskRun,
  UpdateScheduledTaskRequest,
} from "./types";

async function readErrorDetail(response: Response, fallback: string) {
  const error = await response.json().catch(() => ({ detail: fallback }));
  return error.detail ?? fallback;
}

export async function listScheduledTasks(): Promise<ScheduledTask[]> {
  const response = await fetch(`${getBackendBaseURL()}/api/scheduled-tasks`);
  if (!response.ok) {
    throw new Error(await readErrorDetail(response, "Failed to load scheduled tasks"));
  }
  return response.json() as Promise<ScheduledTask[]>;
}

export async function createScheduledTask(
  request: CreateScheduledTaskRequest,
): Promise<ScheduledTask> {
  const response = await fetch(`${getBackendBaseURL()}/api/scheduled-tasks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    throw new Error(await readErrorDetail(response, "Failed to create scheduled task"));
  }
  return response.json() as Promise<ScheduledTask>;
}

export async function getScheduledTask(taskId: string): Promise<ScheduledTask> {
  const response = await fetch(`${getBackendBaseURL()}/api/scheduled-tasks/${taskId}`);
  if (!response.ok) {
    throw new Error(await readErrorDetail(response, "Failed to load scheduled task"));
  }
  return response.json() as Promise<ScheduledTask>;
}

export async function updateScheduledTask(
  taskId: string,
  request: UpdateScheduledTaskRequest,
): Promise<ScheduledTask> {
  const response = await fetch(`${getBackendBaseURL()}/api/scheduled-tasks/${taskId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    throw new Error(await readErrorDetail(response, "Failed to update scheduled task"));
  }
  return response.json() as Promise<ScheduledTask>;
}

export async function deleteScheduledTask(taskId: string): Promise<void> {
  const response = await fetch(`${getBackendBaseURL()}/api/scheduled-tasks/${taskId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error(await readErrorDetail(response, "Failed to delete scheduled task"));
  }
}

export async function pauseScheduledTask(taskId: string): Promise<ScheduledTask> {
  const response = await fetch(`${getBackendBaseURL()}/api/scheduled-tasks/${taskId}/pause`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(await readErrorDetail(response, "Failed to pause scheduled task"));
  }
  return response.json() as Promise<ScheduledTask>;
}

export async function resumeScheduledTask(taskId: string): Promise<ScheduledTask> {
  const response = await fetch(`${getBackendBaseURL()}/api/scheduled-tasks/${taskId}/resume`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(await readErrorDetail(response, "Failed to resume scheduled task"));
  }
  return response.json() as Promise<ScheduledTask>;
}

export async function runScheduledTaskNow(taskId: string): Promise<ScheduledTaskRun> {
  const response = await fetch(`${getBackendBaseURL()}/api/scheduled-tasks/${taskId}/run-now`, {
    method: "POST",
  });
  if (!response.ok) {
    throw new Error(await readErrorDetail(response, "Failed to run scheduled task"));
  }
  return response.json() as Promise<ScheduledTaskRun>;
}

export async function listScheduledTaskRuns(taskId: string): Promise<ScheduledTaskRun[]> {
  const response = await fetch(`${getBackendBaseURL()}/api/scheduled-tasks/${taskId}/runs`);
  if (!response.ok) {
    throw new Error(await readErrorDetail(response, "Failed to load scheduled task runs"));
  }
  return response.json() as Promise<ScheduledTaskRun[]>;
}

export async function getScheduledTaskThreadState(threadId: string): Promise<ScheduledTaskThreadState> {
  const response = await fetch(`${getBackendBaseURL()}/api/threads/${encodeURIComponent(threadId)}/state`);
  if (!response.ok) {
    throw new Error(await readErrorDetail(response, "Failed to load scheduled task conversation"));
  }
  return response.json() as Promise<ScheduledTaskThreadState>;
}
