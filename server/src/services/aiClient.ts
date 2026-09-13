const AI_SERVER_URL = process.env.AI_SERVER_URL || "http://localhost:8000";

export async function triggerRepositoryIndexing(projectId: string, repoUrl?: string, zipPath?: string) {
  const response = await fetch(`${AI_SERVER_URL}/api/index-repository`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      project_id: projectId,
      repo_url: repoUrl || null,
      zip_path: zipPath || null,
    }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`AI Server indexing failed: ${errorText}`);
  }

  return await response.json();
}

export async function triggerBugAnalysis(bugReportId: string, analysisId: string) {
  const response = await fetch(`${AI_SERVER_URL}/api/analyze-bug`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      bug_report_id: bugReportId,
      analysis_id: analysisId,
    }),
    signal: AbortSignal.timeout(15000),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`AI Server bug analysis failed: ${errorText}`);
  }

  return await response.json();
}
