# Project Status - UKUBot Internal Collaboration Platform

Last updated: 2026-05-08

## Current Focus

This fork is evolving from the original agent harness into UKUBot, an internal
collaboration agent platform for company use.

The current direction is:

- keep the existing agent/thread/tool/sandbox architecture as the core runtime
- add authenticated users and ownership boundaries for server deployment
- provide internal collaboration entry points through Web workspace and WeCom
- turn uploaded/generated files into a user-owned asset catalog
- support scheduled agent work with owner notifications
- expose conservative company Wiki tools to the agent

## What Is Already Done

The following workstreams have already landed:

### Multi-User Server Foundation

- business metadata storage foundation
- auth bridge between Better Auth and Python gateway
- thread ownership and per-user thread search
- thread access enforcement
- file ownership checks and file metadata recording
- per-user memory and profile storage
- workspace login guard and login page
- account/settings panel for current user profile
- recent-chat list closure for logged-in users
- upload flow closure for new-thread + real-thread-id behavior
- shared SQLite checkpointer/store so thread state survives restart
- WeCom fixed thread per bound project user (`企微对话`)

### Asset Catalog

- private "my files" and organization-shared asset spaces
- durable metadata for uploads, converted files, generated artifacts, and export
  packages
- asset listing APIs and frontend asset workspace
- version/export first pass through ZIP export assets
- soft deletion and restore behavior for assets
- organization-shared assets are retained when related threads/tasks are deleted

### Scheduled Tasks

- scheduled task persistence and scheduler runner
- Gateway APIs for task CRUD and run history
- built-in conversation tools for create/list/pause/resume/delete/run-now
- workspace scheduled-task list and detail UI
- execution records linked back to normal chat/thread results
- owner-only WeCom notifications for task success/error results

### Confluence Wiki Integration

- `wiki` tool group in `config.yaml`
- credentials moved to `.env` (`CONFLUENCE_BASE_URL`, `CONFLUENCE_USERNAME`,
  `CONFLUENCE_PASSWORD`)
- read/search/permission/child-page tools for Confluence pages
- page creation tool using Confluence storage HTML
- no update or delete Wiki tools in the first version

## Current Runtime Shape

At this stage, the system works like this:

- auth accounts are currently stored in `backend/.deer-flow/auth/users.json`
- business metadata is stored in the configured `business_storage`
- LangGraph thread state is persisted through the configured `checkpointer`
- local files and artifacts still live under `.deer-flow/threads/<thread_id>/...`
- asset ownership and visibility are represented as metadata, not a separate
  shared filesystem
- scheduled tasks run through the Gateway scheduler and bind executions to
  regular threads
- WeCom private chat uses one fixed thread per bound project user
- Confluence access uses Basic Auth from environment variables

This is an intentional transitional architecture:

- account auth is still file-backed for now
- business ownership data is already moving into structured storage
- LangGraph runtime state is no longer expected to live only in memory
- scheduler locking is present for future hardening, but the current runner is
  intended for a single Gateway instance

## What Works Now

- login is required before entering workspace
- recent chats are filtered to the current user
- new threads can be created and kept across restart
- generated thread titles are persisted
- first-message uploads now use the real thread id
- uploaded images in a brand new thread can render immediately
- files now have a first-class asset catalog with private and organization-shared spaces
- the workspace has scheduled-task management and execution history views
- scheduled tasks can be created from normal conversations through built-in
  tools
- scheduled task results can be pushed back to the owner's WeCom private chat
- bound WeCom users have one stable `企微对话` thread in the Web workspace
- the agent can search/read company Wiki pages, inspect page operations, list
  child pages, and create new Wiki pages

## What Is Next

The next planned work items are:

1. Step 7: custom agents with `private` and `org_shared` visibility
2. Step 8: MCP visibility filtering by role
3. Step 9: cleanup of remaining single-user / dev-only global logic
4. Wiki update workflow design, including confirmation and version protection,
   before exposing any page update tool
5. Hardening scheduled-task execution for multi-Gateway deployments

## Important Docs

- Overall workstream index:
  [docs/multi-user-server/README.md](D:\Project\deer-flow2\docs\multi-user-server\README.md)
- Step-by-step execution records:
  [docs/multi-user-server](D:\Project\deer-flow2\docs\multi-user-server)
- Asset catalog:
  [docs/artifacts/README.md](D:\Project\deer-flow2\docs\artifacts\README.md)
- Scheduled tasks:
  [docs/scheduled-tasks/README.md](D:\Project\deer-flow2\docs\scheduled-tasks\README.md)
- Confluence Wiki tools:
  [backend/docs/CONFLUENCE_WIKI_TOOLS.md](D:\Project\deer-flow2\backend\docs\CONFLUENCE_WIKI_TOOLS.md)
- Backend configuration:
  [backend/docs/CONFIGURATION.md](D:\Project\deer-flow2\backend\docs\CONFIGURATION.md)

## Notes

- Old anonymous/in-memory thread data was not migrated.
- This branch is intentionally in a staged migration, so some subsystems are
  already multi-user aware while later workstreams are still pending.
- UKUBot still uses several `deerflow.*` package names, config paths, and
  runtime identifiers internally for compatibility.
- The first Wiki integration intentionally excludes update/delete tools even
  when the authenticated Confluence account has those permissions.
