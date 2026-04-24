import { NextRequest, NextResponse } from "next/server";

import {
  authenticateUser,
  createSessionForUser,
  getSessionCookieOptions,
  getSessionFromToken,
  updateUserAccount,
  updateUserPassword,
} from "@/server/better-auth";
import { AUTH_SESSION_COOKIE_NAME, MIN_PASSWORD_LENGTH } from "@/server/better-auth/shared";

function json(data: unknown, init?: ResponseInit) {
  return NextResponse.json(data, init);
}

function getTokenFromRequest(request: NextRequest) {
  return request.cookies.get(AUTH_SESSION_COOKIE_NAME)?.value;
}

function requireSession(request: NextRequest) {
  const session = getSessionFromToken(getTokenFromRequest(request));
  if (!session) {
    return null;
  }
  return session;
}

function withSessionCookie(response: NextResponse, token: string) {
  response.cookies.set({
    ...getSessionCookieOptions(),
    value: token,
  });
  return response;
}

function clearSessionCookie(response: NextResponse) {
  response.cookies.set({
    ...getSessionCookieOptions(),
    value: "",
    maxAge: 0,
  });
  return response;
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ all: string[] }> },
) {
  const path = (await params).all ?? [];
  if (path[0] === "session") {
    return json({ session: requireSession(request) });
  }
  return json({ detail: "Not found." }, { status: 404 });
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ all: string[] }> },
) {
  const path = (await params).all ?? [];
  const action = path[0];

  if (action === "login") {
    const body = (await request.json().catch(() => ({}))) as {
      email?: string;
      password?: string;
    };
    const email = body.email?.trim() ?? "";
    const password = body.password ?? "";
    if (!email || !password) {
      return json({ detail: "Email and password are required." }, { status: 400 });
    }

    const user = authenticateUser(email, password);
    if (!user) {
      return json({ detail: "Invalid email or password." }, { status: 401 });
    }

    const { session, token } = createSessionForUser(user);
    return withSessionCookie(json({ session }), token);
  }

  if (action === "logout") {
    return clearSessionCookie(json({ success: true }));
  }

  if (action === "change-password") {
    const session = requireSession(request);
    if (!session) {
      return json({ detail: "Authentication required." }, { status: 401 });
    }

    const body = (await request.json().catch(() => ({}))) as {
      currentPassword?: string;
      newPassword?: string;
    };
    const currentPassword = body.currentPassword ?? "";
    const newPassword = body.newPassword ?? "";

    if (!currentPassword || !newPassword) {
      return json({ detail: "Current password and new password are required." }, { status: 400 });
    }
    if (newPassword.length < MIN_PASSWORD_LENGTH) {
      return json(
        { detail: `New password must be at least ${MIN_PASSWORD_LENGTH} characters.` },
        { status: 400 },
      );
    }

    try {
      updateUserPassword(session.user.id, currentPassword, newPassword);
      return json({ success: true });
    } catch (error) {
      return json(
        { detail: error instanceof Error ? error.message : "Failed to change password." },
        { status: 400 },
      );
    }
  }

  return json({ detail: "Not found." }, { status: 404 });
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ all: string[] }> },
) {
  const path = (await params).all ?? [];
  if (path[0] !== "profile") {
    return json({ detail: "Not found." }, { status: 404 });
  }

  const session = requireSession(request);
  if (!session) {
    return json({ detail: "Authentication required." }, { status: 401 });
  }

  const body = (await request.json().catch(() => ({}))) as { name?: string };
  const name = body.name?.trim() ?? "";
  if (!name) {
    return json({ detail: "Display name is required." }, { status: 400 });
  }

  try {
    const updatedUser = updateUserAccount(session.user.id, { name });
    const { session: nextSession, token } = createSessionForUser(updatedUser);
    return withSessionCookie(json({ session: nextSession }), token);
  } catch (error) {
    return json(
      { detail: error instanceof Error ? error.message : "Failed to update account." },
      { status: 400 },
    );
  }
}

