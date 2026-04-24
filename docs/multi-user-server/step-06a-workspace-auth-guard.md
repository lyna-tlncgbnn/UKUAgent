# Step 06A - Workspace Auth Guard

## Goal
为 workspace 建立强制登录闭环，停止匿名访问聊天、上传、设置和最近对话。

## What Changed
- 前端认证层从原先未落地的 `better-auth` 占位，改成项目内置的最小 cookie session 实现，入口仍保留在 `frontend/src/server/better-auth/*`。
- 新增独立登录页 `/login`，只支持邮箱密码登录，不开放注册和找回密码。
- `frontend/src/middleware.ts` 现在会拦截 `/workspace/**`，未登录时统一跳转到 `/login?next=...`。
- `frontend/src/app/workspace/layout.tsx` 继续做服务端兜底校验，避免仅凭 cookie 存在就放行。
- 首页 `frontend/src/app/page.tsx` 改为按 session 决定跳转：未登录去 `/login`，已登录去 `/workspace`。
- Next 前端代理 `frontend/src/app/api/backend/[...path]/route.ts` 会继续从当前 session 中读取用户，并把受信任用户头转发给 Python gateway。

## Interfaces
- 新增页面：`/login`
- 认证 API：
  - `GET /api/auth/session`
  - `POST /api/auth/login`
  - `POST /api/auth/logout`
  - `POST /api/auth/change-password`
  - `PATCH /api/auth/profile`

## Verification
- 检查了首页、workspace layout、中间件、登录页和前端代理的链路闭合。
- 当前行为已明确切换为“没有登录 session 就不能进入 workspace”。

## Known Limits
- 首版不开放注册、找回密码、邮箱验证。
- 认证用户当前仍保存在本地 JSON auth store，不是数据库。
- Next 16 对 `middleware.ts` 有 deprecate warning，后续可迁到 `proxy.ts`，但不影响当前功能。
