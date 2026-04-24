# Step 06C - Thread List Closure

## Goal
把“最近对话只显示当前用户 thread”这条链路真正收口到前端产品层，避免出现 thread 已创建但左侧列表空白、或错误态和空态混在一起的情况。

## What Changed
- `frontend/src/core/threads/hooks.ts` 已在“新对话首次发送消息”时先创建 thread，再上传文件、再提交消息，并在 `onCreated`/`onStart` 后用真实 `thread_id` 切换页面 URL。
- 额外修复了一个关键闭环问题：新对话页不再把路由占位值 `new` 当成真实 `thread_id` 传进发送逻辑；底层 `useThreadStream.sendMessage()` 也会把 `new` 归一化为空，再触发 gateway 创建 thread。
- `frontend/src/app/workspace/chats/[thread_id]/page.tsx` 和 `frontend/src/app/workspace/agents/[agent_name]/chats/[thread_id]/page.tsx` 已修正为使用真实启动出来的 `thread_id` 替换路由。
- `frontend/src/components/workspace/recent-chat-list.tsx` 现在区分三类状态：
  - 正在加载
  - 鉴权/请求失败
  - 确实没有最近对话
- `frontend/src/core/threads/api.ts` 和 gateway `/api/threads/search` 继续沿用“按当前用户过滤 thread”的设计。
- 本轮还同步把 `config.yaml` 和 `config.example.yaml` 中的 `business_storage` 打开，避免 `threads/search` 因业务库未启用而直接 503。

## Interfaces
- `POST /api/threads`
- `POST /api/threads/search`
- `POST /api/threads/{thread_id}/state`

## Verification
- 已对 thread 创建、路由替换、最近对话查询、空态/错误态渲染逻辑逐个检查。
- 当前依赖前提已明确：业务库必须启用，否则按用户过滤的 thread 列表无法工作。

## Known Limits
- 旧匿名 thread 不做迁移；多人模式下默认视为不可见。
- 如果当前运行环境没有重启并加载新的 `business_storage` 配置，左侧列表仍会继续报 503。
## Post Fix Note (2026-04-24)
- Fixed a follow-up regression in the new-thread flow: `useThreadChat()` no longer fabricates a placeholder UUID for `/workspace/chats/new`.
- The hook now tracks the actual route param, so once the page is rewritten to the real `thread_id`, later requests such as suggestions, uploads, and subsequent sends stop targeting a fake thread.
- The chat pages now also write `startedThreadId` back into local page state during `onStart`, so UI-level consumers stop holding onto a stale thread id between `history.replaceState(...)` and the next route sync.
- Gateway thread search now refreshes existing store-backed entries with checkpoint-derived `title` values, which allows the recent-chat list to pick up the generated title instead of staying on `Untitled`.
