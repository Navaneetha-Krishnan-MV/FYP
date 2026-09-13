export type ProjectStatus = 'PENDING' | 'CLONING' | 'PARSING' | 'EMBEDDING' | 'GRAPHING' | 'GIT_INDEXING' | 'READY' | 'FAILED';
export type BugSeverity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
export type ConfidenceLevel = 'LOW' | 'MEDIUM' | 'HIGH';
export type AnalysisStatus = 'pending' | 'processing' | 'completed' | 'failed';

/** Pipeline stages a project moves through before it can be analysed. */
export const INDEXING_STAGES: ProjectStatus[] = [
  'PENDING',
  'CLONING',
  'PARSING',
  'EMBEDDING',
  'GRAPHING',
  'GIT_INDEXING',
  'READY',
];

export interface Project {
  id: string;
  name: string;
  description?: string;
  repoUrl?: string;
  repoType?: string;
  localPath?: string;
  status: ProjectStatus;
  errorMsg?: string;
  fileCount: number;
  chunkCount: number;
  commitCount: number;
  languages: string[];
  createdAt: string;
  updatedAt: string;
  _count?: {
    codeChunks: number;
    commits: number;
    bugReports: number;
  };
}

export interface CodeChunk {
  id: string;
  filePath: string;
  language: string;
  chunkType: string;
  className?: string;
  functionName: string;
  signature?: string;
  codeContent: string;
  startLine: number;
  endLine: number;
  imports: string[];
  calls: string[];
}

export interface Commit {
  id: string;
  commitHash: string;
  authorName: string;
  authorEmail: string;
  message: string;
  committedAt: string;
}

/** Shape returned by GET /api/projects/:id — includes a slice of related records. */
export interface ProjectDetail extends Project {
  codeChunks?: CodeChunk[];
  commits?: Commit[];
  bugReports?: BugReport[];
}

export interface BugReport {
  id: string;
  externalBugId?: string;
  title: string;
  description: string;
  severity: BugSeverity;
  reporter?: string;
  stepsToReproduce?: string;
  source: string;
  createdAt: string;
  projectId: string;
  analysisResults?: AnalysisResult[];
}

export interface AGTRCandidate {
  chunkId: string;
  functionName: string;
  filePath: string;
  rank: number;
  agtrScore: number;
  semanticScore: number;
  graphScore: number;
  gitScore: number;
  codeContent?: string;
  className?: string;
}

export interface AGTRWeights {
  ws: number;
  wg: number;
  wt: number;
}

/** Git evidence rows emitted by ai-server/app/analysis/git_scorer.py */
export interface GitEvidenceCommit {
  hash: string;
  author: string;
  date: string;
  message: string;
  diff?: string;
}

export interface PhaseToolStep {
  step: number;
  action: 'tool' | 'finish';
  tool?: string;
  arguments?: Record<string, unknown>;
  status?: string;
  evidence_ids?: string[];
  summary?: string;
}

export interface PhaseAgentTrace {
  role: string;
  question: string;
  trace: PhaseToolStep[];
}

export interface PhaseOutput {
  phase: 'understand' | 'investigate' | 'rank' | 'reason' | 'verify' | 'replan' | 'finalize';
  status: 'completed' | 'active' | 'pending';
  round?: number;
  decision?: string;
  // understand
  summary?: string;
  search_terms?: string[];
  missing_information?: string[];
  // investigate
  findings?: { role: string; summary: string; evidence_ids: string[] }[];
  agent_traces?: PhaseAgentTrace[];
  new_evidence_count?: number;
  // rank
  weights?: AGTRWeights;
  signal_availability?: Record<'semantic' | 'graph' | 'git', boolean>;
  signal_gaps?: Record<'semantic' | 'graph' | 'git', number>;
  semantic_gap?: number;
  hops_used?: number;
  ranking?: AGTRCandidate[];
  warnings?: string[];
  // reason
  reason?: string;
  hypotheses?: {
    candidate_id: string;
    mechanism: string;
    suggested_fix: string;
    evidence_ids: string[];
    counterevidence_ids?: string[];
    assumptions: string[];
    ranking_rationale?: string;
  }[];
  // verify
  verdict?: string;
  primary_candidate_id?: string;
  explanation?: string;
  evidence_ids?: string[];
  follow_up?: { role: string; question: string }[];
  limitations?: string[];
  // replan
  tasks?: { role: string; question: string }[];
  // finalize
  termination_reason?: string;
  rounds_used?: number;
}

export interface EvidenceContext {
  engine?: 'agentic';
  variant?: 'agent-agtr';
  signal_availability?: Record<'semantic' | 'graph' | 'git', boolean>;
  ranking_warnings?: string[];
  stage?: string;
  error?: string;
  reasoning?: { provider: string; model: string };
  embedding?: { provider: string; model: string };
  generation?: string;
  revision?: string;
  events?: { stage: string; round?: number }[];
  evidence?: AgenticEvidence[];
  report?: AgenticReport;
  phase_outputs?: PhaseOutput[];
  usage?: { llm_calls: number; tool_calls: number; elapsed_seconds: number };
  top_candidates?: unknown[];
  dependency_paths?: string[];
  git_commits?: GitEvidenceCommit[];
  confidence_level?: string;
  agtr_weights?: AGTRWeights;
  confidence_gap_C?: number;
}

export interface AgenticEvidence {
  id: string;
  kind: 'code' | 'git' | 'dependency';
  file_path?: string;
  function_name?: string;
  start_line?: number;
  end_line?: number;
  code_content?: string;
  diff?: string;
  commit_hash?: string;
  message?: string;
  caller_id?: string;
  callee_id?: string;
  resolution?: string;
  truncated?: boolean;
}

export interface AgenticHypothesis {
  candidate_id: string;
  mechanism: string;
  suggested_fix: string;
  assumptions: string[];
  evidence_ids: string[];
  ranking_rationale?: string;
}

export interface AgenticReport {
  outcome: 'supported_hypothesis' | 'inconclusive';
  primary_hypothesis: AgenticHypothesis | null;
  hypotheses: AgenticHypothesis[];
  support_level: string;
  runtime_verified: boolean;
  termination_reason: string;
  rounds_used: number;
  limitations: string[];
  verification: { explanation?: string };
  selected_candidate_rank?: number | null;
  ranking_rationale?: string;
}

export interface AnalysisResult {
  id: string;
  status: AnalysisStatus;
  semanticScores?: unknown;
  graphScores?: unknown;
  gitScores?: unknown;
  finalRanking?: AGTRCandidate[];
  confidence?: ConfidenceLevel;
  confidenceValue?: number;
  semanticGap?: number;
  agtrWeights?: AGTRWeights;
  hopsUsed?: number;
  rootCauseFile?: string;
  rootCauseFunction?: string;
  rootCauseCommit?: string;
  explanation?: string;
  suggestedFix?: string;
  dependencyPath?: string;
  evidenceContext?: EvidenceContext;
  processingTimeMs?: number;
  createdAt: string;
  completedAt?: string;
  bugReportId: string;
  projectId: string;
  bugReport?: BugReport;
  project?: Partial<Project>;
}

export interface HealthStatus {
  status: string;
  service: string;
  timestamp?: string;
  database?: string;
}
