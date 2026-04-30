import { getBackendBaseURL } from "@/core/config";

import type { Asset, AssetListResponse, ListAssetsParams } from "./types";

async function readErrorDetail(response: Response, fallback: string) {
  const error = await response.json().catch(() => ({ detail: fallback }));
  return error.detail ?? fallback;
}

function buildAssetQuery(params: ListAssetsParams = {}) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  }
  const text = query.toString();
  return text ? `?${text}` : "";
}

export async function listAssets(params: ListAssetsParams = {}): Promise<AssetListResponse> {
  const response = await fetch(`${getBackendBaseURL()}/api/assets${buildAssetQuery(params)}`);
  if (!response.ok) {
    throw new Error(await readErrorDetail(response, "Failed to load assets"));
  }
  return response.json() as Promise<AssetListResponse>;
}

export async function getAsset(assetId: string): Promise<Asset> {
  const response = await fetch(`${getBackendBaseURL()}/api/assets/${assetId}`);
  if (!response.ok) {
    throw new Error(await readErrorDetail(response, "Failed to load asset"));
  }
  return response.json() as Promise<Asset>;
}

export async function updateAsset(assetId: string, request: { display_name?: string; metadata?: Record<string, unknown>; status?: "active" | "archived" }): Promise<Asset> {
  const response = await fetch(`${getBackendBaseURL()}/api/assets/${assetId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    throw new Error(await readErrorDetail(response, "Failed to update asset"));
  }
  return response.json() as Promise<Asset>;
}

export async function publishAsset(assetId: string): Promise<Asset> {
  const response = await fetch(`${getBackendBaseURL()}/api/assets/${assetId}/publish`, { method: "POST" });
  if (!response.ok) {
    throw new Error(await readErrorDetail(response, "Failed to publish asset"));
  }
  return response.json() as Promise<Asset>;
}

export async function unpublishAsset(assetId: string): Promise<Asset> {
  const response = await fetch(`${getBackendBaseURL()}/api/assets/${assetId}/unpublish`, { method: "POST" });
  if (!response.ok) {
    throw new Error(await readErrorDetail(response, "Failed to unpublish asset"));
  }
  return response.json() as Promise<Asset>;
}

export async function deleteAsset(assetId: string): Promise<Asset> {
  const response = await fetch(`${getBackendBaseURL()}/api/assets/${assetId}`, { method: "DELETE" });
  if (!response.ok) {
    throw new Error(await readErrorDetail(response, "Failed to delete asset"));
  }
  return response.json() as Promise<Asset>;
}

export function assetContentUrl(assetId: string, download = false) {
  return `${getBackendBaseURL()}/api/assets/${assetId}/content${download ? "?download=true" : ""}`;
}
