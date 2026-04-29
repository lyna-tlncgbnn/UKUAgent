"use client";

import { use } from "react";
import dynamic from "next/dynamic";

const ScheduledTaskDetailPage = dynamic(
  () => import("@/components/workspace/scheduled-tasks/scheduled-task-detail-page").then((m) => m.ScheduledTaskDetailPage),
  { ssr: false },
);

export default function Page({
  params,
}: {
  params: Promise<{ task_id: string }>;
}) {
  const { task_id } = use(params);
  return <ScheduledTaskDetailPage taskId={task_id} />;
}
