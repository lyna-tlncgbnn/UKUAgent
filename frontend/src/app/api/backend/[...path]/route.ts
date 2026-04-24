import type { NextRequest } from "next/server";

import { getSession } from "@/server/better-auth/server";

const BACKEND_BASE_URL =
  process.env.DEER_FLOW_INTERNAL_GATEWAY_BASE_URL ??
  process.env.NEXT_PUBLIC_BACKEND_BASE_URL ??
  "http://127.0.0.1:8001";
const AUTH_PROXY_SECRET =
  process.env.DEER_FLOW_AUTH_PROXY_SECRET ?? "deerflow-dev-auth-proxy-secret";

function buildBackendUrl(pathname: string, search: string) {
  const url = new URL(pathname, BACKEND_BASE_URL);
  url.search = search;
  return url;
}

function attachTrustedUserHeaders(
  headers: Headers,
  session: Awaited<ReturnType<typeof getSession>>,
) {
  const user = session?.user;
  if (!user || typeof user !== "object") {
    return;
  }

  const userId = Reflect.get(user, "id");
  if (typeof userId !== "string" || userId.length === 0) {
    return;
  }

  headers.set("x-deerflow-auth-proxy-secret", AUTH_PROXY_SECRET);
  headers.set("x-deerflow-auth-user-id", userId);

  const email = Reflect.get(user, "email");
  if (typeof email === "string" && email.length > 0) {
    headers.set("x-deerflow-auth-user-email", email);
  }

  const name = Reflect.get(user, "name");
  if (typeof name === "string" && name.length > 0) {
    headers.set("x-deerflow-auth-user-name", name);
  }

  const role = Reflect.get(user, "role");
  if (typeof role === "string" && role.length > 0) {
    headers.set("x-deerflow-auth-user-role", role);
  }
}

async function proxyRequest(
  request: NextRequest,
  path: string[],
) {
  const headers = new Headers(request.headers);
  headers.delete("host");
  headers.delete("connection");
  headers.delete("content-length");

  const session = await getSession();
  attachTrustedUserHeaders(headers, session);

  const pathname = `/${path.join("/")}`;
  const hasBody = !["GET", "HEAD"].includes(request.method);
  const response = await fetch(buildBackendUrl(pathname, request.nextUrl.search), {
    method: request.method,
    headers,
    body: hasBody ? await request.arrayBuffer() : undefined,
  });

  return new Response(await response.arrayBuffer(), {
    status: response.status,
    headers: response.headers,
  });
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  return proxyRequest(request, (await params).path);
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  return proxyRequest(request, (await params).path);
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  return proxyRequest(request, (await params).path);
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  return proxyRequest(request, (await params).path);
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  return proxyRequest(request, (await params).path);
}
