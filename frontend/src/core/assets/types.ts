export type AssetKind = "upload" | "generated" | "converted" | "export" | "snapshot";
export type AssetVisibility = "private" | "org_shared" | "restricted";
export type AssetStatus = "active" | "archived" | "deleted";
export type AssetSpace = "mine" | "org_shared" | "thread" | "task" | "trash";

export type Asset = {
  id: string;
  owner_user_id: string;
  filename: string;
  display_name: string;
  kind: AssetKind;
  mime_type: string | null;
  size_bytes: number | null;
  storage_uri: string;
  checksum: string | null;
  visibility: AssetVisibility;
  status: AssetStatus;
  thread_id: string | null;
  run_id: string | null;
  task_id: string | null;
  agent_id: string | null;
  message_id: string | null;
  tool_call_id: string | null;
  source_asset_id: string | null;
  version_group_id: string | null;
  version_number: number;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
};

export type AssetListResponse = {
  assets: Asset[];
  next_cursor: string | null;
};

export type ListAssetsParams = {
  space?: AssetSpace;
  thread_id?: string;
  task_id?: string;
  kind?: AssetKind;
  q?: string;
  limit?: number;
  cursor?: string | null;
};
