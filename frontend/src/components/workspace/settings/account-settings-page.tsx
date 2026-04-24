"use client";

import {
  CopyIcon,
  LogOutIcon,
  MailIcon,
  ShieldCheckIcon,
} from "lucide-react";
import { useMemo } from "react";
import { toast } from "sonner";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useAuthSession, useSignOut } from "@/core/auth/hooks";
import { useI18n } from "@/core/i18n/hooks";
import { cn } from "@/lib/utils";

function InfoRow({
  label,
  value,
  action,
  mono = false,
}: {
  label: string;
  value: string;
  action?: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="flex items-start justify-between gap-4 rounded-xl border border-border/60 bg-background/70 px-4 py-3">
      <div className="min-w-0 space-y-1">
        <div className="text-muted-foreground text-sm font-medium">
          {label}
        </div>
        <div
          className={cn(
            "text-sm font-medium break-all",
            mono && "font-mono text-xs tracking-[0.04em]",
          )}
        >
          {value}
        </div>
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

export function AccountSettingsPage() {
  const { t } = useI18n();
  const session = useAuthSession();
  const signOut = useSignOut();

  const user = session.data?.user;

  const initials = useMemo(() => {
    const source = (user?.name || user?.email || "U").trim();
    const tokens = source.split(/\s+/).filter(Boolean);
    if (tokens.length >= 2) {
      return `${tokens[0]?.[0] ?? ""}${tokens[1]?.[0] ?? ""}`.toUpperCase();
    }
    return source.slice(0, 2).toUpperCase();
  }, [user?.email, user?.name]);

  async function handleSignOut() {
    try {
      await signOut.mutateAsync();
      window.location.assign("/login");
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : t.settings.account.logoutError,
      );
    }
  }

  async function handleCopyUserId() {
    if (!user?.id) {
      return;
    }
    try {
      await navigator.clipboard.writeText(user.id);
      toast.success(t.clipboard.copiedToClipboard);
    } catch {
      toast.error(t.clipboard.failedToCopyToClipboard);
    }
  }

  return (
    <div className="space-y-6">
      <Card className="gap-0 overflow-hidden border-border/60 bg-background/70 shadow-none">
        <CardHeader className="grid gap-5 border-b border-border/60 bg-gradient-to-br from-background via-background to-muted/40 px-6 py-6 md:grid-cols-[minmax(0,1fr)_auto] md:items-start">
          <div className="flex items-start gap-4">
            <Avatar className="size-16 border border-border/60 bg-muted/60">
              <AvatarFallback className="text-lg font-semibold">
                {initials}
              </AvatarFallback>
            </Avatar>
            <div className="min-w-0 space-y-2">
              <CardTitle className="text-2xl tracking-tight">
                {user?.name || user?.email || t.settings.account.title}
              </CardTitle>
              <CardDescription className="flex items-center gap-2 text-sm">
                <MailIcon className="size-4" />
                <span className="truncate">{user?.email ?? "-"}</span>
              </CardDescription>
              <div className="flex flex-wrap items-center gap-2 pt-1">
                <Badge variant="secondary" className="rounded-full px-2.5 py-1">
                  <ShieldCheckIcon className="size-3.5" />
                  {user?.role ?? "-"}
                </Badge>
              </div>
            </div>
          </div>
          <CardAction className="col-auto row-auto self-start justify-self-start md:justify-self-end">
            <Button
              variant="destructive"
              size="sm"
              onClick={() => void handleSignOut()}
              disabled={signOut.isPending}
              className="rounded-full"
            >
              <LogOutIcon className="size-4" />
              {t.settings.account.logoutAction}
            </Button>
          </CardAction>
        </CardHeader>
        <CardContent className="grid gap-3 px-6 py-5 md:grid-cols-2">
          <InfoRow
            label={t.settings.account.emailLabel}
            value={user?.email ?? "-"}
          />
          <InfoRow
            label={t.settings.account.roleLabel}
            value={user?.role ?? "-"}
          />
          <div className="md:col-span-2">
            <InfoRow
              label={t.settings.account.userIdLabel}
              value={user?.id ?? "-"}
              mono
              action={
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  className="rounded-full"
                  onClick={() => void handleCopyUserId()}
                  disabled={!user?.id}
                >
                  <CopyIcon className="size-4" />
                </Button>
              }
            />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
