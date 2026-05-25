"use client";

import {
  BoxIcon,
  FileTextIcon,
  PackagePlusIcon,
  PencilIcon,
  PlusIcon,
  SaveIcon,
  ShieldCheckIcon,
  SparklesIcon,
  Trash2Icon,
  XIcon,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { Streamdown } from "streamdown";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Input } from "@/components/ui/input";
import {
  Item,
  ItemActions,
  ItemContent,
  ItemDescription,
  ItemMedia,
  ItemTitle,
} from "@/components/ui/item";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CodeEditor } from "@/components/workspace/code-editor";
import {
  WorkspaceBody,
  WorkspaceContainer,
  WorkspaceHeader,
} from "@/components/workspace/workspace-container";
import { useI18n } from "@/core/i18n/hooks";
import {
  useEnableSkill,
  useDeleteSkill,
  useCreateSkillFile,
  useDeleteSkillFile,
  useRenameSkillFile,
  useSaveSkillFile,
  useSkillDetail,
  useSkillFile,
  useSkills,
  useUploadSkill,
} from "@/core/skills/hooks";
import type { Skill } from "@/core/skills/type";
import { streamdownPlugins } from "@/core/streamdown";
import { env } from "@/env";

type SkillCategory = "public" | "custom";

const SKILL_CATEGORIES: { value: SkillCategory; icon: React.ElementType }[] = [
  { value: "public", icon: SparklesIcon },
  { value: "custom", icon: ShieldCheckIcon },
];

function stripFrontmatter(content: string) {
  return content.replace(/^---\s*\n[\s\S]*?\n---\s*\n?/, "").trimStart();
}

function isMarkdownFile(path: string) {
  return path.toLowerCase().endsWith(".md");
}

function previewContent(path: string, content: string) {
  return path === "SKILL.md" ? stripFrontmatter(content) : content;
}

function SkillUploadDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { t } = useI18n();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const upload = useUploadSkill();

  const handleSubmit = async () => {
    if (!file) return;

    try {
      const result = await upload.mutateAsync(file);
      toast.success(result.message);
      setFile(null);
      if (inputRef.current) inputRef.current.value = "";
      onOpenChange(false);
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : t.skills.uploadFailed,
      );
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t.skills.installTitle}</DialogTitle>
          <DialogDescription>{t.skills.installDescription}</DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-4">
          <div className="bg-muted/40 text-muted-foreground rounded-md border p-3 text-sm">
            <div className="text-foreground mb-2 font-medium">
              {t.skills.uploadRequirementsTitle}
            </div>
            <ul className="list-disc space-y-1 pl-5">
              <li>{t.skills.uploadRequirementExtension}</li>
              <li>{t.skills.uploadRequirementStructure}</li>
              <li>{t.skills.uploadRequirementFrontmatter}</li>
              <li>{t.skills.uploadRequirementName}</li>
              <li>{t.skills.uploadRequirementOptionalFiles}</li>
            </ul>
            <pre className="bg-background text-foreground mt-3 overflow-x-auto rounded border p-3 font-mono text-xs">
              {`my-skill/
├─ SKILL.md
├─ scripts/
├─ references/
└─ templates/`}
            </pre>
            <pre className="bg-background text-foreground mt-2 overflow-x-auto rounded border p-3 font-mono text-xs">
              {`---
name: my-skill
description: 这个 skill 用来处理某类任务
---`}
            </pre>
          </div>
          <input
            ref={inputRef}
            type="file"
            accept=".skill"
            className="border-input file:bg-muted file:text-foreground hover:file:bg-muted/80 h-10 rounded-md border text-sm file:mr-4 file:h-full file:border-0 file:px-4 file:text-sm file:font-medium"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={upload.isPending}
            >
              {t.common.cancel}
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={!file || upload.isPending}
            >
              <PackagePlusIcon className="size-4" />
              {upload.isPending ? t.skills.installing : t.skills.installSkill}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function EmptySkills({
  category,
  onInstall,
}: {
  category: SkillCategory;
  onInstall: () => void;
}) {
  const { t } = useI18n();
  const isCustom = category === "custom";

  return (
    <Empty>
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <BoxIcon />
        </EmptyMedia>
        <EmptyTitle>
          {isCustom ? t.skills.emptyCustomTitle : t.skills.emptyPublicTitle}
        </EmptyTitle>
        <EmptyDescription>
          {isCustom
            ? t.skills.emptyCustomDescription
            : t.skills.emptyPublicDescription}
        </EmptyDescription>
      </EmptyHeader>
      {isCustom && (
        <EmptyContent>
          <Button
            onClick={onInstall}
            disabled={env.NEXT_PUBLIC_STATIC_WEBSITE_ONLY === "true"}
          >
            <PackagePlusIcon className="size-4" />
            {t.skills.installSkill}
          </Button>
        </EmptyContent>
      )}
    </Empty>
  );
}

function SkillList({
  skills,
  onSelect,
}: {
  skills: Skill[];
  onSelect: (skill: Skill) => void;
}) {
  const { t } = useI18n();
  const { mutate: enableSkill, isPending } = useEnableSkill();

  return (
    <div className="flex flex-col gap-2">
      {skills.map((skill) => (
        <Item
          key={`${skill.category}-${skill.name}`}
          variant="outline"
          className="cursor-pointer"
          onClick={() => onSelect(skill)}
        >
          <ItemMedia>
            <SparklesIcon className="text-muted-foreground size-5" />
          </ItemMedia>
          <ItemContent>
            <ItemTitle>
              {skill.name}
              <Badge variant="secondary">
                {skill.category === "public"
                  ? t.common.public
                  : t.common.custom}
              </Badge>
              {skill.license && (
                <Badge variant="outline">{skill.license}</Badge>
              )}
            </ItemTitle>
            <ItemDescription className="line-clamp-3">
              {skill.description}
            </ItemDescription>
          </ItemContent>
          <ItemActions>
            <Switch
              checked={skill.enabled}
              disabled={
                isPending || env.NEXT_PUBLIC_STATIC_WEBSITE_ONLY === "true"
              }
              onClick={(event) => event.stopPropagation()}
              onCheckedChange={(checked) =>
                enableSkill({ skillName: skill.name, enabled: checked })
              }
            />
          </ItemActions>
        </Item>
      ))}
    </div>
  );
}

function SkillDetailDialog({
  selectedSkill,
  onOpenChange,
  onRequestDelete,
}: {
  selectedSkill: Skill | null;
  onOpenChange: (open: boolean) => void;
  onRequestDelete: (skill: Skill) => void;
}) {
  const { t } = useI18n();
  const { skill, isLoading, error } = useSkillDetail(selectedSkill?.name ?? null);
  const [selectedFilePath, setSelectedFilePath] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"preview" | "edit">("preview");
  const [draftContent, setDraftContent] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [renameOpen, setRenameOpen] = useState(false);
  const [deleteFileOpen, setDeleteFileOpen] = useState(false);
  const [filePathInput, setFilePathInput] = useState("");
  const { file, isLoading: isFileLoading, error: fileError } = useSkillFile(
    selectedSkill?.name ?? null,
    selectedFilePath,
  );
  const saveFile = useSaveSkillFile();
  const createFile = useCreateSkillFile();
  const renameFile = useRenameSkillFile();
  const deleteFile = useDeleteSkillFile();
  const displaySkill = skill ?? selectedSkill;
  const isCustom =
    displaySkill?.category === "custom" &&
    env.NEXT_PUBLIC_STATIC_WEBSITE_ONLY !== "true";
  const canDelete =
    displaySkill?.category === "custom" &&
    env.NEXT_PUBLIC_STATIC_WEBSITE_ONLY !== "true";
  const canEditFile = !!isCustom && !!selectedFilePath;
  const canRenameOrDeleteFile = canEditFile && selectedFilePath !== "SKILL.md";
  const isDirty = file ? draftContent !== file.content : false;

  useEffect(() => {
    setSelectedFilePath(null);
    setViewMode("preview");
    setDraftContent("");
    setFilePathInput("");
  }, [selectedSkill?.name]);

  useEffect(() => {
    if (!skill) return;
    if (!selectedFilePath || !skill.files.includes(selectedFilePath)) {
      setSelectedFilePath(
        skill.files.includes("SKILL.md") ? "SKILL.md" : (skill.files[0] ?? null),
      );
    }
  }, [skill, selectedFilePath]);

  useEffect(() => {
    if (file) {
      setDraftContent(file.content);
    }
  }, [file]);

  const handleSelectFile = (path: string) => {
    if (path === selectedFilePath) return;
    setSelectedFilePath(path);
    setViewMode("preview");
  };

  const handleSaveFile = async () => {
    if (!selectedSkill?.name || !selectedFilePath) return;
    try {
      const result = await saveFile.mutateAsync({
        skillName: selectedSkill.name,
        filePath: selectedFilePath,
        content: draftContent,
      });
      toast.success(result.message || t.skills.fileSaveSuccess);
      setViewMode("preview");
    } catch (saveError) {
      toast.error(
        saveError instanceof Error
          ? saveError.message
          : t.skills.fileSaveFailed,
      );
    }
  };

  const handleCreateFile = async () => {
    if (!selectedSkill?.name || !filePathInput.trim()) return;
    try {
      const result = await createFile.mutateAsync({
        skillName: selectedSkill.name,
        path: filePathInput.trim(),
      });
      toast.success(result.message || t.skills.fileCreateSuccess);
      setSelectedFilePath(result.path);
      setFilePathInput("");
      setCreateOpen(false);
      setViewMode("edit");
    } catch (createError) {
      toast.error(
        createError instanceof Error
          ? createError.message
          : t.skills.fileCreateFailed,
      );
    }
  };

  const handleRenameFile = async () => {
    if (!selectedSkill?.name || !selectedFilePath || !filePathInput.trim()) {
      return;
    }
    try {
      const result = await renameFile.mutateAsync({
        skillName: selectedSkill.name,
        filePath: selectedFilePath,
        newPath: filePathInput.trim(),
      });
      toast.success(result.message || t.skills.fileRenameSuccess);
      setSelectedFilePath(result.path);
      setFilePathInput("");
      setRenameOpen(false);
    } catch (renameError) {
      toast.error(
        renameError instanceof Error
          ? renameError.message
          : t.skills.fileRenameFailed,
      );
    }
  };

  const handleDeleteFile = async () => {
    if (!selectedSkill?.name || !selectedFilePath || !skill) return;
    try {
      const deletedPath = selectedFilePath;
      const result = await deleteFile.mutateAsync({
        skillName: selectedSkill.name,
        filePath: deletedPath,
      });
      toast.success(result.message || t.skills.fileDeleteSuccess);
      const nextFiles = skill.files.filter((path) => path !== deletedPath);
      setSelectedFilePath(
        nextFiles.includes("SKILL.md") ? "SKILL.md" : (nextFiles[0] ?? null),
      );
      setDeleteFileOpen(false);
      setViewMode("preview");
    } catch (deleteError) {
      toast.error(
        deleteError instanceof Error
          ? deleteError.message
          : t.skills.fileDeleteFailed,
      );
    }
  };

  return (
    <Dialog open={!!selectedSkill} onOpenChange={onOpenChange}>
      <DialogContent className="flex h-[88vh] min-h-[640px] !w-[84vw] !max-w-[84vw] flex-col gap-4 sm:!max-w-[84vw] xl:!w-[78vw] xl:!max-w-[1280px]">
        <DialogHeader className="shrink-0">
          <div className="flex flex-col gap-3">
            <div>
              <DialogTitle className="text-xl">
                {displaySkill?.name ?? t.skills.detailTitle}
              </DialogTitle>
              <DialogDescription className="mt-2 max-w-4xl text-sm leading-6">
                {displaySkill?.description ?? t.skills.detailDescription}
              </DialogDescription>
            </div>
            {displaySkill && (
              <div className="flex flex-wrap gap-2">
                <Badge variant="secondary">
                  {displaySkill.category === "public"
                    ? t.common.public
                    : t.common.custom}
                </Badge>
                <Badge variant={displaySkill.enabled ? "default" : "outline"}>
                  {displaySkill.enabled ? t.skills.enabled : t.skills.disabled}
                </Badge>
                {displaySkill.license && (
                  <Badge variant="outline">{displaySkill.license}</Badge>
                )}
                {skill?.relative_path && (
                  <Badge variant="outline">{skill.relative_path}</Badge>
                )}
              </div>
            )}
          </div>
        </DialogHeader>
        <div className="min-h-0 flex-1 overflow-hidden">
          {isLoading && (
            <div className="text-muted-foreground flex size-full items-center justify-center text-sm">
              {t.common.loading}
            </div>
          )}
          {error && (
            <div className="text-destructive flex size-full items-center justify-center text-sm">
              {t.skills.loadDetailError}
            </div>
          )}
          {displaySkill && !isLoading && !error && (
            <div className="flex size-full min-h-0 flex-col gap-4">
              {skill && (
                <div className="grid size-full min-h-0 gap-4 md:grid-cols-[280px_minmax(0,1fr)]">
                  <section className="flex min-h-0 flex-col rounded-md border p-3">
                    <div className="mb-3 flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 text-sm font-medium">
                        <FileTextIcon className="size-4" />
                        {t.skills.filesTitle}
                      </div>
                      {isCustom && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => {
                            setFilePathInput("");
                            setCreateOpen(true);
                          }}
                        >
                          <PlusIcon className="size-4" />
                          {t.skills.newFile}
                        </Button>
                      )}
                    </div>
                    <div className="min-h-0 flex-1 overflow-auto">
                      {skill.files.length === 0 ? (
                        <p className="text-muted-foreground text-sm">
                          {t.skills.noFiles}
                        </p>
                      ) : (
                        <ul className="space-y-1 pr-1">
                          {skill.files.map((file) => (
                            <li key={file}>
                              <button
                                type="button"
                                className={`hover:bg-muted flex w-full items-center rounded px-2 py-1.5 text-left font-mono text-xs ${
                                  selectedFilePath === file
                                    ? "bg-muted text-foreground"
                                    : "text-muted-foreground"
                                }`}
                                title={file}
                                onClick={() => handleSelectFile(file)}
                              >
                                <span className="truncate">{file}</span>
                              </button>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  </section>
                  <section className="flex min-h-0 flex-col rounded-md border p-3">
                    <div className="mb-3 flex items-center justify-between gap-3">
                      <div className="min-w-0 truncate text-sm font-medium">
                        {selectedFilePath ?? t.skills.noFileSelected}
                      </div>
                      {selectedFilePath && (
                        <div className="flex shrink-0 items-center gap-2">
                          {canEditFile && (
                            <div className="bg-muted inline-flex rounded-md p-0.5">
                              <Button
                                size="sm"
                                variant={
                                  viewMode === "preview" ? "secondary" : "ghost"
                                }
                                onClick={() => setViewMode("preview")}
                              >
                                {t.common.preview}
                              </Button>
                              <Button
                                size="sm"
                                variant={
                                  viewMode === "edit" ? "secondary" : "ghost"
                                }
                                onClick={() => setViewMode("edit")}
                              >
                                {t.common.edit}
                              </Button>
                            </div>
                          )}
                          {canRenameOrDeleteFile && (
                            <>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => {
                                  setFilePathInput(selectedFilePath);
                                  setRenameOpen(true);
                                }}
                              >
                                <PencilIcon className="size-4" />
                                {t.common.rename}
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => setDeleteFileOpen(true)}
                              >
                                <Trash2Icon className="size-4" />
                                {t.common.delete}
                              </Button>
                            </>
                          )}
                        </div>
                      )}
                    </div>
                    <div className="min-h-0 flex-1 overflow-auto">
                      {isFileLoading && (
                        <div className="text-muted-foreground flex size-full items-center justify-center text-sm">
                          {t.common.loading}
                        </div>
                      )}
                      {fileError && (
                        <div className="text-destructive flex size-full items-center justify-center text-sm">
                          {t.skills.loadFileError}
                        </div>
                      )}
                      {file && !isFileLoading && !fileError && (
                        <>
                          {viewMode === "edit" && canEditFile ? (
                            <div className="flex size-full min-h-0 flex-col gap-3">
                              <CodeEditor
                                className="min-h-0 flex-1 border"
                                value={draftContent}
                                onChange={setDraftContent}
                                settings={{
                                  lineNumbers: true,
                                  foldGutter: true,
                                }}
                              />
                              <div className="flex justify-end gap-2">
                                <Button
                                  variant="outline"
                                  onClick={() => {
                                    setDraftContent(file.content);
                                    setViewMode("preview");
                                  }}
                                  disabled={saveFile.isPending}
                                >
                                  <XIcon className="size-4" />
                                  {t.common.cancel}
                                </Button>
                                <Button
                                  onClick={handleSaveFile}
                                  disabled={!isDirty || saveFile.isPending}
                                >
                                  <SaveIcon className="size-4" />
                                  {saveFile.isPending
                                    ? t.skills.savingFile
                                    : t.common.save}
                                </Button>
                              </div>
                            </div>
                          ) : isMarkdownFile(file.path) ? (
                            <Streamdown
                              className="size-full text-sm [&>*:first-child]:mt-0 [&>*:last-child]:mb-0"
                              {...streamdownPlugins}
                            >
                              {previewContent(file.path, file.content)}
                            </Streamdown>
                          ) : (
                            <pre className="bg-muted/30 min-h-full overflow-auto rounded-md p-4 font-mono text-xs whitespace-pre-wrap">
                              {file.content}
                            </pre>
                          )}
                        </>
                      )}
                    </div>
                  </section>
                </div>
              )}
            </div>
          )}
        </div>
        <div className="flex shrink-0 justify-end gap-2">
          {canDelete && displaySkill && (
            <Button
              variant="destructive"
              onClick={() => onRequestDelete(displaySkill)}
            >
              <Trash2Icon className="size-4" />
              {t.skills.deleteSkill}
            </Button>
          )}
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t.common.close}
          </Button>
        </div>
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{t.skills.newFileTitle}</DialogTitle>
              <DialogDescription>{t.skills.filePathHint}</DialogDescription>
            </DialogHeader>
            <Input
              value={filePathInput}
              placeholder="references/example.md"
              onChange={(event) => setFilePathInput(event.target.value)}
            />
            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                onClick={() => setCreateOpen(false)}
                disabled={createFile.isPending}
              >
                {t.common.cancel}
              </Button>
              <Button
                onClick={handleCreateFile}
                disabled={!filePathInput.trim() || createFile.isPending}
              >
                <PlusIcon className="size-4" />
                {t.common.create}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
        <Dialog open={renameOpen} onOpenChange={setRenameOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{t.skills.renameFileTitle}</DialogTitle>
              <DialogDescription>{t.skills.filePathHint}</DialogDescription>
            </DialogHeader>
            <Input
              value={filePathInput}
              onChange={(event) => setFilePathInput(event.target.value)}
            />
            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                onClick={() => setRenameOpen(false)}
                disabled={renameFile.isPending}
              >
                {t.common.cancel}
              </Button>
              <Button
                onClick={handleRenameFile}
                disabled={!filePathInput.trim() || renameFile.isPending}
              >
                <PencilIcon className="size-4" />
                {t.common.rename}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
        <Dialog open={deleteFileOpen} onOpenChange={setDeleteFileOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{t.skills.deleteFileTitle}</DialogTitle>
              <DialogDescription>
                {selectedFilePath
                  ? t.skills.deleteFileDescription.replace(
                      "{path}",
                      selectedFilePath,
                    )
                  : t.skills.deleteFileDescription}
              </DialogDescription>
            </DialogHeader>
            <div className="flex justify-end gap-2">
              <Button
                variant="outline"
                onClick={() => setDeleteFileOpen(false)}
                disabled={deleteFile.isPending}
              >
                {t.common.cancel}
              </Button>
              <Button
                variant="destructive"
                onClick={handleDeleteFile}
                disabled={deleteFile.isPending}
              >
                <Trash2Icon className="size-4" />
                {t.common.delete}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </DialogContent>
    </Dialog>
  );
}

function DeleteSkillDialog({
  skill,
  onOpenChange,
  onDeleted,
}: {
  skill: Skill | null;
  onOpenChange: (open: boolean) => void;
  onDeleted: () => void;
}) {
  const { t } = useI18n();
  const remove = useDeleteSkill();

  const handleDelete = async () => {
    if (!skill) return;
    try {
      const result = await remove.mutateAsync(skill.name);
      toast.success(result.message || t.skills.deleteSuccess);
      onOpenChange(false);
      onDeleted();
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : t.skills.deleteFailed,
      );
    }
  };

  return (
    <Dialog open={!!skill} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t.skills.deleteTitle}</DialogTitle>
          <DialogDescription>
            {skill
              ? t.skills.deleteDescription.replace("{name}", skill.name)
              : t.skills.deleteDescription}
          </DialogDescription>
        </DialogHeader>
        <div className="flex justify-end gap-2">
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={remove.isPending}
          >
            {t.common.cancel}
          </Button>
          <Button
            variant="destructive"
            onClick={handleDelete}
            disabled={remove.isPending}
          >
            <Trash2Icon className="size-4" />
            {remove.isPending ? t.skills.deleting : t.skills.deleteSkill}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function SkillWorkspacePage() {
  const { t } = useI18n();
  const { skills, isLoading, error } = useSkills();
  const [category, setCategory] = useState<SkillCategory>("public");
  const [uploadOpen, setUploadOpen] = useState(false);
  const [selectedSkill, setSelectedSkill] = useState<Skill | null>(null);
  const [deleteSkill, setDeleteSkill] = useState<Skill | null>(null);

  const filteredSkills = useMemo(
    () => skills.filter((skill) => skill.category === category),
    [skills, category],
  );

  return (
    <WorkspaceContainer>
      <WorkspaceHeader />
      <WorkspaceBody>
        <div className="flex size-full flex-col">
          <header className="flex shrink-0 items-center justify-center pt-8">
            <div className="flex w-full max-w-(--container-width-lg) items-start justify-between gap-4">
              <div>
                <h1 className="text-2xl font-semibold">{t.skills.title}</h1>
                <p className="text-muted-foreground mt-1 text-sm">
                  {t.skills.description}
                </p>
              </div>
              <Button
                onClick={() => setUploadOpen(true)}
                disabled={env.NEXT_PUBLIC_STATIC_WEBSITE_ONLY === "true"}
              >
                <PackagePlusIcon className="size-4" />
                {t.skills.installSkill}
              </Button>
            </div>
          </header>
          <main className="min-h-0 flex-1">
            <div className="mx-auto h-full w-full max-w-(--container-width-lg) py-4">
              <section className="flex h-full min-w-0 flex-col">
                <Tabs
                  value={category}
                  onValueChange={(value) => setCategory(value as SkillCategory)}
                >
                  <TabsList variant="line" className="flex-wrap">
                    {SKILL_CATEGORIES.map(({ value, icon: Icon }) => (
                      <TabsTrigger key={value} value={value}>
                        <Icon className="size-4" />
                        {value === "public" ? t.common.public : t.common.custom}
                      </TabsTrigger>
                    ))}
                  </TabsList>
                </Tabs>
                <div className="min-h-0 flex-1 overflow-auto pt-4">
                  {isLoading && (
                    <div className="text-muted-foreground text-sm">
                      {t.common.loading}
                    </div>
                  )}
                  {error && (
                    <div className="text-destructive text-sm">
                      {t.skills.loadError}
                    </div>
                  )}
                  {!isLoading && !error && filteredSkills.length === 0 && (
                    <EmptySkills
                      category={category}
                      onInstall={() => setUploadOpen(true)}
                    />
                  )}
                  {!isLoading && !error && filteredSkills.length > 0 && (
                    <SkillList
                      skills={filteredSkills}
                      onSelect={setSelectedSkill}
                    />
                  )}
                </div>
              </section>
            </div>
          </main>
        </div>
      </WorkspaceBody>
      <SkillUploadDialog open={uploadOpen} onOpenChange={setUploadOpen} />
      <SkillDetailDialog
        selectedSkill={selectedSkill}
        onOpenChange={(open) => !open && setSelectedSkill(null)}
        onRequestDelete={setDeleteSkill}
      />
      <DeleteSkillDialog
        skill={deleteSkill}
        onOpenChange={(open) => !open && setDeleteSkill(null)}
        onDeleted={() => {
          setSelectedSkill(null);
          setDeleteSkill(null);
        }}
      />
    </WorkspaceContainer>
  );
}
