import { authClient } from "@/server/better-auth/client";
import type { AuthSession } from "@/server/better-auth/shared";
import { getBackendBaseURL } from "../config";

export type { AuthSession };

export async function getAuthSession() {
  return authClient.getSession();
}

export async function signInWithPassword(input: { email: string; password: string }) {
  return authClient.signInEmail(input);
}

export async function signOut() {
  return authClient.signOut();
}

export async function changePassword(input: { currentPassword: string; newPassword: string }) {
  return authClient.changePassword(input);
}

export async function updateAccount(input: { name: string }) {
  return authClient.updateProfile(input);
}

export async function getUserProfile() {
  const response = await fetch(`${getBackendBaseURL()}/api/user-profile`);
  const payload = await response.json().catch(() => ({ detail: "Failed to fetch user profile." }));
  if (!response.ok) {
    throw new Error(payload.detail ?? "Failed to fetch user profile.");
  }
  return payload as { content: string | null };
}

export async function updateUserProfile(input: { content: string }) {
  const response = await fetch(`${getBackendBaseURL()}/api/user-profile`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  const payload = await response.json().catch(() => ({ detail: "Failed to update user profile." }));
  if (!response.ok) {
    throw new Error(payload.detail ?? "Failed to update user profile.");
  }
  return payload as { content: string | null };
}
