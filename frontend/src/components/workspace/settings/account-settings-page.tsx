"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useChangePassword, useAuthSession, useSignOut, useUpdateAccount, useUpdateUserProfile, useUserProfile } from "@/core/auth/hooks";
import { useI18n } from "@/core/i18n/hooks";

import { SettingsSection } from "./settings-section";

export function AccountSettingsPage() {
  const { t } = useI18n();
  const session = useAuthSession();
  const profile = useUserProfile();
  const updateAccount = useUpdateAccount();
  const updateUserProfile = useUpdateUserProfile();
  const changePassword = useChangePassword();
  const signOut = useSignOut();

  const [name, setName] = useState("");
  const [profileText, setProfileText] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");

  useEffect(() => {
    setName(session.data?.user.name ?? "");
  }, [session.data?.user.name]);

  useEffect(() => {
    setProfileText(profile.data?.content ?? "");
  }, [profile.data?.content]);

  async function handleSaveProfile() {
    try {
      await updateAccount.mutateAsync({ name });
      await updateUserProfile.mutateAsync({ content: profileText });
      toast.success(t.settings.account.saveSuccess);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t.settings.account.saveError);
    }
  }

  async function handleChangePassword() {
    try {
      await changePassword.mutateAsync({ currentPassword, newPassword });
      setCurrentPassword("");
      setNewPassword("");
      toast.success(t.settings.account.passwordChangeSuccess);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t.settings.account.passwordChangeError);
    }
  }

  async function handleSignOut() {
    try {
      await signOut.mutateAsync();
      window.location.assign("/login");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t.settings.account.logoutError);
    }
  }

  return (
    <div className="space-y-8">
      <SettingsSection
        title={t.settings.account.title}
        description={t.settings.account.description}
      >
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <div className="text-sm font-medium">{t.settings.account.emailLabel}</div>
            <Input value={session.data?.user.email ?? ""} readOnly disabled />
          </div>
          <div className="space-y-2">
            <div className="text-sm font-medium">{t.settings.account.roleLabel}</div>
            <Input value={session.data?.user.role ?? ""} readOnly disabled />
          </div>
          <div className="space-y-2 md:col-span-2">
            <div className="text-sm font-medium">{t.settings.account.userIdLabel}</div>
            <Input value={session.data?.user.id ?? ""} readOnly disabled />
          </div>
          <div className="space-y-2 md:col-span-2">
            <div className="text-sm font-medium">{t.settings.account.nameLabel}</div>
            <Input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder={t.settings.account.namePlaceholder}
            />
          </div>
          <div className="space-y-2 md:col-span-2">
            <div className="text-sm font-medium">{t.settings.account.profileLabel}</div>
            <Textarea
              className="min-h-40"
              value={profileText}
              onChange={(event) => setProfileText(event.target.value)}
              placeholder={t.settings.account.profilePlaceholder}
            />
          </div>
        </div>
        <div className="mt-4 flex justify-end">
          <Button
            onClick={() => void handleSaveProfile()}
            disabled={updateAccount.isPending || updateUserProfile.isPending || session.isLoading || profile.isLoading}
          >
            {t.common.save}
          </Button>
        </div>
      </SettingsSection>

      <SettingsSection
        title={t.settings.account.passwordTitle}
        description={t.settings.account.passwordDescription}
      >
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <div className="text-sm font-medium">{t.settings.account.currentPasswordLabel}</div>
            <Input
              type="password"
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
              placeholder="********"
            />
          </div>
          <div className="space-y-2">
            <div className="text-sm font-medium">{t.settings.account.newPasswordLabel}</div>
            <Input
              type="password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
              placeholder="********"
            />
          </div>
        </div>
        <div className="mt-4 flex justify-end">
          <Button
            variant="outline"
            onClick={() => void handleChangePassword()}
            disabled={changePassword.isPending}
          >
            {t.settings.account.changePasswordAction}
          </Button>
        </div>
      </SettingsSection>

      <SettingsSection
        title={t.settings.account.sessionTitle}
        description={t.settings.account.sessionDescription}
      >
        <div className="flex justify-end">
          <Button
            variant="destructive"
            onClick={() => void handleSignOut()}
            disabled={signOut.isPending}
          >
            {t.settings.account.logoutAction}
          </Button>
        </div>
      </SettingsSection>
    </div>
  );
}

