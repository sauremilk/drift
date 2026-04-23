import type { SignalStatus } from '../types/drift';
import { SEVERITY_COLOR, SEVERITY_BG, SEVERITY_LABEL } from '../types/drift';

interface SignalHeatmapProps {
  signals: SignalStatus[];
  selectedAbbrev: string | null;
  onSelect: (abbrev: string) => void;
}

export function SignalHeatmap({ signals, selectedAbbrev, onSelect }: SignalHeatmapProps) {
  if (signals.length === 0) {
    return (
      <div className="flex flex-col gap-2 rounded-lg border border-drift-border bg-drift-panel p-6 text-center">
        <p className="text-sm text-drift-muted">Run analysis to see signal results.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-3 gap-2 sm:grid-cols-4 lg:grid-cols-3 xl:grid-cols-4">
        {signals.map((sig) => {
          const isSelected = sig.abbrev === selectedAbbrev;
          const isPass = sig.severity === 'pass';
          const colorKey = isPass ? 'low' : sig.severity;

          const borderColor = SEVERITY_COLOR[colorKey as keyof typeof SEVERITY_COLOR] ?? '#58a6ff';
          const bgColor = SEVERITY_BG[colorKey as keyof typeof SEVERITY_BG] ?? '#58a6ff22';
          const textColor = SEVERITY_COLOR[colorKey as keyof typeof SEVERITY_COLOR] ?? '#58a6ff';

          return (
            <button
              key={sig.abbrev}
              onClick={() => onSelect(sig.abbrev)}
              title={`${sig.name} — ${isPass ? 'pass' : `${sig.findingCount} finding${sig.findingCount !== 1 ? 's' : ''}`}`}
              className={`group flex flex-col items-start gap-1 rounded-md border p-2.5 text-left transition-all duration-150 ${
                isSelected ? 'ring-1 ring-drift-accent/60' : 'hover:brightness-110'
              }`}
              style={{
                borderColor: isSelected ? '#58a6ff' : borderColor,
                background: bgColor,
              }}
            >
              <span
                className="font-mono text-sm font-bold leading-none"
                style={{ color: textColor }}
              >
                {sig.abbrev}
              </span>
              <span className="line-clamp-1 text-xs text-drift-muted">{sig.name}</span>
              {!isPass && (
                <span
                  className="mt-0.5 text-xs font-medium"
                  style={{ color: textColor }}
                >
                  {sig.findingCount} {SEVERITY_LABEL[sig.severity as keyof typeof SEVERITY_LABEL]}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Legend */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 pt-1">
        {(['critical', 'high', 'medium', 'low'] as const).map((sev) => (
          <span key={sev} className="flex items-center gap-1.5 text-xs text-drift-muted">
            <span
              className="h-2 w-2 rounded-full"
              style={{ background: SEVERITY_COLOR[sev] }}
            />
            {SEVERITY_LABEL[sev]}
          </span>
        ))}
        <span className="ml-auto text-xs text-drift-muted/60">
          TVS · SMS · CCS excluded (git-history)
        </span>
      </div>
    </div>
  );
}
