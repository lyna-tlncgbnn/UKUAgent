# Multi-User Server Upgrade

Last updated: 2026-04-24

## Purpose

This directory tracks the staged migration of this DeerFlow fork from a
single-user local workspace into a multi-user server-ready system.

The implementation strategy is incremental:

- keep the existing DeerFlow runtime architecture
- introduce user identity and ownership boundaries first
- close frontend workflows around those new boundaries
- then continue into shared/private custom agents and role-aware MCP access

## Current Status

Completed:

- Step 01: persistence foundation
- Step 02: auth context bridge
- Step 03: thread ownership and search
- Step 04: thread access enforcement
- Step 05: file ownership and metadata
- Step 06: per-user memory and profile
- Step 06A: workspace auth guard
- Step 06B: account settings
- Step 06C: thread list closure
- Step 06D: upload closure
- Step 06E: user provisioning

Next:

- Step 07: custom agents as `private` / `org_shared`
- Step 08: MCP filtering by role
- Step 09: cleanup of remaining dev-only global logic

## Runtime Decisions Already Made

- Better Auth is the frontend auth entry point.
- Current auth user records are file-backed in
  `backend/.deer-flow/auth/users.json`.
- Thread ownership, file metadata, user memory/profile, and future custom agent
  metadata are moving through the business storage layer.
- LangGraph thread state is now expected to be persistent instead of in-memory
  only.

## Step Documents

- [Step 01 - Persistence Foundation](D:\Project\deer-flow2\docs\multi-user-server\step-01-persistence-foundation.md)
- [Step 02 - Auth Context Bridge](D:\Project\deer-flow2\docs\multi-user-server\step-02-auth-context-bridge.md)
- [Step 03 - Thread Ownership And Search](D:\Project\deer-flow2\docs\multi-user-server\step-03-thread-ownership-and-search.md)
- [Step 04 - Thread Access Enforcement](D:\Project\deer-flow2\docs\multi-user-server\step-04-thread-access-enforcement.md)
- [Step 05 - File Ownership And Metadata](D:\Project\deer-flow2\docs\multi-user-server\step-05-file-ownership-and-metadata.md)
- [Step 06 - User Memory And Profile](D:\Project\deer-flow2\docs\multi-user-server\step-06-user-memory-and-profile.md)
- [Step 06A - Workspace Auth Guard](D:\Project\deer-flow2\docs\multi-user-server\step-06a-workspace-auth-guard.md)
- [Step 06B - Account Settings](D:\Project\deer-flow2\docs\multi-user-server\step-06b-account-settings.md)
- [Step 06C - Thread List Closure](D:\Project\deer-flow2\docs\multi-user-server\step-06c-thread-list-closure.md)
- [Step 06D - Upload Closure](D:\Project\deer-flow2\docs\multi-user-server\step-06d-upload-closure.md)
- [Step 06E - User Provisioning](D:\Project\deer-flow2\docs\multi-user-server\step-06e-user-provisioning.md)

## Current Known Boundaries

- The current checkpoint/store setup is transitional and intended to be moved
  toward PostgreSQL for server deployment.
- Auth storage is still file-backed for now.
- Custom agents are not yet fully migrated to multi-user ownership and
  visibility.
