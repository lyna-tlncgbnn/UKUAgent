"use client";

import {
  ArchiveIcon,
  BoxIcon,
  DownloadIcon,
  EyeIcon,
  ExternalLinkIcon,
  FilesIcon,
  HistoryIcon,
  MoreHorizontalIcon,
  PackageIcon,
  Share2Icon,
  Trash2Icon,
  Undo2Icon,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { Streamdown } from "streamdown";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Item, ItemActions, ItemContent, ItemDescription, ItemMedia, ItemTitle } from "@/components/ui/item";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  WorkspaceBody,
  WorkspaceContainer,
  WorkspaceHeader,
} from "@/components/workspace/workspace-container";
import { streamdownPlugins } from "@/core/streamdown";
import { assetContentUrl, useAssets, useDeleteAsset, usePublishAsset, useUnpublishAsset, useUpdateAsset } from "@/core/assets";
import type { Asset, AssetSpace } from "@/core/assets";
import { useI18n } from "@/core/i18n/hooks";
import { getFileExtensionDisplayName, getFileIcon } from "@/core/utils/files";

import { ArtifactLink } from "../citations/artifact-link";

const ASSET_SPACES: { value: AssetSpace; icon: React.ElementType }[] = [
  { value: "mine", icon: FilesIcon },
  { value: "org_shared", icon: Share2Icon },
  { value: "thread", icon: HistoryIcon },
  { value: "task", icon: PackageIcon },
  { value: "trash", icon: Trash2Icon },
];

function formatBytes(value: number | null) {
  if (value == null) return "";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

function sourceLabel(asset: Asset, t: ReturnType<typeof useI18n>["t"]) {
  if (asset.task_id) return t.assets.sourceTask;
  if (asset.thread_id) return t.assets.sourceThread;
  return t.assets.sourceStandalone;
}

function canPreviewAsset(asset: Asset) {
  const mime = asset.mime_type ?? "";
  const name = asset.filename.toLowerCase();
  return (
    mime.startsWith("text/") ||
    mime.startsWith("image/") ||
    mime === "application/pdf" ||
    name.endsWith(".md") ||
    name.endsWith(".markdown") ||
    name.endsWith(".json") ||
    name.endsWith(".csv") ||
    name.endsWith(".txt")
  );
}

function isMarkdownAsset(asset: Asset) {
  const name = asset.filename.toLowerCase();
  return name.endsWith(".md") || name.endsWith(".markdown") || asset.mime_type === "text/markdown";
}

function useAssetTextContent(asset: Asset | null, enabled: boolean) {
  const [content, setContent] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!asset || !enabled) {
      setContent("");
      setError(null);
      setIsLoading(false);
      return;
    }

    const controller = new AbortController();
    setIsLoading(true);
    setError(null);
    fetch(assetContentUrl(asset.id), { signal: controller.signal })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Failed to load asset content: ${response.status}`);
        }
        return response.text();
      })
      .then(setContent)
      .catch((err) => {
        if (!controller.signal.aborted) {
          setError(err instanceof Error ? err : new Error(String(err)));
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      });

    return () => controller.abort();
  }, [asset, enabled]);

  return { content, isLoading, error };
}

function AssetPreview({ asset }: { asset: Asset }) {
  const { t } = useI18n();
  const url = assetContentUrl(asset.id);
  const mime = asset.mime_type ?? "";
  const name = asset.filename.toLowerCase();
  const isMarkdown = isMarkdownAsset(asset);
  const shouldFetchText =
    isMarkdown ||
    mime.startsWith("text/") ||
    name.endsWith(".json") ||
    name.endsWith(".csv") ||
    name.endsWith(".txt");
  const { content, isLoading, error } = useAssetTextContent(asset, shouldFetchText);

  if (!canPreviewAsset(asset)) {
    return (
      <div className="flex size-full items-center justify-center bg-muted/10 p-8">
        <Empty>
          <EmptyHeader>
            <EmptyMedia variant="icon">
              {getFileIcon(asset.filename, "size-8")}
            </EmptyMedia>
            <EmptyTitle>{t.assets.previewUnavailableTitle}</EmptyTitle>
            <EmptyDescription>{t.assets.previewUnavailableDescription}</EmptyDescription>
          </EmptyHeader>
        </Empty>
      </div>
    );
  }
  if (isMarkdown) {
    return (
      <div className="size-full overflow-auto px-6 py-4">
        {isLoading && <div className="text-muted-foreground text-sm">{t.common.loading}</div>}
        {error && <div className="text-destructive text-sm">{t.assets.loadError}</div>}
        {!isLoading && !error && (
          <Streamdown
            className="size-full"
            {...streamdownPlugins}
            components={{ a: ArtifactLink }}
          >
            {content}
          </Streamdown>
        )}
      </div>
    );
  }
  if (shouldFetchText) {
    return (
      <pre className="size-full overflow-auto whitespace-pre-wrap px-6 py-4 font-mono text-sm">
        {isLoading ? t.common.loading : error ? t.assets.loadError : content}
      </pre>
    );
  }
  if (mime.startsWith("image/")) {
    return (
      <div className="flex size-full items-center justify-center bg-muted/20 p-4">
        <img className="max-h-full max-w-full rounded-md object-contain" src={url} alt={asset.display_name} />
      </div>
    );
  }
  return <iframe className="size-full border-0" src={url} title={asset.display_name} />;
}

function AssetActionsMenu({
  asset,
  onPreview,
  onCleared,
  showPreview = true,
}: {
  asset: Asset;
  onPreview: (asset: Asset) => void;
  onCleared: () => void;
  showPreview?: boolean;
}) {
  const { t } = useI18n();
  const publish = usePublishAsset();
  const unpublish = useUnpublishAsset();
  const remove = useDeleteAsset();
  const restore = useUpdateAsset();

  const canUnpublish = asset.visibility === "org_shared";
  const isDeleted = asset.status === "deleted";
  const handleAction = async (action: () => Promise<Asset>, success: string) => {
    try {
      await action();
      toast.success(success);
      if (isDeleted || success === t.assets.deleted) onCleared();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t.assets.operationFailed);
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          size="icon-sm"
          variant="ghost"
          aria-label={t.common.more}
          onClick={(event) => event.stopPropagation()}
        >
          <MoreHorizontalIcon />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" onClick={(event) => event.stopPropagation()}>
        {showPreview && (
          <DropdownMenuItem onSelect={() => onPreview(asset)}>
            <EyeIcon />
            <span>{t.common.preview}</span>
          </DropdownMenuItem>
        )}
        {asset.thread_id && !asset.task_id && (
          <DropdownMenuItem asChild>
            <Link href={`/workspace/chats/${asset.thread_id}`}>
              <ExternalLinkIcon />
              <span>{t.assets.openThread}</span>
            </Link>
          </DropdownMenuItem>
        )}
        <DropdownMenuItem asChild>
          <a href={assetContentUrl(asset.id, true)} target="_blank">
            <DownloadIcon />
            <span>{t.common.download}</span>
          </a>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        {!isDeleted && (
          <DropdownMenuItem
            disabled={publish.isPending || unpublish.isPending}
            onSelect={() =>
              handleAction(
                () => (canUnpublish ? unpublish.mutateAsync(asset.id) : publish.mutateAsync(asset.id)),
                canUnpublish ? t.assets.unpublished : t.assets.published,
              )
            }
          >
            <Share2Icon />
            <span>{canUnpublish ? t.assets.unpublish : t.assets.publishToOrg}</span>
          </DropdownMenuItem>
        )}
        {isDeleted ? (
          <DropdownMenuItem
            disabled={restore.isPending}
            onSelect={() => handleAction(() => restore.mutateAsync({ assetId: asset.id, request: { status: "active" } }), t.assets.restored)}
          >
            <Undo2Icon />
            <span>{t.assets.restore}</span>
          </DropdownMenuItem>
        ) : (
          <DropdownMenuItem
            variant="destructive"
            disabled={remove.isPending}
            onSelect={() => handleAction(() => remove.mutateAsync(asset.id), t.assets.deleted)}
          >
            <Trash2Icon />
            <span>{t.common.delete}</span>
          </DropdownMenuItem>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function AssetPreviewDialog({
  asset,
  onOpenChange,
}: {
  asset: Asset | null;
  onOpenChange: (open: boolean) => void;
}) {
  const { t } = useI18n();

  return (
    <Dialog open={!!asset} onOpenChange={onOpenChange}>
      <DialogContent className="flex h-[90vh] !w-[90vw] !max-w-[90vw] sm:!max-w-[90vw] flex-col gap-0 p-0">
        {asset && (
          <>
            <DialogHeader className="shrink-0 border-b px-5 py-4 pr-12">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <DialogTitle className="truncate text-base">{asset.display_name}</DialogTitle>
                  <DialogDescription>
                    {[getFileExtensionDisplayName(asset.filename), formatBytes(asset.size_bytes), sourceLabel(asset, t)].filter(Boolean).join(" / ")}
                  </DialogDescription>
                </div>
                <div className="shrink-0">
                  <AssetActionsMenu asset={asset} onPreview={() => undefined} onCleared={() => onOpenChange(false)} showPreview={false} />
                </div>
              </div>
            </DialogHeader>
            <div className="min-h-0 flex-1">
              <AssetPreview asset={asset} />
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

export function AssetWorkspacePage() {
  const { t, locale } = useI18n();
  const [space, setSpace] = useState<AssetSpace>("mine");
  const [previewAsset, setPreviewAsset] = useState<Asset | null>(null);
  const params = useMemo(() => {
    if (space === "thread") return { space: "mine" as AssetSpace, kind: "generated" as const, limit: 100 };
    if (space === "task") return { space: "mine" as AssetSpace, limit: 100 };
    return { space, limit: 100 };
  }, [space]);
  const { assets, isLoading, error } = useAssets(params);
  const visibleAssets = useMemo(
    () => (space === "task" ? assets.filter((asset) => asset.task_id) : assets),
    [assets, space],
  );

  return (
    <WorkspaceContainer>
      <WorkspaceHeader />
      <WorkspaceBody>
        <div className="flex size-full flex-col">
          <header className="flex shrink-0 items-center justify-center pt-8">
            <div className="w-full max-w-(--container-width-lg)">
              <div>
                <h1 className="text-2xl font-semibold">{t.assets.title}</h1>
                <p className="text-muted-foreground mt-1 text-sm">{t.assets.description}</p>
              </div>
            </div>
          </header>
          <main className="min-h-0 flex-1">
            <div className="mx-auto h-full w-full max-w-(--container-width-lg) py-4">
              <section className="flex h-full min-w-0 flex-col">
                <Tabs value={space} onValueChange={(value) => setSpace(value as AssetSpace)}>
                  <TabsList variant="line" className="flex-wrap">
                    {ASSET_SPACES.map(({ value, icon: Icon }) => (
                      <TabsTrigger key={value} value={value}>
                        <Icon className="size-4" />
                        {t.assets.spaces[value]}
                      </TabsTrigger>
                    ))}
                  </TabsList>
                </Tabs>
                <div className="min-h-0 flex-1 overflow-auto pt-4">
                  {isLoading && <div className="text-muted-foreground text-sm">{t.common.loading}</div>}
                  {error && <div className="text-destructive text-sm">{t.assets.loadError}</div>}
                  {!isLoading && visibleAssets.length === 0 && (
                    <Empty>
                      <EmptyHeader>
                        <EmptyMedia variant="icon">
                          <BoxIcon />
                        </EmptyMedia>
                        <EmptyTitle>{t.assets.emptyTitle}</EmptyTitle>
                        <EmptyDescription>{t.assets.emptyBySpace[space]}</EmptyDescription>
                      </EmptyHeader>
                    </Empty>
                  )}
                  <div className="flex flex-col gap-2">
                    {visibleAssets.map((asset) => (
                      <Item
                        key={asset.id}
                        variant="outline"
                        className="cursor-pointer rounded-lg"
                        onClick={() => setPreviewAsset(asset)}
                      >
                        <ItemMedia>{getFileIcon(asset.filename, "size-5")}</ItemMedia>
                        <ItemContent>
                          <ItemTitle>
                            {asset.display_name}
                            {asset.visibility === "org_shared" && <Badge variant="secondary">{t.assets.orgShared}</Badge>}
                            {asset.status === "deleted" && <Badge variant="destructive">{t.assets.deletedStatus}</Badge>}
                          </ItemTitle>
                          <ItemDescription>
                            {[
                              t.assets.kinds[asset.kind],
                              formatBytes(asset.size_bytes),
                              sourceLabel(asset, t),
                              new Date(asset.created_at).toLocaleString(locale),
                            ]
                              .filter(Boolean)
                              .join(" / ")}
                          </ItemDescription>
                        </ItemContent>
                        <ItemActions>
                          {asset.status === "archived" && <ArchiveIcon className="text-muted-foreground size-4" />}
                          <AssetActionsMenu asset={asset} onPreview={setPreviewAsset} onCleared={() => setPreviewAsset(null)} />
                        </ItemActions>
                      </Item>
                    ))}
                  </div>
                </div>
              </section>
            </div>
          </main>
        </div>
      </WorkspaceBody>
      <AssetPreviewDialog asset={previewAsset} onOpenChange={(open) => !open && setPreviewAsset(null)} />
    </WorkspaceContainer>
  );
}
