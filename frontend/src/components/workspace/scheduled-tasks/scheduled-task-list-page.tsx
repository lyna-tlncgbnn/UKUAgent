"use client";

import { CalendarClockIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { Empty, EmptyContent, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Item, ItemActions, ItemContent, ItemDescription, ItemMedia, ItemTitle } from "@/components/ui/item";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  WorkspaceBody,
  WorkspaceContainer,
  WorkspaceHeader,
} from "@/components/workspace/workspace-container";
import { useI18n } from "@/core/i18n/hooks";
import { useScheduledTasks } from "@/core/scheduled-tasks";
import type { ScheduledTask } from "@/core/scheduled-tasks";

import { DeleteConfirmDialog, TaskActionDropdown } from "./task-action-dropdown";
import { NewTaskDialog } from "./new-task-dialog";
import { TASK_STATUS_COLORS, getTaskStatusLabels, scheduleLabel, taskTimeHint } from "./lib";

export function ScheduledTasksPage() {
  const router = useRouter();
  const { t, locale } = useI18n();
  const st = t.scheduledTasks;
  const { tasks, isLoading, error } = useScheduledTasks();
  const [filter, setFilter] = useState("active");
  const [taskToDelete, setTaskToDelete] = useState<ScheduledTask | null>(null);

  const statusLabels = useMemo(() => getTaskStatusLabels(st), [st]);

  const filteredTasks = useMemo(
    () => (filter === "all" ? tasks : tasks.filter((t) => t.status === filter)),
    [tasks, filter],
  );

  return (
    <WorkspaceContainer>
      <WorkspaceHeader />
      <WorkspaceBody>
        <div className="flex size-full flex-col">
          {/* Page header */}
          <header className="flex shrink-0 items-center justify-center pt-8">
            <div className="flex w-full max-w-(--container-width-md) items-center justify-between">
              <div>
                <h1 className="text-2xl font-semibold">{st.title}</h1>
                <p className="text-muted-foreground mt-1 text-sm">{st.description}</p>
              </div>
              <NewTaskDialog />
            </div>
          </header>

          {/* Content */}
          <main className="min-h-0 flex-1">
            <div className="mx-auto w-full max-w-(--container-width-md) py-4">
              {/* Filter tabs */}
              <Tabs value={filter} onValueChange={setFilter}>
                <TabsList variant="line">
                  <TabsTrigger value="active">{st.statusActive}</TabsTrigger>
                  <TabsTrigger value="paused">{st.statusPaused}</TabsTrigger>
                  <TabsTrigger value="completed">{st.statusCompleted}</TabsTrigger>
                  <TabsTrigger value="all">{st.tabAll}</TabsTrigger>
                </TabsList>
              </Tabs>

              {/* Task list */}
              <div className="pt-4">
                {isLoading && <div className="text-muted-foreground text-sm">{st.loading}</div>}
                {error && <div className="text-destructive text-sm">{st.loadError}</div>}
                {!isLoading && filteredTasks.length === 0 && (
                  <Empty>
                    <EmptyHeader>
                      <EmptyMedia variant="icon">
                        <CalendarClockIcon />
                      </EmptyMedia>
                      <EmptyTitle>{tasks.length === 0 ? st.emptyTitle : st.emptyFilteredTitle}</EmptyTitle>
                      <EmptyDescription>
                        {tasks.length === 0 ? st.emptyDescription : st.emptyFilteredDescription}
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
                        className="w-full cursor-pointer rounded-lg transition-colors hover:bg-accent/50"
                        onClick={() => router.push(`/workspace/scheduled-tasks/${task.id}`)}
                      >
                        <ItemMedia>
                          <span className={`size-2.5 shrink-0 rounded-full ${TASK_STATUS_COLORS[task.status]}`} />
                        </ItemMedia>
                        <ItemContent>
                          <ItemTitle>
                            {task.title}
                            <span className="text-muted-foreground text-xs font-normal">
                              {statusLabels[task.status]}
                            </span>
                          </ItemTitle>
                          <ItemDescription>
                            {[scheduleLabel(task, st), taskTimeHint(task, st, locale), task.assistant_id].filter(Boolean).join(" · ")}
                          </ItemDescription>
                        </ItemContent>
                        <ItemActions onClick={(e: React.MouseEvent) => e.stopPropagation()}>
                          <TaskActionDropdown task={task} onDeleteRequest={() => setTaskToDelete(task)} />
                        </ItemActions>
                      </Item>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </main>

          <DeleteConfirmDialog taskToDelete={taskToDelete} onClear={() => setTaskToDelete(null)} />
        </div>
      </WorkspaceBody>
    </WorkspaceContainer>
  );
}
