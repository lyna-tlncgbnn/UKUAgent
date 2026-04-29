import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createScheduledTask,
  deleteScheduledTask,
  getScheduledTaskThreadState,
  getScheduledTask,
  listScheduledTaskRuns,
  listScheduledTasks,
  pauseScheduledTask,
  resumeScheduledTask,
  runScheduledTaskNow,
  updateScheduledTask,
} from "./api";
import type { CreateScheduledTaskRequest, UpdateScheduledTaskRequest } from "./types";

export function useScheduledTasks() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["scheduled-tasks"],
    queryFn: listScheduledTasks,
  });
  return { tasks: data ?? [], isLoading, error };
}

export function useScheduledTask(taskId: string | null | undefined) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["scheduled-tasks", taskId],
    queryFn: () => getScheduledTask(taskId!),
    enabled: !!taskId,
  });
  return { task: data ?? null, isLoading, error };
}

export function useScheduledTaskRuns(taskId: string | null | undefined) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["scheduled-tasks", taskId, "runs"],
    queryFn: () => listScheduledTaskRuns(taskId!),
    enabled: !!taskId,
  });
  return { runs: data ?? [], isLoading, error };
}

export function useScheduledTaskThreadState(threadId: string | null | undefined) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["scheduled-tasks", "thread-state", threadId],
    queryFn: () => getScheduledTaskThreadState(threadId!),
    enabled: !!threadId,
  });
  return { state: data ?? null, isLoading, error };
}

export function useCreateScheduledTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: CreateScheduledTaskRequest) => createScheduledTask(request),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["scheduled-tasks"] }),
  });
}

export function useUpdateScheduledTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ taskId, request }: { taskId: string; request: UpdateScheduledTaskRequest }) =>
      updateScheduledTask(taskId, request),
    onSuccess: (_data, { taskId }) => {
      void queryClient.invalidateQueries({ queryKey: ["scheduled-tasks"] });
      void queryClient.invalidateQueries({ queryKey: ["scheduled-tasks", taskId] });
    },
  });
}

export function usePauseScheduledTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: pauseScheduledTask,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["scheduled-tasks"] }),
  });
}

export function useResumeScheduledTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: resumeScheduledTask,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["scheduled-tasks"] }),
  });
}

export function useDeleteScheduledTask() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteScheduledTask,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["scheduled-tasks"] }),
  });
}

export function useRunScheduledTaskNow() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: runScheduledTaskNow,
    onSuccess: (_data, taskId) => {
      void queryClient.invalidateQueries({ queryKey: ["scheduled-tasks"] });
      void queryClient.invalidateQueries({ queryKey: ["scheduled-tasks", taskId, "runs"] });
    },
  });
}
