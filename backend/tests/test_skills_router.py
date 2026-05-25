import json
import zipfile
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.gateway.routers.skills as skills_router
from deerflow.config.extensions_config import ExtensionsConfig, SkillStateConfig
from deerflow.skills.installer import install_skill_from_archive
from deerflow.skills.loader import load_skills


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(skills_router.router)
    return app


def _make_skill_archive(tmp_path: Path, skill_name: str = "uploaded-skill") -> Path:
    archive = tmp_path / f"{skill_name}.skill"
    with zipfile.ZipFile(archive, "w") as zip_ref:
        zip_ref.writestr(
            f"{skill_name}/SKILL.md",
            f"---\nname: {skill_name}\ndescription: Uploaded skill\n---\n\n# {skill_name}\n",
        )
    return archive


def _write_skill(skills_root: Path, category: str, skill_name: str, *, extra_file: bool = False) -> Path:
    skill_dir = skills_root / category / skill_name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {skill_name}\ndescription: {category} skill\n---\n\n# {skill_name}\n",
        encoding="utf-8",
    )
    if extra_file:
        (skill_dir / "references").mkdir()
        (skill_dir / "references" / "guide.md").write_text("guide", encoding="utf-8")
    return skill_dir


def test_upload_skill_installs_valid_archive(tmp_path, monkeypatch):
    skills_root = tmp_path / "skills"

    def install_with_test_root(path):
        return install_skill_from_archive(path, skills_root=skills_root)

    monkeypatch.setattr(skills_router, "install_skill_from_archive", install_with_test_root)

    archive = _make_skill_archive(tmp_path)
    app = _build_app()

    with TestClient(app) as client:
        response = client.post(
            "/api/skills/upload",
            files={"file": ("uploaded-skill.skill", archive.read_bytes(), "application/zip")},
        )

    assert response.status_code == 200
    assert response.json()["skill_name"] == "uploaded-skill"
    assert (skills_root / "custom" / "uploaded-skill" / "SKILL.md").exists()


def test_upload_skill_rejects_non_skill_extension():
    app = _build_app()

    with TestClient(app) as client:
        response = client.post(
            "/api/skills/upload",
            files={"file": ("bad.zip", b"not a skill", "application/zip")},
        )

    assert response.status_code == 400
    assert ".skill" in response.json()["detail"]


def test_upload_skill_rejects_bad_zip(tmp_path, monkeypatch):
    skills_root = tmp_path / "skills"

    def install_with_test_root(path):
        return install_skill_from_archive(path, skills_root=skills_root)

    monkeypatch.setattr(skills_router, "install_skill_from_archive", install_with_test_root)
    app = _build_app()

    with TestClient(app) as client:
        response = client.post(
            "/api/skills/upload",
            files={"file": ("bad.skill", b"not a zip", "application/zip")},
        )

    assert response.status_code == 400
    assert "valid ZIP" in response.json()["detail"]


def test_upload_skill_returns_conflict_for_duplicate(tmp_path, monkeypatch):
    skills_root = tmp_path / "skills"
    (skills_root / "custom" / "uploaded-skill").mkdir(parents=True)
    archive = _make_skill_archive(tmp_path)

    def install_with_test_root(path):
        return install_skill_from_archive(path, skills_root=skills_root)

    monkeypatch.setattr(skills_router, "install_skill_from_archive", install_with_test_root)
    app = _build_app()

    with TestClient(app) as client:
        response = client.post(
            "/api/skills/upload",
            files={"file": ("uploaded-skill.skill", archive.read_bytes(), "application/zip")},
        )

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_get_skill_detail_returns_content_and_files(tmp_path, monkeypatch):
    skills_root = tmp_path / "skills"
    _write_skill(skills_root, "custom", "custom-skill", extra_file=True)
    monkeypatch.setattr(skills_router, "load_skills", lambda enabled_only=False: load_skills(skills_path=skills_root, use_config=False, enabled_only=enabled_only))

    app = _build_app()

    with TestClient(app) as client:
        response = client.get("/api/skills/custom-skill/detail")

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "custom-skill"
    assert payload["category"] == "custom"
    assert "# custom-skill" in payload["content"]
    assert payload["relative_path"] == "custom-skill"
    assert payload["skill_file"] == "SKILL.md"
    assert payload["files"] == ["SKILL.md", "references/guide.md"]


def test_get_skill_detail_returns_404_for_missing_skill(tmp_path, monkeypatch):
    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    monkeypatch.setattr(skills_router, "load_skills", lambda enabled_only=False: load_skills(skills_path=skills_root, use_config=False, enabled_only=enabled_only))

    app = _build_app()

    with TestClient(app) as client:
        response = client.get("/api/skills/missing-skill/detail")

    assert response.status_code == 404


def test_delete_custom_skill_removes_directory_and_config(tmp_path, monkeypatch):
    skills_root = tmp_path / "skills"
    skill_dir = _write_skill(skills_root, "custom", "custom-skill")
    config_path = tmp_path / "extensions_config.json"
    config = ExtensionsConfig(skills={"custom-skill": SkillStateConfig(enabled=False)})
    reload_calls = []

    monkeypatch.setattr(skills_router, "load_skills", lambda enabled_only=False: load_skills(skills_path=skills_root, use_config=False, enabled_only=enabled_only))
    monkeypatch.setattr(skills_router.ExtensionsConfig, "resolve_config_path", staticmethod(lambda config_path_arg=None: config_path))
    monkeypatch.setattr(skills_router, "get_extensions_config", lambda: config)
    monkeypatch.setattr(skills_router, "reload_extensions_config", lambda: reload_calls.append(True))

    app = _build_app()

    with TestClient(app) as client:
        response = client.delete("/api/skills/custom-skill")

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert not skill_dir.exists()
    assert json.loads(config_path.read_text(encoding="utf-8"))["skills"] == {}
    assert reload_calls == [True]


def test_delete_public_skill_is_rejected(tmp_path, monkeypatch):
    skills_root = tmp_path / "skills"
    skill_dir = _write_skill(skills_root, "public", "public-skill")
    monkeypatch.setattr(skills_router, "load_skills", lambda enabled_only=False: load_skills(skills_path=skills_root, use_config=False, enabled_only=enabled_only))

    app = _build_app()

    with TestClient(app) as client:
        response = client.delete("/api/skills/public-skill")

    assert response.status_code == 400
    assert skill_dir.exists()
    assert "Public skills" in response.json()["detail"]


def test_delete_missing_skill_returns_404(tmp_path, monkeypatch):
    skills_root = tmp_path / "skills"
    skills_root.mkdir()
    monkeypatch.setattr(skills_router, "load_skills", lambda enabled_only=False: load_skills(skills_path=skills_root, use_config=False, enabled_only=enabled_only))

    app = _build_app()

    with TestClient(app) as client:
        response = client.delete("/api/skills/missing-skill")

    assert response.status_code == 404


def test_delete_prefers_custom_when_public_has_same_name(tmp_path, monkeypatch):
    skills_root = tmp_path / "skills"
    public_dir = _write_skill(skills_root, "public", "shared-skill")
    custom_dir = _write_skill(skills_root, "custom", "shared-skill")

    monkeypatch.setattr(skills_router, "load_skills", lambda enabled_only=False: load_skills(skills_path=skills_root, use_config=False, enabled_only=enabled_only))
    monkeypatch.setattr(skills_router, "get_extensions_config", lambda: ExtensionsConfig())

    app = _build_app()

    with TestClient(app) as client:
        response = client.delete("/api/skills/shared-skill")

    assert response.status_code == 200
    assert public_dir.exists()
    assert not custom_dir.exists()


def test_read_skill_file_returns_content_for_custom_and_public(tmp_path, monkeypatch):
    skills_root = tmp_path / "skills"
    _write_skill(skills_root, "public", "public-skill", extra_file=True)
    _write_skill(skills_root, "custom", "custom-skill", extra_file=True)
    monkeypatch.setattr(
        skills_router,
        "load_skills",
        lambda enabled_only=False: load_skills(skills_path=skills_root, use_config=False, enabled_only=enabled_only),
    )

    app = _build_app()

    with TestClient(app) as client:
        custom_response = client.get("/api/skills/custom-skill/files/references/guide.md")
        public_response = client.get("/api/skills/public-skill/files/SKILL.md")

    assert custom_response.status_code == 200
    assert custom_response.json()["content"] == "guide"
    assert custom_response.json()["files"] == ["SKILL.md", "references/guide.md"]
    assert public_response.status_code == 200
    assert "# public-skill" in public_response.json()["content"]


def test_skill_file_path_traversal_is_rejected(tmp_path, monkeypatch):
    skills_root = tmp_path / "skills"
    _write_skill(skills_root, "custom", "custom-skill")
    monkeypatch.setattr(
        skills_router,
        "load_skills",
        lambda enabled_only=False: load_skills(skills_path=skills_root, use_config=False, enabled_only=enabled_only),
    )

    app = _build_app()

    with TestClient(app) as client:
        response = client.get("/api/skills/custom-skill/files/%2E%2E/secret.txt")

    assert response.status_code == 400


def test_public_skill_file_mutations_are_rejected(tmp_path, monkeypatch):
    skills_root = tmp_path / "skills"
    _write_skill(skills_root, "public", "public-skill", extra_file=True)
    monkeypatch.setattr(
        skills_router,
        "load_skills",
        lambda enabled_only=False: load_skills(skills_path=skills_root, use_config=False, enabled_only=enabled_only),
    )

    app = _build_app()

    with TestClient(app) as client:
        save_response = client.put("/api/skills/public-skill/files/references/guide.md", json={"content": "new"})
        create_response = client.post("/api/skills/public-skill/files", json={"path": "new.md", "content": ""})
        rename_response = client.patch("/api/skills/public-skill/files/references/guide.md", json={"new_path": "renamed.md"})
        delete_response = client.delete("/api/skills/public-skill/files/references/guide.md")

    assert save_response.status_code == 400
    assert create_response.status_code == 400
    assert rename_response.status_code == 400
    assert delete_response.status_code == 400


def test_save_custom_skill_file_updates_content(tmp_path, monkeypatch):
    skills_root = tmp_path / "skills"
    skill_dir = _write_skill(skills_root, "custom", "custom-skill", extra_file=True)
    monkeypatch.setattr(
        skills_router,
        "load_skills",
        lambda enabled_only=False: load_skills(skills_path=skills_root, use_config=False, enabled_only=enabled_only),
    )

    app = _build_app()

    with TestClient(app) as client:
        response = client.put("/api/skills/custom-skill/files/references/guide.md", json={"content": "updated"})

    assert response.status_code == 200
    assert (skill_dir / "references" / "guide.md").read_text(encoding="utf-8") == "updated"


def test_save_skill_md_rejects_invalid_or_renamed_frontmatter(tmp_path, monkeypatch):
    skills_root = tmp_path / "skills"
    skill_dir = _write_skill(skills_root, "custom", "custom-skill")
    original = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    monkeypatch.setattr(
        skills_router,
        "load_skills",
        lambda enabled_only=False: load_skills(skills_path=skills_root, use_config=False, enabled_only=enabled_only),
    )

    app = _build_app()

    with TestClient(app) as client:
        invalid_response = client.put("/api/skills/custom-skill/files/SKILL.md", json={"content": "no frontmatter"})
        renamed_response = client.put(
            "/api/skills/custom-skill/files/SKILL.md",
            json={"content": "---\nname: other-skill\ndescription: custom skill\n---\n\n# other\n"},
        )

    assert invalid_response.status_code == 400
    assert renamed_response.status_code == 400
    assert (skill_dir / "SKILL.md").read_text(encoding="utf-8") == original


def test_save_skill_md_accepts_valid_content_with_same_name(tmp_path, monkeypatch):
    skills_root = tmp_path / "skills"
    skill_dir = _write_skill(skills_root, "custom", "custom-skill")
    monkeypatch.setattr(
        skills_router,
        "load_skills",
        lambda enabled_only=False: load_skills(skills_path=skills_root, use_config=False, enabled_only=enabled_only),
    )

    app = _build_app()
    updated = "---\nname: custom-skill\ndescription: updated skill\n---\n\n# Updated\n"

    with TestClient(app) as client:
        response = client.put("/api/skills/custom-skill/files/SKILL.md", json={"content": updated})

    assert response.status_code == 200
    assert (skill_dir / "SKILL.md").read_text(encoding="utf-8") == updated


def test_create_custom_skill_file_and_reject_existing(tmp_path, monkeypatch):
    skills_root = tmp_path / "skills"
    skill_dir = _write_skill(skills_root, "custom", "custom-skill")
    monkeypatch.setattr(
        skills_router,
        "load_skills",
        lambda enabled_only=False: load_skills(skills_path=skills_root, use_config=False, enabled_only=enabled_only),
    )

    app = _build_app()

    with TestClient(app) as client:
        create_response = client.post("/api/skills/custom-skill/files", json={"path": "notes/new.md", "content": "hello"})
        duplicate_response = client.post("/api/skills/custom-skill/files", json={"path": "notes/new.md", "content": "hello"})

    assert create_response.status_code == 200
    assert (skill_dir / "notes" / "new.md").read_text(encoding="utf-8") == "hello"
    assert duplicate_response.status_code == 409


def test_rename_custom_skill_file_and_reject_skill_md_or_existing_target(tmp_path, monkeypatch):
    skills_root = tmp_path / "skills"
    skill_dir = _write_skill(skills_root, "custom", "custom-skill", extra_file=True)
    (skill_dir / "existing.md").write_text("existing", encoding="utf-8")
    monkeypatch.setattr(
        skills_router,
        "load_skills",
        lambda enabled_only=False: load_skills(skills_path=skills_root, use_config=False, enabled_only=enabled_only),
    )

    app = _build_app()

    with TestClient(app) as client:
        rename_response = client.patch(
            "/api/skills/custom-skill/files/references/guide.md",
            json={"new_path": "references/renamed.md"},
        )
        skill_md_response = client.patch("/api/skills/custom-skill/files/SKILL.md", json={"new_path": "renamed.md"})
        existing_response = client.patch(
            "/api/skills/custom-skill/files/references/renamed.md",
            json={"new_path": "existing.md"},
        )

    assert rename_response.status_code == 200
    assert not (skill_dir / "references" / "guide.md").exists()
    assert (skill_dir / "references" / "renamed.md").exists()
    assert skill_md_response.status_code == 400
    assert existing_response.status_code == 409


def test_delete_custom_skill_file_and_reject_skill_md(tmp_path, monkeypatch):
    skills_root = tmp_path / "skills"
    skill_dir = _write_skill(skills_root, "custom", "custom-skill", extra_file=True)
    monkeypatch.setattr(
        skills_router,
        "load_skills",
        lambda enabled_only=False: load_skills(skills_path=skills_root, use_config=False, enabled_only=enabled_only),
    )

    app = _build_app()

    with TestClient(app) as client:
        delete_response = client.delete("/api/skills/custom-skill/files/references/guide.md")
        skill_md_response = client.delete("/api/skills/custom-skill/files/SKILL.md")

    assert delete_response.status_code == 200
    assert not (skill_dir / "references" / "guide.md").exists()
    assert skill_md_response.status_code == 400
    assert (skill_dir / "SKILL.md").exists()
