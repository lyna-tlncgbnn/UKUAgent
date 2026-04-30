import { getBackendBaseURL } from "../config";

import type { AgentThread } from "./types";

type ThreadSearchBody = {
  metadata?: Record<string, unknown>;
  limit?: number;
  offset?: number;
  status?: string | null;
};

type ThreadCreateResponse = {
  thread_id: string;
};

type WecomThreadResponse = {
  thread_id: string;
  title: string;
};

async function readErrorDetail(response: Response, fallback: string) {
  const error = await response.json().catch(() => ({ detail: fallback }));
  return error.detail ?? fallback;
}

export async function createThread(
  options: { thread_id?: string; metadata?: Record<string, unknown> } = {},
): Promise<ThreadCreateResponse> {
  const response = await fetch(`${getBackendBaseURL()}/api/threads`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      thread_id: options.thread_id,
      metadata: options.metadata ?? {},
    }),
  });

  if (!response.ok) {
    throw new Error(await readErrorDetail(response, "Failed to create thread"));
  }

  return response.json() as Promise<ThreadCreateResponse>;
}

export async function searchThreads(
  body: ThreadSearchBody,
): Promise<AgentThread[]> {
  const response = await fetch(`${getBackendBaseURL()}/api/threads/search`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(await readErrorDetail(response, "Failed to search threads"));
  }

  return response.json() as Promise<AgentThread[]>;
}

export async function getOrCreateWecomThread(): Promise<WecomThreadResponse> {
  const response = await fetch(`${getBackendBaseURL()}/api/channels/wecom/thread`);

  if (!response.ok) {
    throw new Error(await readErrorDetail(response, "Failed to open WeCom thread"));
  }

  return response.json() as Promise<WecomThreadResponse>;
}

export async function clearWecomThread(): Promise<WecomThreadResponse> {
  const response = await fetch(`${getBackendBaseURL()}/api/channels/wecom/thread/clear`, {
    method: "POST",
  });

  if (!response.ok) {
    throw new Error(await readErrorDetail(response, "Failed to clear WeCom thread"));
  }

  return response.json() as Promise<WecomThreadResponse>;
}
