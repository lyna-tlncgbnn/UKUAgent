"use client";

import dynamic from "next/dynamic";

const ScheduledTasksPage = dynamic(
  () => import("@/components/workspace/scheduled-tasks/scheduled-task-list-page").then((m) => m.ScheduledTasksPage),
  { ssr: false },
);

export default function Page() {
  return <ScheduledTasksPage />;
}
