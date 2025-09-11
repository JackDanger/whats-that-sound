export type ReadyItem = { path: string; name: string };

export type Status = {
  counts: Record<string, number>;
  processed: number;
  total: number;
  ready: ReadyItem[];
};

export type PathsResponse = {
  current: { source_dir: string; target_dir: string };
  staged: { source_dir: string; target_dir: string };
};

export type DebugJobs = {
  counts: Record<string, number>;
  recent: any[];
};

export type ListedEntry = { name: string; path: string };

export type Decision = {
  metadata: {
    folder_path?: string;
    folder_name?: string;
    total_files?: number;
    files?: { relative_path?: string; filename?: string }[];
  };
  proposal: {
    artist?: string;
    album?: string;
    year?: string | number;
    release_type?: string;
    reasoning?: string;
  };
};


