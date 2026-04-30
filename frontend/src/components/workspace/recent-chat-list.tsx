"use client";

import {
  Download,
  Eraser,
  FileJson,
  FileText,
  MoreHorizontal,
  Pencil,
  Share2,
  Trash2,
} from "lucide-react";
import Link from "next/link";
import { useParams, usePathname, useRouter } from "next/navigation";
import { type MouseEvent, useCallback, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import {
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuAction,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { getAPIClient } from "@/core/api";
import { useI18n } from "@/core/i18n/hooks";
import {
  exportThreadAsJSON,
  exportThreadAsMarkdown,
} from "@/core/threads/export";
import {
  useDeleteThread,
  useClearWecomThread,
  useOpenWecomThread,
  useRenameThread,
  useThreads,
} from "@/core/threads/hooks";
import type { AgentThread, AgentThreadState } from "@/core/threads/types";
import { pathOfThread, titleOfThread } from "@/core/threads/utils";
import { env } from "@/env";
import { isIMEComposing } from "@/lib/ime";

export function RecentChatList() {
  const { t } = useI18n();
  const router = useRouter();
  const pathname = usePathname();
  const { thread_id: threadIdFromPath } = useParams<{ thread_id: string }>();
  const {
    data: threads = [],
    error,
    isLoading,
  } = useThreads();
  const { mutate: deleteThread } = useDeleteThread();
  const { mutate: renameThread } = useRenameThread();
  const { mutate: clearWecomThread } = useClearWecomThread();
  const { mutate: openWecomThread } = useOpenWecomThread();

  // Rename dialog state
  const [renameDialogOpen, setRenameDialogOpen] = useState(false);
  const [renameThreadId, setRenameThreadId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");

  const handleDelete = useCallback(
    (threadId: string) => {
      deleteThread({ threadId });
      if (threadId === threadIdFromPath) {
        const threadIndex = threads.findIndex((t) => t.thread_id === threadId);
        let nextThreadId = "new";
        if (threadIndex > -1) {
          if (threads[threadIndex + 1]) {
            nextThreadId = threads[threadIndex + 1]!.thread_id;
          } else if (threads[threadIndex - 1]) {
            nextThreadId = threads[threadIndex - 1]!.thread_id;
          }
        }
        void router.push(`/workspace/chats/${nextThreadId}`);
      }
    },
    [deleteThread, router, threadIdFromPath, threads],
  );

  const handleRenameClick = useCallback(
    (threadId: string, currentTitle: string) => {
      setRenameThreadId(threadId);
      setRenameValue(currentTitle);
      setRenameDialogOpen(true);
    },
    [],
  );

  const handleRenameSubmit = useCallback(() => {
    if (renameThreadId && renameValue.trim()) {
      renameThread({ threadId: renameThreadId, title: renameValue.trim() });
      setRenameDialogOpen(false);
      setRenameThreadId(null);
      setRenameValue("");
    }
  }, [renameThread, renameThreadId, renameValue]);

  const handleClearWecomThread = useCallback(
    (threadId: string) => {
      clearWecomThread(undefined, {
        onSuccess() {
          toast.success(t.sidebar.clearChatHistorySuccess);
          if (threadId === threadIdFromPath) {
            window.location.reload();
          }
        },
        onError(error) {
          toast.error(error instanceof Error ? error.message : "Failed to clear chat history");
        },
      });
    },
    [clearWecomThread, t.sidebar.clearChatHistorySuccess, threadIdFromPath],
  );

  const handleOpenWecomThread = useCallback(
    (event: MouseEvent<HTMLAnchorElement>) => {
      event.preventDefault();
      openWecomThread(undefined, {
        onSuccess(data) {
          router.push(`/workspace/chats/${data.thread_id}`);
        },
        onError(error) {
          toast.error(error instanceof Error ? error.message : "Failed to open WeCom chat");
        },
      });
    },
    [openWecomThread, router],
  );

  const handleShare = useCallback(
    async (threadId: string) => {
      // Always use Vercel URL for sharing so others can access
      const VERCEL_URL = "https://deer-flow-v2.vercel.app";
      const isLocalhost =
        window.location.hostname === "localhost" ||
        window.location.hostname === "127.0.0.1";
      // On localhost: use Vercel URL; On production: use current origin
      const baseUrl = isLocalhost ? VERCEL_URL : window.location.origin;
      const shareUrl = `${baseUrl}/workspace/chats/${threadId}`;
      try {
        await navigator.clipboard.writeText(shareUrl);
        toast.success(t.clipboard.linkCopied);
      } catch {
        toast.error(t.clipboard.failedToCopyToClipboard);
      }
    },
    [t],
  );

  const handleExport = useCallback(
    async (thread: AgentThread, format: "markdown" | "json") => {
      try {
        const apiClient = getAPIClient();
        const state = await apiClient.threads.getState<AgentThreadState>(
          thread.thread_id,
        );
        const messages = state.values?.messages ?? [];
        if (messages.length === 0) {
          toast.error(t.conversation.noMessages);
          return;
        }
        if (format === "markdown") {
          exportThreadAsMarkdown(thread, messages);
        } else {
          exportThreadAsJSON(thread, messages);
        }
        toast.success(t.common.exportSuccess);
      } catch {
        toast.error("Failed to export conversation");
      }
    },
    [t],
  );

  if (isLoading) {
    return (
      <SidebarGroup>
        <SidebarGroupLabel>{t.sidebar.recentChats}</SidebarGroupLabel>
        <SidebarGroupContent className="px-2 text-sm text-muted-foreground">
          {t.common.loading}
        </SidebarGroupContent>
      </SidebarGroup>
    );
  }

  if (error) {
    const message =
      error instanceof Error && error.message.includes("Authentication required")
        ? t.sidebar.recentChatsUnauthenticated
        : t.sidebar.recentChatsLoadError;
    return (
      <SidebarGroup>
        <SidebarGroupLabel>{t.sidebar.recentChats}</SidebarGroupLabel>
        <SidebarGroupContent className="px-2 text-sm text-muted-foreground">
          {message}
        </SidebarGroupContent>
      </SidebarGroup>
    );
  }

  if (threads.length === 0) {
    return (
      <SidebarGroup>
        <SidebarGroupLabel>{t.sidebar.recentChats}</SidebarGroupLabel>
        <SidebarGroupContent className="px-2 text-sm text-muted-foreground">
          {t.sidebar.recentChatsEmpty}
        </SidebarGroupContent>
      </SidebarGroup>
    );
  }
  return (
    <>
      <SidebarGroup>
        <SidebarGroupLabel>
          {env.NEXT_PUBLIC_STATIC_WEBSITE_ONLY !== "true"
            ? t.sidebar.recentChats
            : t.sidebar.demoChats}
        </SidebarGroupLabel>
        <SidebarGroupContent className="group-data-[collapsible=icon]:pointer-events-none group-data-[collapsible=icon]:-mt-8 group-data-[collapsible=icon]:opacity-0">
          <SidebarMenu>
            <div className="flex w-full flex-col gap-1">
              {threads.map((thread) => {
                const isActive = pathOfThread(thread.thread_id) === pathname;
                const isWecomThread = thread.metadata?.source === "wecom";
                return (
                  <SidebarMenuItem
                    key={thread.thread_id}
                    className="group/side-menu-item"
                  >
                    <SidebarMenuButton isActive={isActive} asChild>
                      <div>
                        <Link
                          className="text-muted-foreground block w-full whitespace-nowrap group-hover/side-menu-item:overflow-hidden"
                          href={pathOfThread(thread.thread_id)}
                          onClick={isWecomThread ? handleOpenWecomThread : undefined}
                        >
                          {titleOfThread(thread)}
                        </Link>
                        {env.NEXT_PUBLIC_STATIC_WEBSITE_ONLY !== "true" && (
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <SidebarMenuAction
                                showOnHover
                                className="bg-background/50 hover:bg-background"
                              >
                                <MoreHorizontal />
                                <span className="sr-only">{t.common.more}</span>
                              </SidebarMenuAction>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent
                              className="w-48 rounded-lg"
                              side={"right"}
                              align={"start"}
                            >
                              {!isWecomThread && (
                                <DropdownMenuItem
                                  onSelect={() =>
                                    handleRenameClick(
                                      thread.thread_id,
                                      titleOfThread(thread),
                                    )
                                  }
                                >
                                  <Pencil className="text-muted-foreground" />
                                  <span>{t.common.rename}</span>
                                </DropdownMenuItem>
                              )}
                              <DropdownMenuItem
                                onSelect={() => handleShare(thread.thread_id)}
                              >
                                <Share2 className="text-muted-foreground" />
                                <span>{t.common.share}</span>
                              </DropdownMenuItem>
                              <DropdownMenuSub>
                                <DropdownMenuSubTrigger>
                                  <Download className="text-muted-foreground" />
                                  <span>{t.common.export}</span>
                                </DropdownMenuSubTrigger>
                                <DropdownMenuSubContent>
                                  <DropdownMenuItem
                                    onSelect={() =>
                                      handleExport(thread, "markdown")
                                    }
                                  >
                                    <FileText className="text-muted-foreground" />
                                    <span>{t.common.exportAsMarkdown}</span>
                                  </DropdownMenuItem>
                                  <DropdownMenuItem
                                    onSelect={() =>
                                      handleExport(thread, "json")
                                    }
                                  >
                                    <FileJson className="text-muted-foreground" />
                                    <span>{t.common.exportAsJSON}</span>
                                  </DropdownMenuItem>
                                </DropdownMenuSubContent>
                              </DropdownMenuSub>
                              <DropdownMenuSeparator />
                              {isWecomThread ? (
                                <DropdownMenuItem
                                  onSelect={() => handleClearWecomThread(thread.thread_id)}
                                >
                                  <Eraser className="text-muted-foreground" />
                                  <span>{t.sidebar.clearChatHistory}</span>
                                </DropdownMenuItem>
                              ) : (
                                <DropdownMenuItem
                                  onSelect={() => handleDelete(thread.thread_id)}
                                >
                                  <Trash2 className="text-muted-foreground" />
                                  <span>{t.common.delete}</span>
                                </DropdownMenuItem>
                              )}
                            </DropdownMenuContent>
                          </DropdownMenu>
                        )}
                      </div>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                );
              })}
            </div>
          </SidebarMenu>
        </SidebarGroupContent>
      </SidebarGroup>

      {/* Rename Dialog */}
      <Dialog open={renameDialogOpen} onOpenChange={setRenameDialogOpen}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>{t.common.rename}</DialogTitle>
          </DialogHeader>
          <div className="py-4">
            <Input
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              placeholder={t.common.rename}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !isIMEComposing(e)) {
                  e.preventDefault();
                  handleRenameSubmit();
                }
              }}
            />
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setRenameDialogOpen(false)}
            >
              {t.common.cancel}
            </Button>
            <Button onClick={handleRenameSubmit}>{t.common.save}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
