import { ScheduledTaskDetailPage } from "@/components/workspace/scheduled-tasks/scheduled-task-pages";

export default async function Page({
  params,
}: {
  params: Promise<{ task_id: string }>;
}) {
  const { task_id } = await params;
  return <ScheduledTaskDetailPage taskId={task_id} />;
}
