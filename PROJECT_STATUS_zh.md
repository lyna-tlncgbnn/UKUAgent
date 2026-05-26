# 项目进度 - UKUBot 企业内部协作平台

更新时间：2026-05-08

## 当前主线

这个分支正在从原 agent harness 演进为 UKUBot，一个面向企业内部协作场景的智能 Agent 平台。

当前主线包括：

- 保留现有的 agent / thread / tool / sandbox 核心运行时架构
- 补齐多用户登录、数据归属和服务器部署边界
- 通过 Web 工作台和企业微信提供内部协作入口
- 把上传和生成文件升级为用户归属的资产目录
- 支持定时 agent 任务和任务结果通知
- 给 agent 增加保守的企业 Wiki 工具能力

## 已完成内容

目前已经完成的阶段包括：

### 多用户服务化基础

- Step 01：持久化基础
- Step 02：认证上下文桥接
- Step 03：thread ownership 与按用户搜索
- Step 04：thread 访问控制
- Step 05：文件 ownership 与 metadata
- Step 06：按用户的 memory / profile
- Step 06A：workspace 登录守卫
- Step 06B：账号设置页
- Step 06C：最近对话链路收口
- Step 06D：上传链路收口
- Step 06E：账号预置方案
- Step 06F：企业微信固定对话线程

### 资产目录

- 每个用户有私有的“我的文件”空间
- 支持组织共享文件空间（`org_shared`），不引入匿名公开访问
- 上传文件、转换文件、生成产物、导出包都有持久 metadata
- 已有资产 API 和前端资产工作区
- 支持版本 / 导出第一版语义，可导出 ZIP 资产
- 删除采用软删除，支持恢复
- 关联 thread / scheduled task 删除时，组织共享资产会保留

### 定时任务

- 定时任务持久化和 scheduler runner
- Gateway 侧任务 CRUD 和执行历史 API
- agent 内置对话工具：创建、列表、暂停、恢复、删除、立即执行
- workspace 内已有定时任务列表和详情页
- 执行记录会绑定普通 thread，仍然通过聊天视图查看结果
- 定时任务成功 / 失败结果可以推送到任务 owner 的企业微信私聊

### Confluence Wiki 集成

- `config.yaml` 已增加 `wiki` tool group
- Wiki 地址、账号、密码从代码移到 `.env`
- 已支持 Wiki 页面搜索、读取、权限查看、子页面列表
- 已支持使用 Confluence storage HTML 创建新页面
- 第一版没有提供 Wiki 更新和删除工具

## 当前系统形态

当前运行形态可以这样理解：

- 登录账号目前仍然落在 `backend/.deer-flow/auth/users.json`
- 业务元数据通过 business storage 管理
- LangGraph 的 thread state 通过 checkpointer 持久化
- 会话文件和产物仍然放在 `.deer-flow/threads/<thread_id>/...`
- 资产的私有 / 组织共享通过 metadata 表达，不是单独的共享物理目录
- 定时任务通过 Gateway scheduler 执行，每次执行绑定普通 thread
- 企业微信私聊和 Web 工作台共用每个绑定用户的固定 `企微对话` thread
- Confluence Wiki 通过 `.env` 中的 Basic Auth 配置访问

这是一个有意为之的过渡状态：

- 认证账号先用文件存储跑通闭环
- 业务归属和多用户隔离已经进入结构化存储
- thread 状态已经不再依赖纯内存
- scheduler 目前适合单 Gateway 实例，锁字段已为后续多实例加固预留

## 现在已经可用的能力

- 必须登录后才能进入 workspace
- 最近对话会按当前用户过滤
- 新建对话可以跨重启保留
- 对话标题可以自动生成并保留
- 新对话首条消息带文件时，上传链路已经打通
- 新对话第一次上传图片后，可以立即在消息区正确预览
- 文件已有私有空间和组织共享空间
- workspace 已有定时任务管理和执行历史视图
- 普通对话里可以通过 agent 工具创建和管理定时任务
- 定时任务结果可以通知到 owner 的企业微信私聊
- 绑定企业微信账号的用户有稳定的 `企微对话` Web 入口
- agent 可以搜索 / 读取公司 Wiki 页面、查看页面操作权限、列出子页面，并创建新 Wiki 页面

## 下一步计划

后续将继续推进：

1. Step 07：自定义智能体改造成 `private / org_shared`
2. Step 08：MCP 按角色过滤
3. Step 09：清理剩余开发态 / 单用户全局逻辑
4. Wiki 更新工具需要单独设计确认流程和版本号保护后再开放
5. 定时任务执行后续需要继续加固多 Gateway 实例部署场景

## 相关文档

- 总览入口：
  [docs/multi-user-server/README.md](D:\Project\deer-flow2\docs\multi-user-server\README.md)
- 分步落地记录：
  [docs/multi-user-server](D:\Project\deer-flow2\docs\multi-user-server)
- 资产目录：
  [docs/artifacts/README.md](D:\Project\deer-flow2\docs\artifacts\README.md)
- 定时任务：
  [docs/scheduled-tasks/README.md](D:\Project\deer-flow2\docs\scheduled-tasks\README.md)
- Confluence Wiki 工具：
  [backend/docs/CONFLUENCE_WIKI_TOOLS.md](D:\Project\deer-flow2\backend\docs\CONFLUENCE_WIKI_TOOLS.md)
- 后端配置：
  [backend/docs/CONFIGURATION.md](D:\Project\deer-flow2\backend\docs\CONFIGURATION.md)
- 英文进度说明：
  [PROJECT_STATUS.md](D:\Project\deer-flow2\PROJECT_STATUS.md)

## 备注

- 旧的匿名对话和内存态数据没有做迁移。
- 当前分支仍处在阶段性迁移中，所以有些能力已经是多用户模式，有些还在后续步骤里。
- UKUBot 内部仍保留部分 `deerflow.*` 包名、配置路径和运行时标识，这是为了保持现有运行时兼容。
- 第一版 Wiki 集成即使账号有 update / delete 权限，也不会把更新和删除工具暴露给 agent。
