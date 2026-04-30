"use client";

import { BotIcon, CalendarClockIcon, MessageCircle, MessagesSquare } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { toast } from "sonner";

import {
  SidebarGroup,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { useI18n } from "@/core/i18n/hooks";
import { useOpenWecomThread } from "@/core/threads/hooks";

export function WorkspaceNavChatList() {
  const { t } = useI18n();
  const pathname = usePathname();
  const router = useRouter();
  const { mutate: openWecomThread, isPending: isOpeningWecomThread } =
    useOpenWecomThread();

  const handleOpenWecomThread = () => {
    openWecomThread(undefined, {
      onSuccess(data) {
        router.push(`/workspace/chats/${data.thread_id}`);
      },
      onError(error) {
        toast.error(error instanceof Error ? error.message : "Failed to open WeCom chat");
      },
    });
  };

  return (
    <SidebarGroup className="pt-1">
      <SidebarMenu>
        <SidebarMenuItem>
          <SidebarMenuButton isActive={pathname === "/workspace/chats"} asChild>
            <Link className="text-muted-foreground" href="/workspace/chats">
              <MessagesSquare />
              <span>{t.sidebar.chats}</span>
            </Link>
          </SidebarMenuButton>
        </SidebarMenuItem>
        <SidebarMenuItem>
          <SidebarMenuButton
            isActive={pathname.startsWith("/workspace/agents")}
            asChild
          >
            <Link className="text-muted-foreground" href="/workspace/agents">
              <BotIcon />
              <span>{t.sidebar.agents}</span>
            </Link>
          </SidebarMenuButton>
        </SidebarMenuItem>
        <SidebarMenuItem>
          <SidebarMenuButton
            isActive={pathname.startsWith("/workspace/scheduled-tasks")}
            asChild
          >
            <Link className="text-muted-foreground" href="/workspace/scheduled-tasks">
              <CalendarClockIcon />
              <span>{t.sidebar.scheduledTasks}</span>
            </Link>
          </SidebarMenuButton>
        </SidebarMenuItem>
        <SidebarMenuItem>
          <SidebarMenuButton
            disabled={isOpeningWecomThread}
            onClick={handleOpenWecomThread}
          >
            <MessageCircle />
            <span>{t.sidebar.wecomChat}</span>
          </SidebarMenuButton>
        </SidebarMenuItem>
      </SidebarMenu>
    </SidebarGroup>
  );
}
