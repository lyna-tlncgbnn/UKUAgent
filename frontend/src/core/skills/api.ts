import { getBackendBaseURL } from "@/core/config";

import type {
  Skill,
  SkillDetail,
  SkillFileContent,
  SkillFileMutationResult,
} from "./type";

function skillFileUrl(skillName: string, filePath: string) {
  return `${getBackendBaseURL()}/api/skills/${encodeURIComponent(skillName)}/files/${filePath
    .split("/")
    .map(encodeURIComponent)
    .join("/")}`;
}

async function readPayload(response: Response) {
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(
      payload.detail ?? `HTTP ${response.status}: ${response.statusText}`,
    );
  }
  return payload;
}

export async function loadSkills() {
  const skills = await fetch(`${getBackendBaseURL()}/api/skills`);
  const json = await skills.json();
  return json.skills as Skill[];
}

export async function enableSkill(skillName: string, enabled: boolean) {
  const response = await fetch(
    `${getBackendBaseURL()}/api/skills/${skillName}`,
    {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        enabled,
      }),
    },
  );
  return response.json();
}

export async function loadSkillDetail(skillName: string) {
  const response = await fetch(
    `${getBackendBaseURL()}/api/skills/${skillName}/detail`,
  );
  const payload = await readPayload(response);
  return payload as SkillDetail;
}

export async function deleteSkill(skillName: string) {
  const response = await fetch(`${getBackendBaseURL()}/api/skills/${skillName}`, {
    method: "DELETE",
  });
  const payload = await readPayload(response);
  return payload as { success: boolean; skill_name: string; message: string };
}

export async function loadSkillFile(skillName: string, filePath: string) {
  const response = await fetch(skillFileUrl(skillName, filePath));
  const payload = await readPayload(response);
  return payload as SkillFileContent;
}

export async function saveSkillFile({
  skillName,
  filePath,
  content,
}: {
  skillName: string;
  filePath: string;
  content: string;
}) {
  const response = await fetch(skillFileUrl(skillName, filePath), {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ content }),
  });
  const payload = await readPayload(response);
  return payload as SkillFileMutationResult;
}

export async function createSkillFile({
  skillName,
  path,
  content = "",
}: {
  skillName: string;
  path: string;
  content?: string;
}) {
  const response = await fetch(
    `${getBackendBaseURL()}/api/skills/${encodeURIComponent(skillName)}/files`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ path, content }),
    },
  );
  const payload = await readPayload(response);
  return payload as SkillFileMutationResult;
}

export async function renameSkillFile({
  skillName,
  filePath,
  newPath,
}: {
  skillName: string;
  filePath: string;
  newPath: string;
}) {
  const response = await fetch(skillFileUrl(skillName, filePath), {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ new_path: newPath }),
  });
  const payload = await readPayload(response);
  return payload as SkillFileMutationResult;
}

export async function deleteSkillFile({
  skillName,
  filePath,
}: {
  skillName: string;
  filePath: string;
}) {
  const response = await fetch(skillFileUrl(skillName, filePath), {
    method: "DELETE",
  });
  const payload = await readPayload(response);
  return payload as SkillFileMutationResult;
}

export interface InstallSkillRequest {
  thread_id: string;
  path: string;
}

export interface InstallSkillResponse {
  success: boolean;
  skill_name: string;
  message: string;
}

export async function installSkill(
  request: InstallSkillRequest,
): Promise<InstallSkillResponse> {
  const response = await fetch(`${getBackendBaseURL()}/api/skills/install`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    // Handle HTTP error responses (4xx, 5xx)
    const errorData = await response.json().catch(() => ({}));
    const errorMessage =
      errorData.detail ?? `HTTP ${response.status}: ${response.statusText}`;
    return {
      success: false,
      skill_name: "",
      message: errorMessage,
    };
  }

  return response.json();
}

export async function uploadSkill(file: File): Promise<InstallSkillResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${getBackendBaseURL()}/api/skills/upload`, {
    method: "POST",
    body: formData,
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(
      payload.detail ?? `HTTP ${response.status}: ${response.statusText}`,
    );
  }

  return payload as InstallSkillResponse;
}
