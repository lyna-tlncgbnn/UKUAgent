export interface Skill {
  name: string;
  description: string;
  category: string;
  license: string | null;
  enabled: boolean;
}

export interface SkillDetail extends Skill {
  relative_path: string;
  skill_file: string;
  content: string;
  files: string[];
}

export interface SkillFileContent {
  path: string;
  content: string;
  files: string[];
}

export interface SkillFileMutationResult {
  success: boolean;
  path: string | null;
  files: string[];
  message: string;
}
