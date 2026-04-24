# Project Status - Multi-User Server Upgrade

Last updated: 2026-04-24

## Current Focus

This fork is in the middle of a large upgrade from a single-user local workspace
to a multi-user server-oriented deployment.

The main direction is:

- keep the existing DeerFlow agent/thread/tool/sandbox architecture
- add authenticated users
- add per-user ownership for threads, files, memory, and profile data
- make runtime state persistent across restarts
- prepare custom agents for `private` and `org_shared` visibility

## What Is Already Done

The following workstreams have already landed:

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
- custom agents with owner-aware `private` / `org_shared` visibility

## Current Runtime Shape

At this stage, the system works like this:

- auth accounts are currently stored in `backend/.deer-flow/auth/users.json`
- business metadata is stored in the configured `business_storage`
- LangGraph thread state is persisted through the configured `checkpointer`
- local files and artifacts still live under `.deer-flow/threads/<thread_id>/...`

This is an intentional transitional architecture:

- account auth is still file-backed for now
- business ownership data is already moving into structured storage
- LangGraph runtime state is no longer expected to live only in memory

## What Works Now

- login is required before entering workspace
- recent chats are filtered to the current user
- new threads can be created and kept across restart
- generated thread titles are persisted
- first-message uploads now use the real thread id
- uploaded images in a brand new thread can render immediately

## What Is Next

The next planned work items are:

1. Step 8: MCP visibility filtering by role
2. Step 9: cleanup of remaining single-user / dev-only global logic

## Important Docs

- Overall workstream index:
  [docs/multi-user-server/README.md](D:\Project\deer-flow2\docs\multi-user-server\README.md)
- Step-by-step execution records:
  [docs/multi-user-server](D:\Project\deer-flow2\docs\multi-user-server)

## Notes

- Old anonymous/in-memory thread data was not migrated.
- This branch is intentionally in a staged migration, so some subsystems are
  already multi-user aware while later workstreams are still pending.
