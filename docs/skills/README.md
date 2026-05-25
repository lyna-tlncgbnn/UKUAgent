# Skills Workspace Management

Last updated: 2026-05-25

## Purpose

The Skills workspace page gives users a first-level place to inspect and manage
agent skills without opening the settings dialog or creating skills through a
conversation first.

It supports:

- browsing built-in `public` skills and user-installed `custom` skills
- enabling or disabling skills
- uploading `.skill` archives into `skills/custom/`
- opening skill details to inspect metadata, `SKILL.md`, and helper files
- editing files inside custom skills
- creating, renaming, and deleting non-`SKILL.md` files inside custom skills
- deleting custom skills

## UI Behavior

The page is available at `/workspace/skills` and appears in the workspace
sidebar alongside chats, agents, scheduled tasks, and files.

The detail dialog uses a fixed viewport-relative height so file switching does
not resize the dialog while content is loading. The left pane is a file list and
the right pane is a preview/editor area. Long content scrolls inside the dialog.

Public skills are read-only. They can be viewed and toggled, but their files
cannot be edited, renamed, created, or deleted from the UI.

Custom skills can be edited in place. `SKILL.md` can be saved after editing, but
it cannot be renamed or deleted because it is the required skill entrypoint.

## Skill Package Requirements

Manual installation uses a `.skill` file, which is a ZIP archive.

Expected archive structure:

```text
my-skill/
  SKILL.md
  scripts/
  references/
  templates/
```

`SKILL.md` must contain frontmatter with at least `name` and `description`:

```markdown
---
name: my-skill
description: Describe what this skill does
---

# My Skill
```

Skill names must use lowercase letters, digits, and hyphens. They cannot start
or end with a hyphen.

## Backend API Summary

The Gateway exposes Skills management under `/api/skills`.

- `GET /api/skills` lists public and custom skills.
- `GET /api/skills/{skill_name}` returns summary metadata.
- `PUT /api/skills/{skill_name}` updates enabled state.
- `POST /api/skills/install` installs a `.skill` archive from a thread artifact.
- `POST /api/skills/upload` uploads and installs a `.skill` archive directly.
- `GET /api/skills/{skill_name}/detail` returns metadata, `SKILL.md`, and file list.
- `GET /api/skills/{skill_name}/files/{file_path}` reads a UTF-8 text file.
- `PUT /api/skills/{skill_name}/files/{file_path}` saves a custom skill file.
- `POST /api/skills/{skill_name}/files` creates a custom skill file.
- `PATCH /api/skills/{skill_name}/files/{file_path}` renames a custom skill file.
- `DELETE /api/skills/{skill_name}/files/{file_path}` deletes a custom skill file.
- `DELETE /api/skills/{skill_name}` deletes a custom skill directory.

All skill file paths are relative to the skill directory. Absolute paths,
empty paths, and traversal paths such as `..` are rejected.

## Runtime Decisions

- Skills are a top-level workspace asset, not a settings-only configuration.
- Custom skill deletion physically removes the skill directory.
- File editing is text-only and expects UTF-8 content.
- Public skills remain read-only from the file management API.
- When a custom skill and public skill share the same name, file detail and file
  operations prefer the custom skill.
- Saving `SKILL.md` validates frontmatter and rejects attempts to change the
  skill name.
- `NEXT_PUBLIC_STATIC_WEBSITE_ONLY=true` keeps the UI read-only.

## Verification

Targeted checks for this workstream:

```bash
cd backend
uv run pytest tests/test_skills_router.py
uv run ruff check app/gateway/routers/skills.py tests/test_skills_router.py

cd frontend
corepack pnpm typecheck
.\node_modules\.bin\eslint.cmd src/components/workspace/skills/skill-workspace-page.tsx src/components/workspace/code-editor.tsx src/core/skills/api.ts src/core/skills/hooks.ts src/core/skills/type.ts src/core/i18n/locales/types.ts src/core/i18n/locales/en-US.ts src/core/i18n/locales/zh-CN.ts
```

## Known Boundaries

- Whole-skill rename is not supported.
- Overwrite install, version upgrades, and rollback are not supported.
- Binary files are not previewed or edited.
- Auxiliary files are listed and editable, but only `SKILL.md` content is used
  for skill metadata validation.
