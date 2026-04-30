"use client";

import {
  CirclePauseIcon,
  CirclePlayIcon,
  MoreHorizontalIcon,
  RefreshCwIcon,
  Trash2Icon,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useI18n } from "@/core/i18n/hooks";
import {
  useDeleteScheduledTask,
  usePauseScheduledTask,
  useResumeScheduledTask,
  useRunScheduledTaskNow,
} from "@/core/scheduled-tasks";
import type { ScheduledTask } from "@/core/scheduled-tasks";

/* ─── TaskActionDropdown ─── */

export function TaskActionDropdown({ task, onDeleteRequest }: { task: ScheduledTask; onDeleteRequest: () => void }) {
  const { t } = useI18n();
  const st = t.scheduledTasks;
  const pauseTask = usePauseScheduledTask();
  const resumeTask = useResumeScheduledTask();
  const runNow = useRunScheduledTaskNow();

  async function action(label: string, fn: () => Promise<unknown>) {
    try {
      await fn();
      toast.success(label);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : st.operationFailed);
    }
  }

  const showPause = task.status === "active";
  const showResume = task.status === "paused" || task.status === "disabled";
  const showRunNow = task.status === "active";
  const showSeparator = (showPause || showResume || showRunNow);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon">
          <MoreHorizontalIcon className="size-4" />
          <span className="sr-only">{st.actions}</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-48 rounded-lg" align="end">
        {showPause && (
          <DropdownMenuItem onSelect={() => action(st.paused, () => pauseTask.mutateAsync(task.id))}>
            <CirclePauseIcon className="text-muted-foreground" />
            <span>{st.pause}</span>
          </DropdownMenuItem>
        )}
        {showResume && (
          <DropdownMenuItem onSelect={() => action(st.resumed, () => resumeTask.mutateAsync(task.id))}>
            <CirclePlayIcon className="text-muted-foreground" />
            <span>{st.resume}</span>
          </DropdownMenuItem>
        )}
        {showRunNow && (
          <DropdownMenuItem onSelect={() => action(st.runNowTriggered, () => runNow.mutateAsync(task.id))}>
            <RefreshCwIcon className="text-muted-foreground" />
            <span>{st.runNow}</span>
          </DropdownMenuItem>
        )}
        {showSeparator && <DropdownMenuSeparator />}
        <DropdownMenuItem variant="destructive" onSelect={onDeleteRequest}>
          <Trash2Icon />
          <span>{st.delete}</span>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/* ─── DeleteConfirmDialog ─── */

export function DeleteConfirmDialog({
  taskToDelete,
  onClear,
}: {
  taskToDelete: ScheduledTask | null;
  onClear: () => void;
}) {
  const { t } = useI18n();
  const st = t.scheduledTasks;
  const deleteTask = useDeleteScheduledTask();

  async function handleDelete() {
    if (!taskToDelete) return;
    try {
      await deleteTask.mutateAsync(taskToDelete.id);
      toast.success(st.taskDeleted);
      onClear();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : st.deleteFailed);
    }
  }

  return (
    <Dialog open={taskToDelete !== null} onOpenChange={(open) => { if (!open) onClear(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{st.deleteConfirmTitle}</DialogTitle>
          <DialogDescription>{st.deleteConfirmDescription}</DialogDescription>
        </DialogHeader>
        {taskToDelete && (
          <div className="bg-muted rounded-md border p-3 text-sm">
            <div className="text-muted-foreground mb-1 font-medium">{st.deleteTaskName}</div>
            <p className="break-words">{taskToDelete.title}</p>
          </div>
        )}
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline" disabled={deleteTask.isPending}>
              {t.common.cancel}
            </Button>
          </DialogClose>
          <Button variant="destructive" onClick={handleDelete} disabled={deleteTask.isPending}>
            {deleteTask.isPending ? st.deleting : st.delete}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
