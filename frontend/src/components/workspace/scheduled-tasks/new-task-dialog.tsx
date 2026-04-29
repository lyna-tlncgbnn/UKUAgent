"use client";

import { PlusIcon } from "lucide-react";
import { useState } from "react";
import type { FormEvent } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useCreateScheduledTask } from "@/core/scheduled-tasks";
import type { CreateScheduledTaskRequest } from "@/core/scheduled-tasks";

/* ─── FormField ─── */

function FormField({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <label className="text-sm font-medium">{label}</label>
      {hint && <p className="text-muted-foreground text-xs">{hint}</p>}
      {children}
    </div>
  );
}

/* ─── NewTaskDialog ─── */

export function NewTaskDialog() {
  const [open, setOpen] = useState(false);
  const [scheduleType, setScheduleType] = useState<CreateScheduledTaskRequest["schedule_type"]>("cron");
  const createTask = useCreateScheduledTask();

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    const payload: CreateScheduledTaskRequest = {
      title: String(form.get("title") ?? ""),
      assistant_id: String(form.get("assistant_id") || "lead_agent"),
      prompt: String(form.get("prompt") ?? ""),
      schedule_type: scheduleType,
      timezone: String(form.get("timezone") || "Asia/Shanghai"),
      cron_expr: scheduleType === "cron" ? String(form.get("cron_expr") ?? "") : null,
      interval_seconds: scheduleType === "interval" ? Number(form.get("interval_seconds") ?? 0) : null,
      run_at: scheduleType === "once" ? String(form.get("run_at") ?? "") : null,
    };
    try {
      await createTask.mutateAsync(payload);
      toast.success("定时任务已创建");
      formElement.reset();
      setOpen(false);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "创建定时任务失败");
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <PlusIcon className="size-4" />
          新建任务
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>新建定时任务</DialogTitle>
          <DialogDescription>创建一个定时自动执行的 Agent 任务。</DialogDescription>
        </DialogHeader>
        <form className="grid gap-5" onSubmit={handleSubmit}>
          <FormField label="任务名称" hint="为这个定时任务起一个容易辨识的名字">
            <Input name="title" placeholder="例如：每日站会提醒" required />
          </FormField>

          <FormField label="执行内容" hint="每次触发时发送给 Agent 的指令">
            <Textarea name="prompt" placeholder="例如：现在是早上 9 点，请提醒团队开站会" required className="min-h-24" />
          </FormField>

          <FormField label="智能体" hint="执行此任务的 Agent ID">
            <Input name="assistant_id" defaultValue="lead_agent" placeholder="lead_agent" />
          </FormField>

          <div className="space-y-3">
            <div className="text-sm font-medium">调度配置</div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <div className="text-muted-foreground text-xs">调度类型</div>
                <Select value={scheduleType} onValueChange={(v) => setScheduleType(v as CreateScheduledTaskRequest["schedule_type"])}>
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="cron">Cron 表达式</SelectItem>
                    <SelectItem value="interval">固定间隔</SelectItem>
                    <SelectItem value="once">仅执行一次</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <div className="text-muted-foreground text-xs">时区</div>
                <Input name="timezone" defaultValue="Asia/Shanghai" />
              </div>
            </div>
            {scheduleType === "cron" && (
              <div className="space-y-1.5">
                <div className="text-muted-foreground text-xs">Cron 表达式</div>
                <Input name="cron_expr" defaultValue="0 9 * * *" placeholder="0 9 * * *" />
                <p className="text-muted-foreground text-xs">例如：0 9 * * * 表示每天 9:00 执行</p>
              </div>
            )}
            {scheduleType === "interval" && (
              <div className="space-y-1.5">
                <div className="text-muted-foreground text-xs">间隔时间（秒）</div>
                <Input name="interval_seconds" type="number" min={60} defaultValue={3600} />
                <p className="text-muted-foreground text-xs">最小 60 秒，3600 = 每 1 小时</p>
              </div>
            )}
            {scheduleType === "once" && (
              <div className="space-y-1.5">
                <div className="text-muted-foreground text-xs">执行时间</div>
                <Input name="run_at" type="datetime-local" required />
              </div>
            )}
          </div>

          <DialogFooter>
            <Button type="submit" disabled={createTask.isPending}>
              {createTask.isPending ? "创建中..." : "创建任务"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
