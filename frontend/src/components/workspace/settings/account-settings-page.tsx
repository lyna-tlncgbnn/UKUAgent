"use client";

import { LogOutIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  useAuthSession,
  useSignOut,
  useUpdateUserProfile,
  useUserProfile,
} from "@/core/auth/hooks";
import { useI18n } from "@/core/i18n/hooks";

export function AccountSettingsPage() {
  const { t } = useI18n();
  const session = useAuthSession();
  const profile = useUserProfile();
  const updateUserProfile = useUpdateUserProfile();
  const signOut = useSignOut();

  const user = session.data?.user;
  const [profileText, setProfileText] = useState("");

  useEffect(() => {
    setProfileText(profile.data?.content ?? "");
  }, [profile.data?.content]);

  async function handleSaveProfile() {
    try {
      await updateUserProfile.mutateAsync({ content: profileText });
      toast.success(t.settings.account.saveSuccess);
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : t.settings.account.saveError,
      );
    }
  }

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

  const isSaving = updateUserProfile.isPending || session.isLoading || profile.isLoading;

  const avatarLetter = (user?.name || user?.email || "U").slice(0, 1).toUpperCase();

  return (
    <div className="mx-auto w-full max-w-2xl space-y-8">
      {/* Avatar + 基本信息 */}
      <div className="flex items-center gap-5">
        <div className="flex size-16 shrink-0 items-center justify-center rounded-full bg-primary text-2xl font-semibold text-primary-foreground">
          {avatarLetter}
        </div>
        <div className="min-w-0">
          <p className="truncate text-xl font-semibold tracking-tight">
            {user?.name || user?.email || t.settings.account.title}
          </p>
          <p className="mt-0.5 truncate text-sm text-muted-foreground">
            {user?.email ?? ""}
          </p>
        </div>
      </div>

      {/* 账号信息列表 */}
      <div className="rounded-xl border border-border/60 bg-muted/30">
        <InfoRow label={t.settings.account.emailLabel} value={user?.email ?? "—"} />
        <InfoRow label={t.settings.account.roleLabel} value={user?.role ?? "—"} />
        <InfoRow
          label={t.settings.account.userIdLabel}
          value={user?.id ?? "—"}
          mono
          last
        />
      </div>

      {/* 个人说明 */}
      <div className="space-y-2">
        <label
          className="text-sm font-medium text-foreground"
          htmlFor="account-profile"
        >
          {t.settings.account.profileLabel}
        </label>
        <Textarea
          id="account-profile"
          className="min-h-36 resize-y rounded-xl border-border/60 bg-muted/30 text-sm transition-colors focus-visible:bg-background"
          value={profileText}
          onChange={(event) => setProfileText(event.target.value)}
          placeholder={t.settings.account.profilePlaceholder}
        />
        <div className="flex justify-end pt-1">
          <Button
            size="sm"
            onClick={() => void handleSaveProfile()}
            disabled={isSaving}
          >
            {t.common.save}
          </Button>
        </div>
      </div>

      {/* 退出登录 */}
      <div className="border-t border-border/60 pt-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-foreground">
              {t.settings.account.logoutAction}
            </p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {t.settings.account.sessionDescription}
            </p>
          </div>
          <Button
            variant="destructive"
            size="sm"
            onClick={() => void handleSignOut()}
            disabled={signOut.isPending}
          >
            <LogOutIcon className="size-3.5" />
            {t.settings.account.logoutAction}
          </Button>
        </div>
      </div>
    </div>
  );
}

function InfoRow({
  label,
  value,
  mono = false,
  last = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
  last?: boolean;
}) {
  return (
    <div
      className={`flex items-center justify-between gap-6 px-4 py-3 ${
        last ? "" : "border-b border-border/60"
      }`}
    >
      <span className="shrink-0 text-sm text-muted-foreground">{label}</span>
      <span
        className={`min-w-0 truncate text-sm text-foreground ${mono ? "font-mono text-xs" : ""}`}
      >
        {value}
      </span>
    </div>
  );
}
