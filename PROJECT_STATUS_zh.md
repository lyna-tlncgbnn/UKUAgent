# 项目进度 - 多用户服务化改造

最后更新：2026-04-24

## 当前主线

这个分支正在把当前项目从“单用户本地工作台”逐步改造成“可部署到服务器、支持多用户登录和数据隔离”的版本。

当前改造原则保持不变：

- 保留 DeerFlow 现有的 agent / thread / tool / sandbox 主架构
- 先补用户身份与数据归属
- 再补前端登录闭环和工作流收口
- 然后继续推进智能体共享能力与 MCP 权限控制

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
- Step 07：智能体 `private / org_shared` 可见性改造

## 当前系统形态

当前运行形态可以这样理解：

- 登录账号目前仍然存放在 `backend/.deer-flow/auth/users.json`
- 业务元数据通过 business storage 管理
- LangGraph 的 thread state 通过 checkpointer 持久化
- 会话文件和产物仍然存放在 `.deer-flow/threads/<thread_id>/...`
- 自定义智能体的 ownership / visibility 已经进入业务存储，但运行时仍保留文件镜像兼容层

这是一个有意为之的过渡状态：

- 认证账号先用文件存储把多用户闭环跑通
- 业务归属和多用户隔离已经进入结构化存储
- thread 状态不再依赖纯内存
- 智能体开始从全局文件式实现迁移到 owner/shared 模式

## 现在已经可用的能力

- 必须登录后才能进入 workspace
- 最近对话会按当前用户过滤
- 新建对话可以跨重启保留
- 对话标题可以自动生成并持久化
- 新对话首条消息携带文件时，上传链路已经打通
- 新对话首次上传图片后，可以立即在消息区正确显示
- 自定义智能体已经支持：
  - 私有
  - 组织共享
- 智能体列表会区分：
  - 我的智能体
  - 组织共享智能体
- 非 owner 不能删除他人的智能体

## 下一步计划

后续将继续推进：

1. Step 08：MCP 按角色过滤
2. Step 09：清理剩余开发态 / 单用户全局逻辑

## 相关文档

- 总览入口：
  [docs/multi-user-server/README.md](D:\Project\deer-flow2\docs\multi-user-server\README.md)
- 分步落地记录：
  [docs/multi-user-server](D:\Project\deer-flow2\docs\multi-user-server)
- 英文进度说明：
  [PROJECT_STATUS.md](D:\Project\deer-flow2\PROJECT_STATUS.md)

## 备注

- 旧的匿名对话和内存态数据没有做迁移。
- 当前分支仍处在阶段性迁移中，所以有些能力已经是多用户模式，有些能力还在后续步骤里。
