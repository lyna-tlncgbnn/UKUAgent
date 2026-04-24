export const AUTH_SESSION_COOKIE_NAME = "deerflow_session";
export const AUTH_SESSION_TTL_SECONDS = 60 * 60 * 24 * 7;
export const MIN_PASSWORD_LENGTH = 8;

export type AuthUserRole = "admin" | "member";
export type AuthUserStatus = "active" | "disabled";

export type AuthUserRecord = {
  id: string;
  email: string;
  name: string;
  passwordHash: string;
  role: AuthUserRole;
  status: AuthUserStatus;
  createdAt: string;
  updatedAt: string;
};

export type AuthSessionUser = {
  id: string;
  email: string;
  name: string;
  role: AuthUserRole;
  status: AuthUserStatus;
};

export type AuthSession = {
  user: AuthSessionUser;
  expiresAt: string;
};

