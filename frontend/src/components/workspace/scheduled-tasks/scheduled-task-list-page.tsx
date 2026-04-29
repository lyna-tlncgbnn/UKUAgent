"use client";

import { CalendarClockIcon } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Item, ItemActions, ItemContent, ItemDescription, ItemMedia, ItemTitle } from "@/components/ui/item";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useScheduledTasks } from "@/core/scheduled-tasks";
import type { ScheduledTask } from "@/core/scheduled-tasks";

import { DeleteConfirmDialog, TaskActionDropdown } from "./task-action-dropdown";
import { NewTaskDialog } from "./new-task-dialog";
import { TASK_STATUS_COLORS, TASK_STATUS_LABELS, scheduleLabel, taskTimeHint } from "./lib";

export function ScheduledTasksPage() {
  const { tasks, isLoading, error } = useScheduledTasks();
  const [filter, setFilter] = useState("active");
  const [taskToDelete, setTaskToDelete] = useState<ScheduledTask | null>(null);

  const filteredTasks = useMemo(
    () => (filter === "all" ? tasks : tasks.filter((t) => t.status === filter)),
    [tasks, filter],
  );

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

      <div className="min-h-0 flex-1 overflow-auto">
        {/* Filter tabs */}
        <div className="px-8 pt-6">
          <Tabs value={filter} onValueChange={setFilter}>
            <TabsList variant="line">
              <TabsTrigger value="active">活跃</TabsTrigger>
              <TabsTrigger value="paused">已暂停</TabsTrigger>
              <TabsTrigger value="completed">已完成</TabsTrigger>
              <TabsTrigger value="all">全部</TabsTrigger>
            </TabsList>
          </Tabs>
        </div>

        {/* Content */}
        <div className="px-8 py-4">
          {isLoading && <div className="text-muted-foreground text-sm">加载中...</div>}
          {error && <div className="text-destructive text-sm">加载定时任务失败。</div>}
          {!isLoading && filteredTasks.length === 0 && (
            <Empty>
              <EmptyHeader>
                <EmptyMedia variant="icon">
                  <CalendarClockIcon />
                </EmptyMedia>
                <EmptyTitle>{tasks.length === 0 ? "还没有定时任务" : "没有匹配的任务"}</EmptyTitle>
                <EmptyDescription>
                  {tasks.length === 0 ? "创建一个定时任务，让 agent 自动执行。" : "当前过滤条件下没有任务。"}
                </EmptyDescription>
              </EmptyHeader>
              {tasks.length === 0 && (
                <EmptyContent>
                  <NewTaskDialog />
                </EmptyContent>
              )}
            </Empty>
          )}
          {filteredTasks.length > 0 && (
            <div className="flex flex-col gap-2">
              {filteredTasks.map((task) => (
                <Item
                  key={task.id}
                  variant="outline"
                  className="w-full rounded-lg transition-colors hover:bg-accent/50"
                >
                  <ItemMedia>
                    <span className={`size-2.5 shrink-0 rounded-full ${TASK_STATUS_COLORS[task.status]}`} />
                  </ItemMedia>
                  <ItemContent>
                    <ItemTitle>
                      <Link href={`/workspace/scheduled-tasks/${task.id}`} className="hover:underline">
                        {task.title}
                      </Link>
                      <span className="text-muted-foreground text-xs font-normal">
                        {TASK_STATUS_LABELS[task.status]}
                      </span>
                    </ItemTitle>
                    <ItemDescription>
                      {[scheduleLabel(task), taskTimeHint(task), task.assistant_id].filter(Boolean).join(" · ")}
                    </ItemDescription>
                  </ItemContent>
                  <ItemActions>
                    <TaskActionDropdown task={task} onDeleteRequest={() => setTaskToDelete(task)} />
                  </ItemActions>
                </Item>
              ))}
            </div>
          )}
        </div>
      </div>

      <DeleteConfirmDialog taskToDelete={taskToDelete} onClear={() => setTaskToDelete(null)} />
    </main>
  );
}
