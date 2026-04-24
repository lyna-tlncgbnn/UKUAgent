import { cookies } from "next/headers";

import { AUTH_SESSION_COOKIE_NAME } from "./shared";
import { getSessionFromToken } from "./config";

export async function getSession() {
  const cookieStore = await cookies();
  const token = cookieStore.get(AUTH_SESSION_COOKIE_NAME)?.value;
  return getSessionFromToken(token);
}
