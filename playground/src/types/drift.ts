// TypeScript types derived from drift.output.schema.json (v2.2)
// Do not edit manually — regenerate if the schema version bumps.

export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info';

export interface FindingCompact {
  rank: number;
  finding_id: string;
  signal: string;
  signal_abbrev?: string;
  rule_id?: string | null;
  severity: Severity;
  status?: 'active' | 'suppressed' | 'resolved';
  finding_context?: string;
  impact?: number;
  score_contribution?: number;
  title: string;
  file?: string | null;
  start_line?: number | null;
  duplicate_count?: number;
  next_step?: string | null;
}

export interface AnalysisStatus {
  status: string;
  degraded: boolean;
  is_fully_reliable: boolean;
  causes: string[];
  affected_components: string[];
  events: unknown[];
}

export interface Summary {
  total_files?: number;
  total_functions?: number;
  ai_attributed_ratio?: number;
  ai_tools_detected?: string[];
  analysis_duration_seconds?: number | null;
}

export interface CompactSummary {
  findings_total?: number;
  findings_deduplicated?: number;
  duplicate_findings_removed?: number;
  suppressed_total?: number;
  critical_count?: number;
  high_count?: number;
  fix_first_count?: number;
}

export interface DriftOutput {
  schema_version: string;
  version: string;
  signal_abbrev_map?: Record<string, string>;
  repo: string;
  analyzed_at: string;
  drift_score: number;
  drift_score_scope?: string;
  severity: Severity;
  analysis_status?: AnalysisStatus;
  summary?: Summary;
  findings_compact?: FindingCompact[];
  compact_summary?: CompactSummary;
  modules?: ModuleScore[];
}

export interface ModuleScore {
  path: string;
  drift_score: number;
  severity: Severity;
  signal_scores?: Record<string, number>;
  finding_count: number;
  ai_ratio?: number;
}

/** Derived per-signal summary for the heatmap, built from findings_compact */
export interface SignalStatus {
  abbrev: string;
  name: string;
  /** 'pass' = no findings for this signal */
  severity: Severity | 'pass';
  findings: FindingCompact[];
}

const SEVERITY_ORDER: Record<Severity | 'pass', number> = {
  critical: 5,
  high: 4,
  medium: 3,
  low: 2,
  info: 1,
  pass: 0,
};

export function severityOrder(s: Severity | 'pass'): number {
  return SEVERITY_ORDER[s] ?? 0;
}

/** Aggregate findings_compact into per-signal status for the heatmap. */
export function deriveSignalStatuses(output: DriftOutput): SignalStatus[] {
  const abbrevMap = output.signal_abbrev_map ?? {};
  const findingsByAbbrev = new Map<string, FindingCompact[]>();

  for (const f of output.findings_compact ?? []) {
    const key = f.signal_abbrev ?? f.signal;
    const list = findingsByAbbrev.get(key);
    if (list) {
      list.push(f);
    } else {
      findingsByAbbrev.set(key, [f]);
    }
  }

  const statuses: SignalStatus[] = Object.entries(abbrevMap).map(([abbrev, name]) => {
    const findings = findingsByAbbrev.get(abbrev) ?? [];
    const worstSeverity: Severity | 'pass' =
      findings.length === 0
        ? 'pass'
        : findings.reduce<Severity | 'pass'>((worst, f) => {
            return severityOrder(f.severity) > severityOrder(worst) ? f.severity : worst;
          }, 'pass');
    return { abbrev, name, severity: worstSeverity, findings };
  });

  // Also include signals from findings that aren't in the abbrevMap
  for (const [abbrev, findings] of findingsByAbbrev.entries()) {
    if (!(abbrev in abbrevMap)) {
      const worstSeverity = findings.reduce<Severity | 'pass'>((worst, f) => {
        return severityOrder(f.severity) > severityOrder(worst) ? f.severity : worst;
      }, 'pass');
      statuses.push({ abbrev, name: findings[0]?.signal ?? abbrev, severity: worstSeverity, findings });
    }
  }

  return statuses.sort((a, b) => severityOrder(b.severity) - severityOrder(a.severity));
}

export const SEVERITY_COLOR: Record<Severity | 'pass', string> = {
  critical: '#f85149',
  high: '#e85d04',
  medium: '#d29922',
  low: '#7ee787',
  info: '#8b949e',
  pass: '#3fb950',
};

export const SEVERITY_BG: Record<Severity | 'pass', string> = {
  critical: 'rgba(248, 81, 73, 0.15)',
  high: 'rgba(232, 93, 4, 0.15)',
  medium: 'rgba(210, 153, 34, 0.12)',
  low: 'rgba(63, 185, 80, 0.10)',
  info: 'rgba(139, 148, 158, 0.10)',
  pass: 'rgba(63, 185, 80, 0.10)',
};

export const SEVERITY_LABEL: Record<Severity | 'pass', string> = {
  critical: 'CRITICAL',
  high: 'HIGH',
  medium: 'MEDIUM',
  low: 'LOW',
  info: 'INFO',
  pass: 'PASS',
};
