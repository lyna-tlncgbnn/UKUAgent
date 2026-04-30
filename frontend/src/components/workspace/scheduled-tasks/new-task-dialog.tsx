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
import { useI18n } from "@/core/i18n/hooks";
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
  const { t } = useI18n();
  const st = t.scheduledTasks;
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
      toast.success(st.taskCreated);
      formElement.reset();
      setOpen(false);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : st.createFailed);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>
          <PlusIcon className="size-4" />
          {st.newTask}
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{st.createDialogTitle}</DialogTitle>
          <DialogDescription>{st.createDialogDescription}</DialogDescription>
        </DialogHeader>
        <form className="grid gap-5" onSubmit={handleSubmit}>
          <FormField label={st.taskNameLabel} hint={st.taskNameHint}>
            <Input name="title" placeholder={st.taskNamePlaceholder} required />
          </FormField>

          <FormField label={st.executionContentLabel} hint={st.executionContentHint}>
            <Textarea name="prompt" placeholder={st.executionContentPlaceholder} required className="min-h-24" />
          </FormField>

          <FormField label={st.agentLabel} hint={st.agentHint}>
            <Input name="assistant_id" defaultValue="lead_agent" placeholder="lead_agent" />
          </FormField>

          <div className="space-y-3">
            <div className="text-sm font-medium">{st.scheduleConfigLabel}</div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <div className="text-muted-foreground text-xs">{st.scheduleTypeLabel}</div>
                <Select value={scheduleType} onValueChange={(v) => setScheduleType(v as CreateScheduledTaskRequest["schedule_type"])}>
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="cron">{st.scheduleCron}</SelectItem>
                    <SelectItem value="interval">{st.scheduleInterval}</SelectItem>
                    <SelectItem value="once">{st.scheduleOnce}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <div className="text-muted-foreground text-xs">{st.timezoneLabel}</div>
                <Input name="timezone" defaultValue="Asia/Shanghai" />
              </div>
            </div>
            {scheduleType === "cron" && (
              <div className="space-y-1.5">
                <div className="text-muted-foreground text-xs">{st.cronExpressionLabel}</div>
                <Input name="cron_expr" defaultValue="0 9 * * *" placeholder="0 9 * * *" />
                <p className="text-muted-foreground text-xs">{st.cronExpressionHint}</p>
              </div>
            )}
            {scheduleType === "interval" && (
              <div className="space-y-1.5">
                <div className="text-muted-foreground text-xs">{st.intervalSecondsLabel}</div>
                <Input name="interval_seconds" type="number" min={60} defaultValue={3600} />
                <p className="text-muted-foreground text-xs">{st.intervalSecondsHint}</p>
              </div>
            )}
            {scheduleType === "once" && (
              <div className="space-y-1.5">
                <div className="text-muted-foreground text-xs">{st.executionTimeLabel}</div>
                <Input name="run_at" type="datetime-local" required />
              </div>
            )}
          </div>

          <DialogFooter>
            <Button type="submit" disabled={createTask.isPending}>
              {createTask.isPending ? st.creating : st.createTask}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
