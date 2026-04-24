# 项目进度 - 多用户服务化改造

更新时间：2026-04-24

## 当前主线

这个分支正在把当前项目从“单用户本地工作台”逐步改造成“可部署到服务器、支持多用户登录和数据隔离”的版本。

改造原则没有变：

- 保留 DeerFlow 现有的 agent / thread / tool / sandbox 主架构
- 先补用户身份和数据归属
- 再补前端登录闭环和工作流收口
- 最后继续做智能体私有/共享和 MCP 权限控制

## 已完成内容

目前已经完成的阶段包括：

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

## 当前系统形态

当前运行形态可以这样理解：

- 登录账号目前仍然落在 `backend/.deer-flow/auth/users.json`
- 业务元数据通过 business storage 管理
- LangGraph 的 thread state 通过 checkpointer 持久化
- 会话文件和产物仍然放在 `.deer-flow/threads/<thread_id>/...`

这是一个有意为之的过渡状态：

- 认证账号先用文件存储跑通闭环
- 业务归属和多用户隔离已经进入结构化存储
- thread 状态已经不再依赖纯内存

## 现在已经可用的能力

- 必须登录后才能进入 workspace
- 最近对话会按当前用户过滤
- 新建对话可以跨重启保留
- 对话标题可以自动生成并保留
- 新对话首条消息带文件时，上传链路已经打通
- 新对话第一次上传图片后，可以立即在消息区正确预览

## 下一步计划

后续将继续推进：

1. Step 07：自定义智能体改造成 `private / org_shared`
2. Step 08：MCP 按角色过滤
3. Step 09：清理剩余开发态 / 单用户全局逻辑

## 相关文档

- 总览入口：
  [docs/multi-user-server/README.md](D:\Project\deer-flow2\docs\multi-user-server\README.md)
- 分步落地记录：
  [docs/multi-user-server](D:\Project\deer-flow2\docs\multi-user-server)
- 英文进度说明：
  [PROJECT_STATUS.md](D:\Project\deer-flow2\PROJECT_STATUS.md)

## 备注

- 旧的匿名对话和内存态数据没有做迁移。
- 当前分支仍处在阶段性迁移中，所以有些能力已经是多用户模式，有些还在后续步骤里。
