import { randomBytes, createHmac, scryptSync, timingSafeEqual } from "crypto";
import fs from "fs";
import path from "path";

import { env } from "@/env";

import {
  AUTH_SESSION_COOKIE_NAME,
  AUTH_SESSION_TTL_SECONDS,
  MIN_PASSWORD_LENGTH,
  type AuthSession,
  type AuthSessionUser,
  type AuthUserRecord,
  type AuthUserRole,
  type AuthUserStatus,
} from "./shared";

type AuthStore = {
  version: 1;
  users: AuthUserRecord[];
};

type SeedUserInput = {
  email: string;
  password: string;
  name: string;
  role?: AuthUserRole;
  status?: AuthUserStatus;
};

const AUTH_STORE_VERSION = 1;

function ensureAuthSecret() {
  return env.BETTER_AUTH_SECRET ?? "deerflow-dev-auth-secret";
}

function resolveAuthStorePath() {
  if (process.env.DEER_FLOW_AUTH_STORE_PATH) {
    return path.resolve(process.env.DEER_FLOW_AUTH_STORE_PATH);
  }

  if (process.env.DEER_FLOW_HOME) {
    return path.resolve(process.env.DEER_FLOW_HOME, "auth", "users.json");
  }

  const cwd = process.cwd();
  if (path.basename(cwd) === "frontend") {
    return path.resolve(cwd, "../backend/.deer-flow/auth/users.json");
  }

  return path.resolve(cwd, "backend/.deer-flow/auth/users.json");
}

function ensureAuthStoreDir() {
  const storePath = resolveAuthStorePath();
  fs.mkdirSync(path.dirname(storePath), { recursive: true });
  return storePath;
}

function parseSeedUsersFromEnv(): SeedUserInput[] {
  const seeds: SeedUserInput[] = [];

  const singleEmail = process.env.DEER_FLOW_AUTH_SEED_EMAIL?.trim();
  const singlePassword = process.env.DEER_FLOW_AUTH_SEED_PASSWORD ?? "";
  const singleName = process.env.DEER_FLOW_AUTH_SEED_NAME?.trim();
  const singleRole = process.env.DEER_FLOW_AUTH_SEED_ROLE as AuthUserRole | undefined;

  if (singleEmail && singlePassword && singleName) {
    seeds.push({
      email: singleEmail,
      password: singlePassword,
      name: singleName,
      role: singleRole === "admin" ? "admin" : "member",
      status: "active",
    });
  }

  const jsonPayload = process.env.DEER_FLOW_AUTH_SEED_USERS;
  if (!jsonPayload) {
    return seeds;
  }

  try {
    const parsed = JSON.parse(jsonPayload) as unknown;
    if (!Array.isArray(parsed)) {
      return seeds;
    }

    for (const item of parsed) {
      if (typeof item !== "object" || item === null) {
        continue;
      }
      const email = Reflect.get(item, "email");
      const password = Reflect.get(item, "password");
      const name = Reflect.get(item, "name");
      const role = Reflect.get(item, "role");
      const status = Reflect.get(item, "status");
      if (
        typeof email !== "string" ||
        typeof password !== "string" ||
        typeof name !== "string" ||
        !email.trim() ||
        !password ||
        !name.trim()
      ) {
        continue;
      }

      seeds.push({
        email,
        password,
        name,
        role: role === "admin" ? "admin" : "member",
        status: status === "disabled" ? "disabled" : "active",
      });
    }
  } catch {
    return seeds;
  }

  return seeds;
}

function mergeSeedUsers(store: AuthStore): AuthStore {
  const nextStore: AuthStore = {
    version: AUTH_STORE_VERSION,
    users: [...store.users],
  };
  const now = new Date().toISOString();

  for (const seed of parseSeedUsersFromEnv()) {
    const email = normalizeEmail(seed.email);
    const existing = nextStore.users.find((user) => user.email === email);
    if (existing) {
      const nextRole = seed.role ?? existing.role;
      const nextStatus = seed.status ?? existing.status;
      const needsPasswordUpdate = !verifyPassword(seed.password, existing.passwordHash);
      if (
        existing.name !== seed.name.trim() ||
        existing.role !== nextRole ||
        existing.status !== nextStatus ||
        needsPasswordUpdate
      ) {
        existing.name = seed.name.trim();
        existing.role = nextRole;
        existing.status = nextStatus;
        if (needsPasswordUpdate) {
          existing.passwordHash = hashPassword(seed.password);
        }
        existing.updatedAt = now;
      }
      continue;
    }

    nextStore.users.push({
      id: randomBytes(12).toString("hex"),
      email,
      name: seed.name.trim(),
      passwordHash: hashPassword(seed.password),
      role: seed.role ?? "member",
      status: seed.status ?? "active",
      createdAt: now,
      updatedAt: now,
    });
  }

  return nextStore;
}

function readAuthStore(): AuthStore {
  const storePath = ensureAuthStoreDir();
  if (!fs.existsSync(storePath)) {
    const seeded = mergeSeedUsers({ version: AUTH_STORE_VERSION, users: [] });
    writeAuthStore(seeded);
    return seeded;
  }

  try {
    const raw = fs.readFileSync(storePath, "utf-8");
    const parsed = JSON.parse(raw) as Partial<AuthStore>;
    if (!parsed || !Array.isArray(parsed.users)) {
      const seeded = mergeSeedUsers({ version: AUTH_STORE_VERSION, users: [] });
      writeAuthStore(seeded);
      return seeded;
    }
    const store = {
      version: AUTH_STORE_VERSION,
      users: parsed.users.filter((user): user is AuthUserRecord => {
        return (
          typeof user?.id === "string" &&
          typeof user?.email === "string" &&
          typeof user?.name === "string" &&
          typeof user?.passwordHash === "string" &&
          (user?.role === "admin" || user?.role === "member") &&
          (user?.status === "active" || user?.status === "disabled") &&
          typeof user?.createdAt === "string" &&
          typeof user?.updatedAt === "string"
        );
      }),
    };
    const merged = mergeSeedUsers(store);
    if (JSON.stringify(merged) !== JSON.stringify(store)) {
      writeAuthStore(merged);
    }
    return merged;
  } catch {
    const seeded = mergeSeedUsers({ version: AUTH_STORE_VERSION, users: [] });
    writeAuthStore(seeded);
    return seeded;
  }
}

function writeAuthStore(store: AuthStore) {
  const storePath = ensureAuthStoreDir();
  fs.writeFileSync(storePath, JSON.stringify(store, null, 2), "utf-8");
}

function normalizeEmail(email: string) {
  return email.trim().toLowerCase();
}

function assertPasswordStrength(password: string) {
  if (password.length < MIN_PASSWORD_LENGTH) {
    throw new Error(`Password must be at least ${MIN_PASSWORD_LENGTH} characters.`);
  }
}

function hashPassword(password: string) {
  assertPasswordStrength(password);
  const salt = randomBytes(16).toString("hex");
  const hash = scryptSync(password, salt, 64).toString("hex");
  return `scrypt:${salt}:${hash}`;
}

function verifyPassword(password: string, passwordHash: string) {
  const [algorithm, salt, storedHash] = passwordHash.split(":");
  if (algorithm !== "scrypt" || !salt || !storedHash) {
    return false;
  }

  const incoming = scryptSync(password, salt, 64);
  const expected = Buffer.from(storedHash, "hex");
  if (incoming.byteLength !== expected.byteLength) {
    return false;
  }

  return timingSafeEqual(incoming, expected);
}

function userToSessionUser(user: AuthUserRecord): AuthSessionUser {
  return {
    id: user.id,
    email: user.email,
    name: user.name,
    role: user.role,
    status: user.status,
  };
}

function signSessionPayload(payload: AuthSession) {
  const body = Buffer.from(JSON.stringify(payload)).toString("base64url");
  const signature = createHmac("sha256", ensureAuthSecret()).update(body).digest("base64url");
  return `${body}.${signature}`;
}

function verifySessionPayload(token: string): AuthSession | null {
  const [body, signature] = token.split(".");
  if (!body || !signature) {
    return null;
  }

  const expected = createHmac("sha256", ensureAuthSecret()).update(body).digest("base64url");
  if (signature !== expected) {
    return null;
  }

  try {
    const payload = JSON.parse(Buffer.from(body, "base64url").toString("utf-8")) as AuthSession;
    if (!payload?.user?.id || !payload?.expiresAt) {
      return null;
    }
    const expiresAt = Date.parse(payload.expiresAt);
    if (Number.isNaN(expiresAt) || expiresAt <= Date.now()) {
      return null;
    }
    return payload;
  } catch {
    return null;
  }
}

export function createSessionForUser(user: AuthUserRecord) {
  const session: AuthSession = {
    user: userToSessionUser(user),
    expiresAt: new Date(Date.now() + AUTH_SESSION_TTL_SECONDS * 1000).toISOString(),
  };
  return {
    session,
    token: signSessionPayload(session),
  };
}

export function getSessionFromToken(token: string | null | undefined) {
  if (!token) {
    return null;
  }

  const payload = verifySessionPayload(token);
  if (!payload) {
    return null;
  }

  const user = getUserById(payload.user.id);
  if (!user || user.status !== "active") {
    return null;
  }

  return {
    user: userToSessionUser(user),
    expiresAt: payload.expiresAt,
  } satisfies AuthSession;
}

export function getUserByEmail(email: string) {
  const normalizedEmail = normalizeEmail(email);
  return readAuthStore().users.find((user) => user.email === normalizedEmail) ?? null;
}

export function getUserById(userId: string) {
  return readAuthStore().users.find((user) => user.id === userId) ?? null;
}

export function authenticateUser(email: string, password: string) {
  const user = getUserByEmail(email);
  if (!user || user.status !== "active") {
    return null;
  }
  if (!verifyPassword(password, user.passwordHash)) {
    return null;
  }
  return user;
}

export function updateUserAccount(userId: string, updates: { name?: string }) {
  const store = readAuthStore();
  const record = store.users.find((user) => user.id === userId);
  if (!record) {
    throw new Error("User not found.");
  }

  if (typeof updates.name === "string") {
    const nextName = updates.name.trim();
    if (!nextName) {
      throw new Error("Display name cannot be empty.");
    }
    record.name = nextName;
  }

  record.updatedAt = new Date().toISOString();
  writeAuthStore(store);
  return record;
}

export function updateUserPassword(userId: string, currentPassword: string, newPassword: string) {
  const store = readAuthStore();
  const record = store.users.find((user) => user.id === userId);
  if (!record) {
    throw new Error("User not found.");
  }
  if (!verifyPassword(currentPassword, record.passwordHash)) {
    throw new Error("Current password is incorrect.");
  }
  record.passwordHash = hashPassword(newPassword);
  record.updatedAt = new Date().toISOString();
  writeAuthStore(store);
  return record;
}

export function upsertSeedUser(input: SeedUserInput) {
  const email = normalizeEmail(input.email);
  const name = input.name.trim();
  if (!email) {
    throw new Error("Email is required.");
  }
  if (!name) {
    throw new Error("Name is required.");
  }

  const store = readAuthStore();
  const now = new Date().toISOString();
  const existing = store.users.find((user) => user.email === email);

  if (existing) {
    existing.name = name;
    existing.passwordHash = hashPassword(input.password);
    existing.role = input.role ?? existing.role;
    existing.status = input.status ?? existing.status;
    existing.updatedAt = now;
    writeAuthStore(store);
    return existing;
  }

  const created: AuthUserRecord = {
    id: randomBytes(12).toString("hex"),
    email,
    name,
    passwordHash: hashPassword(input.password),
    role: input.role ?? "member",
    status: input.status ?? "active",
    createdAt: now,
    updatedAt: now,
  };
  store.users.push(created);
  writeAuthStore(store);
  return created;
}

export function listSeedUsers() {
  return readAuthStore().users.map((user) => ({
    id: user.id,
    email: user.email,
    name: user.name,
    role: user.role,
    status: user.status,
    createdAt: user.createdAt,
    updatedAt: user.updatedAt,
  }));
}

export function getSessionCookieOptions() {
  return {
    name: AUTH_SESSION_COOKIE_NAME,
    httpOnly: true,
    sameSite: "lax" as const,
    secure: env.NODE_ENV === "production",
    path: "/",
    maxAge: AUTH_SESSION_TTL_SECONDS,
  };
}
