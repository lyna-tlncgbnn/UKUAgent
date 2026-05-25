import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createSkillFile,
  deleteSkill,
  deleteSkillFile,
  enableSkill,
  loadSkillDetail,
  loadSkillFile,
  renameSkillFile,
  saveSkillFile,
  uploadSkill,
} from "./api";

import { loadSkills } from ".";

export function useSkills() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["skills"],
    queryFn: () => loadSkills(),
  });
  return { skills: data ?? [], isLoading, error };
}

export function useEnableSkill() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({
      skillName,
      enabled,
    }: {
      skillName: string;
      enabled: boolean;
    }) => {
      await enableSkill(skillName, enabled);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["skills"] });
    },
  });
}

export function useSkillDetail(skillName: string | null) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["skills", "detail", skillName],
    queryFn: () => loadSkillDetail(skillName!),
    enabled: !!skillName,
  });
  return { skill: data ?? null, isLoading, error };
}

export function useSkillFile(skillName: string | null, filePath: string | null) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["skills", skillName, "files", filePath],
    queryFn: () => loadSkillFile(skillName!, filePath!),
    enabled: !!skillName && !!filePath,
  });
  return { file: data ?? null, isLoading, error };
}

export function useSaveSkillFile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: saveSkillFile,
    onSuccess: (result, variables) => {
      void queryClient.invalidateQueries({
        queryKey: ["skills", variables.skillName, "files", variables.filePath],
      });
      void queryClient.invalidateQueries({
        queryKey: ["skills", "detail", variables.skillName],
      });
      if (variables.filePath === "SKILL.md") {
        void queryClient.invalidateQueries({ queryKey: ["skills"] });
      }
    },
  });
}

export function useCreateSkillFile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createSkillFile,
    onSuccess: (_result, variables) => {
      void queryClient.invalidateQueries({
        queryKey: ["skills", "detail", variables.skillName],
      });
    },
  });
}

export function useRenameSkillFile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: renameSkillFile,
    onSuccess: (_result, variables) => {
      void queryClient.invalidateQueries({
        queryKey: ["skills", "detail", variables.skillName],
      });
      void queryClient.invalidateQueries({
        queryKey: ["skills", variables.skillName, "files"],
      });
    },
  });
}

export function useDeleteSkillFile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteSkillFile,
    onSuccess: (_result, variables) => {
      void queryClient.invalidateQueries({
        queryKey: ["skills", "detail", variables.skillName],
      });
      void queryClient.invalidateQueries({
        queryKey: ["skills", variables.skillName, "files"],
      });
    },
  });
}

export function useDeleteSkill() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteSkill,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["skills"] });
    },
  });
}

export function useUploadSkill() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: uploadSkill,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["skills"] });
    },
  });
}
