# Step 06F - WeCom Fixed Thread

## Goal

Give each project user one fixed Enterprise WeChat conversation thread.

The same thread is used from two entry points:

- private chat with the WeCom bot
- Web workspace sidebar item named `企微对话`

This keeps bot messages isolated by project user, prevents cross-user thread
mixing, and gives users one stable Web location for their WeCom conversation.

## Scope

Current supported scope:

- Enterprise WeChat private bot chat only
- no WeCom group chat support
- one fixed WeCom thread per project user
- admin-managed WeCom member ID binding

The implementation assumes the WeCom inbound `user_id` is the company employee
number and is stable. Example: `10300090`.

## Identity Binding

Project users now have an optional unique `wecom_userid` field.

The binding is:

```text
WeCom inbound user_id -> users.wecom_userid -> users.id
```

When a WeCom message arrives:

1. `WecomChannel` keeps the WeCom member ID in `InboundMessage.user_id`.
2. `ChannelManager` looks up `users.wecom_userid`.
3. If no project user is found, the bot replies:

   ```text
   未绑定企业微信账号，请联系管理员绑定工号。
   ```

4. If a project user is found, the fixed WeCom thread is loaded or created for
   that project user.
5. The agent run receives the project user ID through `context.user_id`.

Do not pass the project user ID through both `config.configurable.user_id` and
`context.user_id` for LangGraph Server runs. LangGraph Server 0.6+ rejects
requests that contain both `configurable` and `context`. The WeCom channel path
therefore moves configurable values into `context` before calling
`runs.stream` / `runs.wait`.

## User Provisioning Script

For local testing, use:

```powershell
python scripts\upsert_test_user.py `
  --email tangqiang@mindigitalgroup.com `
  --password poiucctv `
  --name tlncgbnn `
  --wecom-userid 10300090
```

The script updates both stores:

- `backend/.deer-flow/auth/users.json`
  - login email
  - display name
  - password hash
  - role and status
- `backend/.deer-flow/business.db`
  - `users.id`
  - `users.email`
  - `users.name`
  - `users.role`
  - `users.status`
  - `users.wecom_userid`

Repeated execution with the same email updates the existing user instead of
creating a duplicate. The script rejects duplicate `wecom_userid` bindings in
`business.db`.

Batch provisioning is also supported:

```json
[
  {
    "email": "test1@mindigitalgroup.com",
    "password": "Password123",
    "name": "Test User 1",
    "wecom_userid": "10300091"
  }
]
```

```powershell
python scripts\upsert_test_user.py --batch-json .\test-users.json
```

## Thread Records

Each bound project user has exactly one business thread with:

```text
threads.user_id = <project user id>
threads.source = "wecom"
threads.source_user_id = <wecom_userid>
threads.title = "企微对话"
```

The channel store keeps the WeCom mapping:

```json
{
  "wecom:user:10300090": {
    "thread_id": "<fixed-thread-id>",
    "user_id": "10300090",
    "created_at": 1776930483.6725547,
    "updated_at": 1776930483.6725547
  }
}
```

The gateway store also records the thread with:

```json
{
  "metadata": {
    "source": "wecom"
  },
  "values": {
    "title": "企微对话"
  }
}
```

This makes `/api/threads/search` return the thread in the normal recent-chat
list.

## Web Entry

The workspace sidebar contains a fixed `企微对话` item at the same navigation
level as:

- `对话`
- `智能体`
- `定时任务`

Click behavior:

1. Calls `GET /api/channels/wecom/thread`.
2. Receives the current user's fixed WeCom `thread_id`.
3. Ensures the same `thread_id` exists in LangGraph Server by calling
   `threads.create({ threadId, graphId: "lead_agent", ifExists: "do_nothing" })`.
4. Navigates to `/workspace/chats/<thread_id>`.

The LangGraph Server creation step is required because the Web chat stream
uses the LangGraph SDK against `/api/langgraph`, while the gateway endpoint
owns business metadata and ownership records. If only the gateway store exists,
Web sends can fail with:

```text
Thread or assistant not found.
```

The same open behavior is also used when the user clicks `企微对话` from the
recent-chat list, so old gateway records cannot bypass LangGraph thread
creation.

## WeCom Inbound Flow

For a bound user:

1. WeCom message arrives with `InboundMessage.user_id=<wecom_userid>`.
2. `ChannelManager` resolves the project user via `users.wecom_userid`.
3. The manager reuses the existing `wecom:user:<wecom_userid>` channel-store
   mapping when present.
4. If the channel-store mapping is missing, it reuses the existing business
   thread with `source="wecom"` for that project user.
5. If no thread exists, it creates a LangGraph Server thread and then writes:
   - channel-store mapping
   - business thread record
   - gateway store thread record
6. The message is sent to LangGraph Server through `runs.stream`.
7. The final response is sent back to the WeCom private chat.

## Thread Operation Rules

WeCom threads have fixed product semantics:

- title is always `企微对话`
- no rename action in the Web recent-chat menu
- no delete action in the Web recent-chat menu
- backend rejects deleting a `source="wecom"` thread
- backend rejects title mutation for a `source="wecom"` thread

The user can clear chat history instead.

## Clear Chat History

`POST /api/channels/wecom/thread/clear` clears the current user's WeCom thread
without changing the identity of the thread.

Preserved:

- `thread_id`
- `threads` business record
- channel-store mapping
- gateway store thread record
- title `企微对话`
- `source="wecom"`
- `source_user_id=<wecom_userid>`

Cleared:

- visible message history
- agent checkpoint history
- local thread files
- upload and artifact records for that thread

After clearing, an empty checkpoint is written again so the Web chat page can
continue using the same fixed thread.

## APIs

### `GET /api/channels/wecom/thread`

Requires login.

Returns the current user's fixed WeCom thread, creating it when necessary:

```json
{
  "thread_id": "<thread-id>",
  "title": "企微对话"
}
```

Failure cases:

- `401`: not logged in
- `400`: current user has no `wecom_userid`
- `503`: business store unavailable

### `POST /api/channels/wecom/thread/clear`

Requires login.

Clears only the current user's fixed WeCom thread:

```json
{
  "success": true,
  "thread_id": "<thread-id>",
  "title": "企微对话"
}
```

Failure cases:

- `401`: not logged in
- `404`: current user has no WeCom thread
- `503`: business store unavailable

## Files Touched

Backend:

- `backend/app/persistence/models.py`
- `backend/app/persistence/store.py`
- `backend/app/channels/manager.py`
- `backend/app/channels/service.py`
- `backend/app/gateway/app.py`
- `backend/app/gateway/routers/channels.py`
- `backend/app/gateway/routers/threads.py`
- `scripts/upsert_test_user.py`

Frontend:

- `frontend/src/components/workspace/workspace-nav-chat-list.tsx`
- `frontend/src/components/workspace/recent-chat-list.tsx`
- `frontend/src/core/threads/api.ts`
- `frontend/src/core/threads/hooks.ts`
- `frontend/src/core/i18n/locales/types.ts`
- `frontend/src/core/i18n/locales/zh-CN.ts`
- `frontend/src/core/i18n/locales/en-US.ts`

Tests:

- `backend/tests/test_business_storage.py`
- `backend/tests/test_channels.py`
- `backend/tests/test_threads_router.py`

## Troubleshooting

### Web send shows `Thread or assistant not found`

Cause: the fixed thread exists in gateway/business storage, but not in
LangGraph Server.

Resolution: open the thread through the sidebar `企微对话` entry or the recent
chat item after the current fix. Both paths call LangGraph
`threads.create(..., ifExists: "do_nothing")` before navigation.

### WeCom bot replies with generic processing error

Check `gateway.log`.

If the error is:

```text
Cannot specify both configurable and context.
```

then the channel path is sending both `config.configurable` and `context` to
LangGraph Server. The fixed implementation moves configurable values into
`context` before calling `runs.stream` or `runs.wait`.

### WeCom message says the account is unbound

Check that `users.wecom_userid` in `business.db` matches the WeCom inbound
member ID. For local testing, re-run:

```powershell
python scripts\upsert_test_user.py --email <email> --password <password> --name <name> --wecom-userid <employee-id>
```

### Thread appears in recent chats but clear/delete behavior is wrong

Check the thread metadata and business source:

- gateway store metadata should include `source="wecom"`
- business thread should have `source="wecom"`

The frontend hides rename/delete based on gateway store metadata, while backend
delete/title protection uses the business thread source.

## Verification

Recommended checks:

- Login as a user with `wecom_userid`.
- Click sidebar `企微对话`; verify navigation to `/workspace/chats/<thread_id>`.
- Verify `企微对话` appears in recent chats.
- Send a Web message in that thread.
- Send a private WeCom bot message from the bound employee account.
- Confirm both messages land in the same thread.
- Confirm another bound user gets a different fixed thread.
- Confirm unbound WeCom users receive the binding prompt and no thread is
  created.
- Confirm WeCom thread cannot be deleted or renamed.
- Confirm clear history keeps the same `thread_id` and future Web/WeCom sends
  still work.
