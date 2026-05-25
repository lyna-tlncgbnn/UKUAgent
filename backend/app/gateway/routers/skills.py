import json
import logging
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.gateway.path_utils import resolve_thread_virtual_path
from deerflow.config.extensions_config import ExtensionsConfig, SkillStateConfig, get_extensions_config, reload_extensions_config
from deerflow.skills import Skill, load_skills
from deerflow.skills.installer import SkillAlreadyExistsError, install_skill_from_archive
from deerflow.skills.validation import _validate_skill_frontmatter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["skills"])


class SkillResponse(BaseModel):
    """Response model for skill information."""

    name: str = Field(..., description="Name of the skill")
    description: str = Field(..., description="Description of what the skill does")
    license: str | None = Field(None, description="License information")
    category: str = Field(..., description="Category of the skill (public or custom)")
    enabled: bool = Field(default=True, description="Whether this skill is enabled")


class SkillsListResponse(BaseModel):
    """Response model for listing all skills."""

    skills: list[SkillResponse]


class SkillUpdateRequest(BaseModel):
    """Request model for updating a skill."""

    enabled: bool = Field(..., description="Whether to enable or disable the skill")


class SkillInstallRequest(BaseModel):
    """Request model for installing a skill from a .skill file."""

    thread_id: str = Field(..., description="The thread ID where the .skill file is located")
    path: str = Field(..., description="Virtual path to the .skill file (e.g., mnt/user-data/outputs/my-skill.skill)")


class SkillInstallResponse(BaseModel):
    """Response model for skill installation."""

    success: bool = Field(..., description="Whether the installation was successful")
    skill_name: str = Field(..., description="Name of the installed skill")
    message: str = Field(..., description="Installation result message")


class SkillDetailResponse(SkillResponse):
    """Response model for skill detail."""

    relative_path: str = Field(..., description="Relative path from the skill category root")
    skill_file: str = Field(..., description="Path to the skill's SKILL.md file")
    content: str = Field(..., description="Contents of SKILL.md")
    files: list[str] = Field(default_factory=list, description="Files contained in the skill directory")


class SkillDeleteResponse(BaseModel):
    """Response model for deleting a custom skill."""

    success: bool = Field(..., description="Whether the deletion was successful")
    skill_name: str = Field(..., description="Name of the deleted skill")
    message: str = Field(..., description="Deletion result message")


class SkillFileResponse(BaseModel):
    """Response model for reading a skill file."""

    path: str = Field(..., description="Relative path inside the skill directory")
    content: str = Field(..., description="UTF-8 text content")
    files: list[str] = Field(default_factory=list, description="Current skill file list")


class SkillFileSaveRequest(BaseModel):
    """Request model for saving a skill file."""

    content: str = Field(..., description="UTF-8 text content to write")


class SkillFileCreateRequest(BaseModel):
    """Request model for creating a skill file."""

    path: str = Field(..., description="Relative path inside the skill directory")
    content: str = Field(default="", description="Initial UTF-8 text content")


class SkillFileRenameRequest(BaseModel):
    """Request model for renaming a skill file."""

    new_path: str = Field(..., description="New relative path inside the skill directory")


class SkillFileMutationResponse(BaseModel):
    """Response model for skill file mutations."""

    success: bool = Field(..., description="Whether the mutation was successful")
    path: str | None = Field(None, description="Current relative path after the mutation")
    files: list[str] = Field(default_factory=list, description="Current skill file list")
    message: str = Field(..., description="Mutation result message")


def _skill_to_response(skill: Skill) -> SkillResponse:
    """Convert a Skill object to a SkillResponse."""
    return SkillResponse(
        name=skill.name,
        description=skill.description,
        license=skill.license,
        category=skill.category,
        enabled=skill.enabled,
    )


def _find_skill(skill_name: str, *, custom_first: bool = False) -> Skill | None:
    skills = load_skills(enabled_only=False)
    if custom_first:
        skill = next((s for s in skills if s.name == skill_name and s.category == "custom"), None)
        if skill is not None:
            return skill
    return next((s for s in skills if s.name == skill_name), None)


def _skill_files(skill: Skill) -> list[str]:
    skill_root = skill.skill_dir.resolve()
    files: list[str] = []
    for path in (p for p in skill_root.rglob("*") if p.is_file()):
        resolved = path.resolve()
        if not resolved.is_relative_to(skill_root):
            continue
        files.append(resolved.relative_to(skill_root).as_posix())
    return sorted(files)


def _validate_skill_file_path(file_path: str) -> str:
    normalized = file_path.replace("\\", "/").strip()
    path = Path(normalized)
    if not normalized or normalized in {".", "/"}:
        raise HTTPException(status_code=400, detail="File path cannot be empty")
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise HTTPException(status_code=400, detail="Invalid skill file path")
    return path.as_posix()


def _resolve_skill_file(skill: Skill, file_path: str) -> tuple[str, Path]:
    relative_path = _validate_skill_file_path(file_path)
    skill_root = skill.skill_dir.resolve()
    resolved = (skill_root / relative_path).resolve()
    if not resolved.is_relative_to(skill_root):
        raise HTTPException(status_code=400, detail="Invalid skill file path")
    return relative_path, resolved


def _ensure_custom_skill(skill: Skill) -> None:
    if skill.category != "custom":
        raise HTTPException(status_code=400, detail="Public skills are read-only")


def _validate_skill_md_update(skill: Skill, original_content: str) -> None:
    is_valid, message, skill_name = _validate_skill_frontmatter(skill.skill_dir)
    if not is_valid:
        skill.skill_file.write_text(original_content, encoding="utf-8")
        raise HTTPException(status_code=400, detail=message)
    if skill_name != skill.name:
        skill.skill_file.write_text(original_content, encoding="utf-8")
        raise HTTPException(status_code=400, detail="SKILL.md name cannot be changed")


def _skill_to_detail_response(skill: Skill) -> SkillDetailResponse:
    skill_root = skill.skill_dir.resolve()
    skill_file = skill.skill_file.resolve()
    if not skill_file.is_relative_to(skill_root):
        raise ValueError("Skill file is outside the skill directory")

    return SkillDetailResponse(
        name=skill.name,
        description=skill.description,
        license=skill.license,
        category=skill.category,
        enabled=skill.enabled,
        relative_path=skill.skill_path,
        skill_file=skill.skill_file.name,
        content=skill.skill_file.read_text(encoding="utf-8"),
        files=_skill_files(skill),
    )


def _resolve_extensions_config_write_path() -> Path:
    config_path = ExtensionsConfig.resolve_config_path()
    if config_path is None:
        config_path = Path.cwd().parent / "extensions_config.json"
        logger.info(f"No existing extensions config found. Creating new config at: {config_path}")
    return config_path


def _write_extensions_config(extensions_config: ExtensionsConfig, config_path: Path) -> None:
    config_data = {
        "mcpServers": {name: server.model_dump() for name, server in extensions_config.mcp_servers.items()},
        "skills": {name: {"enabled": skill_config.enabled} for name, skill_config in extensions_config.skills.items()},
    }

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2)


@router.get(
    "/skills",
    response_model=SkillsListResponse,
    summary="List All Skills",
    description="Retrieve a list of all available skills from both public and custom directories.",
)
async def list_skills() -> SkillsListResponse:
    try:
        skills = load_skills(enabled_only=False)
        return SkillsListResponse(skills=[_skill_to_response(skill) for skill in skills])
    except Exception as e:
        logger.error(f"Failed to load skills: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to load skills: {str(e)}")


@router.get(
    "/skills/{skill_name}",
    response_model=SkillResponse,
    summary="Get Skill Details",
    description="Retrieve detailed information about a specific skill by its name.",
)
async def get_skill(skill_name: str) -> SkillResponse:
    try:
        skills = load_skills(enabled_only=False)
        skill = next((s for s in skills if s.name == skill_name), None)

        if skill is None:
            raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")

        return _skill_to_response(skill)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get skill {skill_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get skill: {str(e)}")


@router.get(
    "/skills/{skill_name}/detail",
    response_model=SkillDetailResponse,
    summary="Get Skill Detail",
    description="Retrieve metadata, SKILL.md content, and file list for a specific skill.",
)
async def get_skill_detail(skill_name: str) -> SkillDetailResponse:
    try:
        skill = _find_skill(skill_name, custom_first=True)

        if skill is None:
            raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")

        return _skill_to_detail_response(skill)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get skill detail {skill_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get skill detail: {str(e)}")


@router.get(
    "/skills/{skill_name}/files/{file_path:path}",
    response_model=SkillFileResponse,
    summary="Read Skill File",
    description="Read a UTF-8 text file inside a skill directory.",
)
async def read_skill_file(skill_name: str, file_path: str) -> SkillFileResponse:
    try:
        skill = _find_skill(skill_name, custom_first=True)
        if skill is None:
            raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")

        relative_path, resolved = _resolve_skill_file(skill, file_path)
        if not resolved.exists() or not resolved.is_file():
            raise HTTPException(status_code=404, detail=f"File '{relative_path}' not found")

        try:
            content = resolved.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raise HTTPException(status_code=415, detail="Only UTF-8 text files can be previewed")

        return SkillFileResponse(path=relative_path, content=content, files=_skill_files(skill))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to read skill file {skill_name}/{file_path}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to read skill file: {str(e)}")


@router.put(
    "/skills/{skill_name}/files/{file_path:path}",
    response_model=SkillFileMutationResponse,
    summary="Save Skill File",
    description="Save a UTF-8 text file inside a custom skill directory.",
)
async def save_skill_file(skill_name: str, file_path: str, request: SkillFileSaveRequest) -> SkillFileMutationResponse:
    try:
        skill = _find_skill(skill_name, custom_first=True)
        if skill is None:
            raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")
        _ensure_custom_skill(skill)

        relative_path, resolved = _resolve_skill_file(skill, file_path)
        if not resolved.exists() or not resolved.is_file():
            raise HTTPException(status_code=404, detail=f"File '{relative_path}' not found")

        original_content = resolved.read_text(encoding="utf-8")
        resolved.write_text(request.content, encoding="utf-8")
        if relative_path == "SKILL.md":
            _validate_skill_md_update(skill, original_content)

        return SkillFileMutationResponse(
            success=True,
            path=relative_path,
            files=_skill_files(skill),
            message=f"File '{relative_path}' saved successfully",
        )
    except UnicodeDecodeError:
        raise HTTPException(status_code=415, detail="Only UTF-8 text files can be edited")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to save skill file {skill_name}/{file_path}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to save skill file: {str(e)}")


@router.post(
    "/skills/{skill_name}/files",
    response_model=SkillFileMutationResponse,
    summary="Create Skill File",
    description="Create a UTF-8 text file inside a custom skill directory.",
)
async def create_skill_file(skill_name: str, request: SkillFileCreateRequest) -> SkillFileMutationResponse:
    try:
        skill = _find_skill(skill_name, custom_first=True)
        if skill is None:
            raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")
        _ensure_custom_skill(skill)

        relative_path, resolved = _resolve_skill_file(skill, request.path)
        if resolved.exists():
            raise HTTPException(status_code=409, detail=f"File '{relative_path}' already exists")

        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(request.content, encoding="utf-8")

        return SkillFileMutationResponse(
            success=True,
            path=relative_path,
            files=_skill_files(skill),
            message=f"File '{relative_path}' created successfully",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create skill file {skill_name}/{request.path}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create skill file: {str(e)}")


@router.patch(
    "/skills/{skill_name}/files/{file_path:path}",
    response_model=SkillFileMutationResponse,
    summary="Rename Skill File",
    description="Rename a file inside a custom skill directory.",
)
async def rename_skill_file(skill_name: str, file_path: str, request: SkillFileRenameRequest) -> SkillFileMutationResponse:
    try:
        skill = _find_skill(skill_name, custom_first=True)
        if skill is None:
            raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")
        _ensure_custom_skill(skill)

        relative_path, source = _resolve_skill_file(skill, file_path)
        new_relative_path, target = _resolve_skill_file(skill, request.new_path)
        if relative_path == "SKILL.md" or new_relative_path == "SKILL.md":
            raise HTTPException(status_code=400, detail="SKILL.md cannot be renamed")
        if not source.exists() or not source.is_file():
            raise HTTPException(status_code=404, detail=f"File '{relative_path}' not found")
        if target.exists():
            raise HTTPException(status_code=409, detail=f"File '{new_relative_path}' already exists")

        target.parent.mkdir(parents=True, exist_ok=True)
        source.rename(target)

        return SkillFileMutationResponse(
            success=True,
            path=new_relative_path,
            files=_skill_files(skill),
            message=f"File '{relative_path}' renamed successfully",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to rename skill file {skill_name}/{file_path}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to rename skill file: {str(e)}")


@router.delete(
    "/skills/{skill_name}/files/{file_path:path}",
    response_model=SkillFileMutationResponse,
    summary="Delete Skill File",
    description="Delete a file inside a custom skill directory.",
)
async def delete_skill_file(skill_name: str, file_path: str) -> SkillFileMutationResponse:
    try:
        skill = _find_skill(skill_name, custom_first=True)
        if skill is None:
            raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")
        _ensure_custom_skill(skill)

        relative_path, resolved = _resolve_skill_file(skill, file_path)
        if relative_path == "SKILL.md":
            raise HTTPException(status_code=400, detail="SKILL.md cannot be deleted")
        if not resolved.exists() or not resolved.is_file():
            raise HTTPException(status_code=404, detail=f"File '{relative_path}' not found")

        resolved.unlink()

        return SkillFileMutationResponse(
            success=True,
            path=None,
            files=_skill_files(skill),
            message=f"File '{relative_path}' deleted successfully",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete skill file {skill_name}/{file_path}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete skill file: {str(e)}")


@router.put(
    "/skills/{skill_name}",
    response_model=SkillResponse,
    summary="Update Skill",
    description="Update a skill's enabled status by modifying the extensions_config.json file.",
)
async def update_skill(skill_name: str, request: SkillUpdateRequest) -> SkillResponse:
    try:
        skills = load_skills(enabled_only=False)
        skill = next((s for s in skills if s.name == skill_name), None)

        if skill is None:
            raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")

        config_path = _resolve_extensions_config_write_path()
        extensions_config = get_extensions_config()
        extensions_config.skills[skill_name] = SkillStateConfig(enabled=request.enabled)
        _write_extensions_config(extensions_config, config_path)

        logger.info(f"Skills configuration updated and saved to: {config_path}")
        reload_extensions_config()

        skills = load_skills(enabled_only=False)
        updated_skill = next((s for s in skills if s.name == skill_name), None)

        if updated_skill is None:
            raise HTTPException(status_code=500, detail=f"Failed to reload skill '{skill_name}' after update")

        logger.info(f"Skill '{skill_name}' enabled status updated to {request.enabled}")
        return _skill_to_response(updated_skill)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update skill {skill_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to update skill: {str(e)}")


@router.delete(
    "/skills/{skill_name}",
    response_model=SkillDeleteResponse,
    summary="Delete Custom Skill",
    description="Delete a custom skill directory. Public skills cannot be deleted.",
)
async def delete_skill(skill_name: str) -> SkillDeleteResponse:
    try:
        skills = load_skills(enabled_only=False)
        skill = next((s for s in skills if s.name == skill_name and s.category == "custom"), None)

        if skill is None:
            public_skill = next((s for s in skills if s.name == skill_name and s.category == "public"), None)
            if public_skill is not None:
                raise HTTPException(status_code=400, detail="Public skills cannot be deleted")
            raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' not found")

        skill_dir = skill.skill_dir.resolve()
        skills_root = skill_dir.parent.resolve()
        if skill.category != "custom" or not skill_dir.is_relative_to(skills_root):
            raise HTTPException(status_code=400, detail="Only custom skills can be deleted")

        shutil.rmtree(skill_dir)

        extensions_config = get_extensions_config()
        if skill_name in extensions_config.skills:
            config_path = _resolve_extensions_config_write_path()
            extensions_config.skills.pop(skill_name, None)
            _write_extensions_config(extensions_config, config_path)
            reload_extensions_config()

        return SkillDeleteResponse(
            success=True,
            skill_name=skill_name,
            message=f"Skill '{skill_name}' deleted successfully",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete skill {skill_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete skill: {str(e)}")


@router.post(
    "/skills/install",
    response_model=SkillInstallResponse,
    summary="Install Skill",
    description="Install a skill from a .skill file (ZIP archive) located in the thread's user-data directory.",
)
async def install_skill(request: SkillInstallRequest) -> SkillInstallResponse:
    try:
        skill_file_path = resolve_thread_virtual_path(request.thread_id, request.path)
        result = install_skill_from_archive(skill_file_path)
        return SkillInstallResponse(**result)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except SkillAlreadyExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to install skill: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to install skill: {str(e)}")


@router.post(
    "/skills/upload",
    response_model=SkillInstallResponse,
    summary="Upload and Install Skill",
    description="Upload a .skill ZIP archive and install it into the custom skills directory.",
)
async def upload_skill(file: UploadFile = File(...)) -> SkillInstallResponse:
    filename = Path(file.filename or "").name
    if not filename or Path(filename).suffix != ".skill":
        raise HTTPException(status_code=400, detail="File must have .skill extension")

    try:
        with tempfile.TemporaryDirectory() as tmp:
            temp_path = Path(tmp) / filename
            with temp_path.open("wb") as f:
                while chunk := await file.read(1024 * 1024):
                    f.write(chunk)

            result = install_skill_from_archive(temp_path)
            return SkillInstallResponse(**result)
    except SkillAlreadyExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload skill: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to upload skill: {str(e)}")
    finally:
        await file.close()
