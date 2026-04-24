import crypto from "crypto";
import fs from "fs";
import path from "path";

const MIN_PASSWORD_LENGTH = 8;

function usage() {
  console.log(
    "Usage: node scripts/seed-auth-user.mjs --email user@example.com --password secret123 --name \"User\" [--role admin|member]",
  );
}

function parseArgs(argv) {
  const args = {};
  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (!arg.startsWith("--")) continue;
    args[arg.slice(2)] = argv[index + 1];
    index += 1;
  }
  return args;
}

function resolveStorePath() {
  if (process.env.DEER_FLOW_AUTH_STORE_PATH) {
    return path.resolve(process.env.DEER_FLOW_AUTH_STORE_PATH);
  }
  if (process.env.DEER_FLOW_HOME) {
    return path.resolve(process.env.DEER_FLOW_HOME, "auth", "users.json");
  }
  return path.resolve(process.cwd(), "../backend/.deer-flow/auth/users.json");
}

function readStore(storePath) {
  fs.mkdirSync(path.dirname(storePath), { recursive: true });
  if (!fs.existsSync(storePath)) {
    return { version: 1, users: [] };
  }
  return JSON.parse(fs.readFileSync(storePath, "utf-8"));
}

function writeStore(storePath, store) {
  fs.writeFileSync(storePath, JSON.stringify(store, null, 2), "utf-8");
}

function hashPassword(password) {
  if (password.length < MIN_PASSWORD_LENGTH) {
    throw new Error(`Password must be at least ${MIN_PASSWORD_LENGTH} characters.`);
  }
  const salt = crypto.randomBytes(16).toString("hex");
  const hash = crypto.scryptSync(password, salt, 64).toString("hex");
  return `scrypt:${salt}:${hash}`;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const email = args.email?.trim().toLowerCase();
  const password = args.password ?? "";
  const name = args.name?.trim();
  const role = args.role === "admin" ? "admin" : "member";

  if (!email || !password || !name) {
    usage();
    process.exitCode = 1;
    return;
  }

  const storePath = resolveStorePath();
  const store = readStore(storePath);
  const now = new Date().toISOString();
  const passwordHash = hashPassword(password);

  const existing = store.users.find((user) => user.email === email);
  if (existing) {
    existing.name = name;
    existing.role = role;
    existing.status = "active";
    existing.passwordHash = passwordHash;
    existing.updatedAt = now;
  } else {
    store.users.push({
      id: crypto.randomBytes(12).toString("hex"),
      email,
      name,
      role,
      status: "active",
      passwordHash,
      createdAt: now,
      updatedAt: now,
    });
  }

  writeStore(storePath, store);
  console.log(`Seeded auth user: ${email}`);
  console.log(`Store path: ${storePath}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

