import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  deleteAsset,
  getAsset,
  listAssets,
  publishAsset,
  unpublishAsset,
  updateAsset,
} from "./api";
import type { ListAssetsParams } from "./types";

export function useAssets(params: ListAssetsParams = {}) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["assets", params],
    queryFn: () => listAssets(params),
  });
  return { assets: data?.assets ?? [], nextCursor: data?.next_cursor ?? null, isLoading, error };
}

export function useAsset(assetId: string | null | undefined) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["assets", assetId],
    queryFn: () => getAsset(assetId!),
    enabled: !!assetId,
  });
  return { asset: data ?? null, isLoading, error };
}

function useInvalidateAssets() {
  const queryClient = useQueryClient();
  return () => {
    void queryClient.invalidateQueries({ queryKey: ["assets"] });
  };
}

export function usePublishAsset() {
  const invalidate = useInvalidateAssets();
  return useMutation({ mutationFn: publishAsset, onSuccess: invalidate });
}

export function useUnpublishAsset() {
  const invalidate = useInvalidateAssets();
  return useMutation({ mutationFn: unpublishAsset, onSuccess: invalidate });
}

export function useDeleteAsset() {
  const invalidate = useInvalidateAssets();
  return useMutation({ mutationFn: deleteAsset, onSuccess: invalidate });
}

export function useUpdateAsset() {
  const invalidate = useInvalidateAssets();
  return useMutation({
    mutationFn: ({ assetId, request }: { assetId: string; request: Parameters<typeof updateAsset>[1] }) =>
      updateAsset(assetId, request),
    onSuccess: invalidate,
  });
}
