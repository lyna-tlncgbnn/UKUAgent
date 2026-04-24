export type AgentVisibility = "private" | "org_shared";

export interface Agent {
  name: string;
  slug: string;
  description: string;
  model: string | null;
  tool_groups: string[] | null;
  visibility: AgentVisibility;
  is_owner: boolean;
  soul?: string | null;
}

export interface CreateAgentRequest {
  name: string;
  description?: string;
  model?: string | null;
  tool_groups?: string[] | null;
  visibility?: AgentVisibility;
  soul?: string;
}

export interface UpdateAgentRequest {
  description?: string | null;
  model?: string | null;
  tool_groups?: string[] | null;
  visibility?: AgentVisibility | null;
  soul?: string | null;
}
