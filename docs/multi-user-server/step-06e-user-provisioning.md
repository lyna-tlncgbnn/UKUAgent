# Step 06E - User Provisioning

## Goal
为“首版不开放自助注册”的登录流提供可执行的预置账号方案，并明确开发环境与服务器环境的运维方式。

## What Changed
- 新增脚本：`frontend/scripts/seed-auth-user.mjs`
- 新增命令：`pnpm auth:seed -- --email ... --password ... --name ... [--role admin]`
- 前端 auth store 默认写入：
  - `DEER_FLOW_AUTH_STORE_PATH` 指定路径；若显式配置
  - 否则 `${DEER_FLOW_HOME}/auth/users.json`
  - 本地未设置 `DEER_FLOW_HOME` 时回退到 `backend/.deer-flow/auth/users.json`
- `frontend/src/server/better-auth/config.ts` 新增了基于环境变量的自动 seed 能力：
  - `DEER_FLOW_AUTH_SEED_EMAIL`
  - `DEER_FLOW_AUTH_SEED_PASSWORD`
  - `DEER_FLOW_AUTH_SEED_NAME`
  - `DEER_FLOW_AUTH_SEED_ROLE`
  - 或 `DEER_FLOW_AUTH_SEED_USERS` JSON 数组
- `docker/docker-compose-dev.yaml` 现在会为开发环境默认注入一组 `@mindigitalgroup.com` 测试账号：
  - `admin@mindigitalgroup.com` / `ChangeMe123!` / `admin`
  - `alice@mindigitalgroup.com` / `ChangeMe123!` / `member`
  - `bob@mindigitalgroup.com` / `ChangeMe123!` / `member`
  - `carol@mindigitalgroup.com` / `ChangeMe123!` / `member`
  - `david@mindigitalgroup.com` / `ChangeMe123!` / `member`
- `docker/docker-compose.yaml` 也预留了同一组环境变量，但不在仓库里硬编码生产账号，只从部署环境读取。
- `frontend/.env.example` 增加了认证、seed 用户和 auth store 路径说明。

## Interfaces
- Seed 命令：
  - `pnpm auth:seed -- --email admin@example.com --password ChangeMe123! --name Admin --role admin`
- 相关环境变量：
  - `BETTER_AUTH_SECRET`
  - `DEER_FLOW_AUTH_STORE_PATH`
  - `DEER_FLOW_AUTH_SEED_EMAIL`
  - `DEER_FLOW_AUTH_SEED_PASSWORD`
  - `DEER_FLOW_AUTH_SEED_NAME`
  - `DEER_FLOW_AUTH_SEED_ROLE`
  - `DEER_FLOW_AUTH_SEED_USERS`

## Verification
- 已核对 auth store 解析顺序与 Docker 挂载路径一致。
- 已确认首版账号创建不依赖 UI，而是依赖 seed 脚本或环境变量预置。
- 已将当前多用户 thread 列表依赖的 `business_storage` 在示例配置和本地配置里一并打开。

## Known Limits
- 当前认证用户仍保存在本地 JSON 文件，不是数据库。
- 没有后台用户管理页面；新增/变更用户仍以脚本或部署环境变量为主。
- Docker 开发环境默认账号仅适用于本地联调，服务器部署时必须改成自己的安全密码。
