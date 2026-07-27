import type {
  AnalysisResult,
  BugReport,
  HealthStatus,
  Project,
  ProjectDetail,
} from '../types';

const API_BASE = '/api';

/**
 * Single place where fetch errors get turned into readable messages.
 * The Express error handler replies with `{ error: "..." }`, so surface that
 * instead of a generic "Failed to fetch" whenever it is available.
 */
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new Error('Cannot reach the CodeLens backend. Is the Express server running on port 5000?');
  }

  const raw = await res.text();
  let payload: unknown = null;
  if (raw) {
    try {
      payload = JSON.parse(raw);
    } catch {
      payload = raw;
    }
  }

  if (!res.ok) {
    const message =
      typeof payload === 'object' && payload !== null && 'error' in payload
        ? String((payload as { error: unknown }).error)
        : typeof payload === 'string' && payload
          ? payload
          : `Request failed with status ${res.status}`;
    throw new Error(message);
  }

  return payload as T;
}

/* ------------------------------------------------------------------ health */

export function fetchHealth(): Promise<HealthStatus> {
  return request<HealthStatus>('/health');
}

/* ---------------------------------------------------------------- projects */

export function fetchProjects(): Promise<Project[]> {
  return request<Project[]>('/projects');
}

export function fetchProjectById(id: string): Promise<ProjectDetail> {
  return request<ProjectDetail>(`/projects/${id}`);
}

export function createProjectGithub(
  name: string,
  description: string,
  repoUrl: string,
): Promise<Project> {
  return request<Project>('/projects', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, description, repoUrl }),
  });
}

export function createProjectZip(
  name: string,
  description: string,
  zipFile: File,
): Promise<Project> {
  const formData = new FormData();
  formData.append('name', name);
  formData.append('description', description);
  formData.append('zipFile', zipFile);

  return request<Project>('/projects/zip', { method: 'POST', body: formData });
}

export function triggerReindex(projectId: string): Promise<{ message: string; projectId: string }> {
  return request<{ message: string; projectId: string }>(`/projects/${projectId}/index`, {
    method: 'POST',
  });
}

/* -------------------------------------------------------------------- bugs */

export function fetchBugsForProject(projectId: string): Promise<BugReport[]> {
  return request<BugReport[]>(`/bugs/project/${projectId}`);
}

export function createBugReport(data: {
  projectId: string;
  title: string;
  description: string;
  severity: string;
  stepsToReproduce?: string;
  externalBugId?: string;
  reporter?: string;
}): Promise<BugReport> {
  return request<BugReport>('/bugs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
}

export function uploadBugsCsv(
  projectId: string,
  csvFile: File,
): Promise<{ count: number; bugs: BugReport[] }> {
  const formData = new FormData();
  formData.append('projectId', projectId);
  formData.append('file', csvFile);

  return request<{ count: number; bugs: BugReport[] }>('/bugs/csv', {
    method: 'POST',
    body: formData,
  });
}

/* ---------------------------------------------------------------- analysis */

export function triggerAGTRAnalysis(
  bugReportId: string,
): Promise<{ message: string; analysisId: string }> {
  return request<{ message: string; analysisId: string }>('/analysis/trigger', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ bugReportId }),
  });
}

export function fetchAnalysisById(analysisId: string): Promise<AnalysisResult> {
  return request<AnalysisResult>(`/analysis/${analysisId}`);
}

export function fetchAnalysesForProject(projectId: string): Promise<AnalysisResult[]> {
  return request<AnalysisResult[]>(`/analysis/project/${projectId}`);
}
