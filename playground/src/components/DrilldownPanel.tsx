import type { SignalStatus } from '../types/drift';
import { SEVERITY_COLOR, SEVERITY_LABEL } from '../types/drift';

interface DrilldownPanelProps {
  signal: SignalStatus | null;
}

export function DrilldownPanel({ signal }: DrilldownPanelProps) {
  if (!signal) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-drift-border bg-drift-panel p-8 text-center">
        <svg
          viewBox="0 0 24 24"
          className="h-8 w-8 text-drift-muted/40"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25H12"
          />
        </svg>
        <p className="text-sm text-drift-muted">Click a signal tile to see findings</p>
      </div>
    );
  }

  const isPass = signal.severity === 'pass';
  const color = isPass
    ? '#3fb950'
    : (SEVERITY_COLOR[signal.severity as keyof typeof SEVERITY_COLOR] ?? '#58a6ff');

  const docsUrl = `https://mick-gsk.github.io/drift/signals/${signal.abbrev.toLowerCase()}/`;

  return (
    <div className="flex flex-1 flex-col gap-4 overflow-hidden rounded-lg border border-drift-border bg-drift-panel p-4">
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-mono text-lg font-bold text-drift-text">{signal.abbrev}</span>
            <span
              className="rounded-full px-2 py-0.5 text-xs font-semibold uppercase tracking-wider"
              style={{ background: `${color}22`, color }}
            >
              {isPass ? 'pass' : SEVERITY_LABEL[signal.severity as keyof typeof SEVERITY_LABEL]}
            </span>
          </div>
          <p className="mt-0.5 text-sm text-drift-muted">{signal.name}</p>
        </div>
        <a
          href={docsUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="shrink-0 rounded border border-drift-border px-2 py-1 text-xs text-drift-muted transition-colors hover:border-drift-accent/50 hover:text-drift-accent"
        >
          Docs ↗
        </a>
      </div>

      {/* Findings */}
      {isPass ? (
        <div className="flex flex-1 items-center justify-center rounded-md border border-drift-border/50 bg-[#3fb95011] p-6 text-center">
          <div>
            <span className="text-2xl">✓</span>
            <p className="mt-2 text-sm font-medium text-[#3fb950]">No findings — signal passes</p>
          </div>
        </div>
      ) : (
        <div className="flex flex-1 flex-col gap-2 overflow-y-auto pr-1">
          {signal.findings.length === 0 ? (
            <p className="text-sm text-drift-muted">No detailed findings available.</p>
          ) : (
            signal.findings.map((finding, i) => (
              <div
                key={i}
                className="rounded-md border border-drift-border bg-drift-bg p-3"
              >
                {/* Severity badge + title */}
                <div className="flex items-start gap-2">
                  <span
                    className="mt-0.5 shrink-0 rounded px-1.5 py-0.5 font-mono text-xs font-bold uppercase"
                    style={{
                      background: `${SEVERITY_COLOR[finding.severity as keyof typeof SEVERITY_COLOR] ?? color}22`,
                      color: SEVERITY_COLOR[finding.severity as keyof typeof SEVERITY_COLOR] ?? color,
                    }}
                  >
                    {finding.severity}
                  </span>
                  <p className="text-sm font-medium text-drift-text">{finding.title}</p>
                </div>

                {/* Context */}
                {finding.finding_context && (
                  <p className="mt-2 text-xs leading-relaxed text-drift-muted">
                    {finding.finding_context}
                  </p>
                )}

                {/* Next step */}
                {finding.next_step && (
                  <div className="mt-2 flex items-start gap-1.5 rounded border-l-2 border-drift-accent/50 pl-2">
                    <span className="shrink-0 text-xs font-medium text-drift-accent">→</span>
                    <p className="text-xs text-drift-muted">{finding.next_step}</p>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
