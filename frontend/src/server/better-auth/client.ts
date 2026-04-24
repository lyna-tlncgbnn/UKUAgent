import type { AuthSession } from "./shared";

async function parseResponse<T>(response: Response): Promise<T> {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message =
      payload && typeof payload === "object" && "detail" in payload
        ? String(payload.detail)
        : "Request failed.";
    throw new Error(message);
  }
  return payload as T;
}

export const authClient = {
  async getSession(): Promise<AuthSession | null> {
    const response = await fetch("/api/auth/session", {
      credentials: "include",
    });
    const payload = await parseResponse<{ session: AuthSession | null }>(response);
    return payload.session;
  },
  async signInEmail(input: { email: string; password: string }): Promise<AuthSession> {
    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
      credentials: "include",
    });
    const payload = await parseResponse<{ session: AuthSession }>(response);
    return payload.session;
  },
  async signOut(): Promise<void> {
    const response = await fetch("/api/auth/logout", {
      method: "POST",
      credentials: "include",
    });
    await parseResponse<{ success: boolean }>(response);
  },
  async changePassword(input: { currentPassword: string; newPassword: string }): Promise<void> {
    const response = await fetch("/api/auth/change-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
      credentials: "include",
    });
    await parseResponse<{ success: boolean }>(response);
  },
  async updateProfile(input: { name: string }): Promise<AuthSession> {
    const response = await fetch("/api/auth/profile", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
      credentials: "include",
    });
    const payload = await parseResponse<{ session: AuthSession }>(response);
    return payload.session;
  },
};

export type Session = AuthSession;

