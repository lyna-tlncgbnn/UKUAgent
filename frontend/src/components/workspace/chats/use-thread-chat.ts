"use client";

import { useParams, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

export function useThreadChat() {
  const { thread_id: threadIdFromPath } = useParams<{ thread_id: string }>();
  const searchParams = useSearchParams();
  const [threadId, setThreadId] = useState(() => threadIdFromPath);

  const [isNewThread, setIsNewThread] = useState(
    () => threadIdFromPath === "new",
  );

  useEffect(() => {
    setThreadId(threadIdFromPath);
    setIsNewThread(threadIdFromPath === "new");
  }, [threadIdFromPath]);

  const isMock = searchParams.get("mock") === "true";
  return { threadId, setThreadId, isNewThread, setIsNewThread, isMock };
}
