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
import {
  useDeleteScheduledTask,
  usePauseScheduledTask,
  useResumeScheduledTask,
  useRunScheduledTaskNow,
} from "@/core/scheduled-tasks";
import type { ScheduledTask } from "@/core/scheduled-tasks";

/* ─── TaskActionDropdown ─── */

export function TaskActionDropdown({ task, onDeleteRequest }: { task: ScheduledTask; onDeleteRequest: () => void }) {
  const pauseTask = usePauseScheduledTask();
  const resumeTask = useResumeScheduledTask();
  const runNow = useRunScheduledTaskNow();

  async function action(label: string, fn: () => Promise<unknown>) {
    try {
      await fn();
      toast.success(label);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "操作失败");
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
          <span className="sr-only">操作</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="w-48 rounded-lg" align="end">
        {showPause && (
          <DropdownMenuItem onSelect={() => action("任务已暂停", () => pauseTask.mutateAsync(task.id))}>
            <CirclePauseIcon className="text-muted-foreground" />
            <span>暂停</span>
          </DropdownMenuItem>
        )}
        {showResume && (
          <DropdownMenuItem onSelect={() => action("任务已恢复", () => resumeTask.mutateAsync(task.id))}>
            <CirclePlayIcon className="text-muted-foreground" />
            <span>恢复</span>
          </DropdownMenuItem>
        )}
        {showRunNow && (
          <DropdownMenuItem onSelect={() => action("已触发立即运行", () => runNow.mutateAsync(task.id))}>
            <RefreshCwIcon className="text-muted-foreground" />
            <span>立即运行</span>
          </DropdownMenuItem>
        )}
        {showSeparator && <DropdownMenuSeparator />}
        <DropdownMenuItem variant="destructive" onSelect={onDeleteRequest}>
          <Trash2Icon />
          <span>删除</span>
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
  const deleteTask = useDeleteScheduledTask();

  async function handleDelete() {
    if (!taskToDelete) return;
    try {
      await deleteTask.mutateAsync(taskToDelete.id);
      toast.success("任务已删除");
      onClear();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "删除失败");
    }
  }

  return (
    <Dialog open={taskToDelete !== null} onOpenChange={(open) => { if (!open) onClear(); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>确认删除</DialogTitle>
          <DialogDescription>删除后无法恢复，确认要删除这个定时任务吗？</DialogDescription>
        </DialogHeader>
        {taskToDelete && (
          <div className="bg-muted rounded-md border p-3 text-sm">
            <div className="text-muted-foreground mb-1 font-medium">任务名称</div>
            <p className="break-words">{taskToDelete.title}</p>
          </div>
        )}
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline" disabled={deleteTask.isPending}>
              取消
            </Button>
          </DialogClose>
          <Button variant="destructive" onClick={handleDelete} disabled={deleteTask.isPending}>
            {deleteTask.isPending ? "删除中..." : "删除"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
