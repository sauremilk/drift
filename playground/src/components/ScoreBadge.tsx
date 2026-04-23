import type { Severity } from '../types/drift';
import { SEVERITY_LABEL } from '../types/drift';

interface ScoreBadgeProps {
  score: number;
  severity: Severity;
}

const SCORE_COLOR: Record<string, string> = {
  low: '#3fb950',
  medium: '#d29922',
  high: '#f0883e',
  critical: '#f85149',
};

function getColor(score: number): string {
  if (score < 0.3) return SCORE_COLOR.low;
  if (score < 0.6) return SCORE_COLOR.medium;
  if (score < 0.8) return SCORE_COLOR.high;
  return SCORE_COLOR.critical;
}

export function ScoreBadge({ score, severity }: ScoreBadgeProps) {
  const color = getColor(score);
  const pct = Math.min(1, Math.max(0, score));

  // SVG circle parameters
  const r = 38;
  const cx = 50;
  const cy = 50;
  const circumference = 2 * Math.PI * r;
  const progress = pct * circumference;
  const gap = circumference - progress;

  return (
    <div className="flex flex-col items-center gap-3">
      <div className="relative h-28 w-28">
        <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90">
          {/* Track */}
          <circle
            cx={cx}
            cy={cy}
            r={r}
            fill="none"
            stroke="#30363d"
            strokeWidth="8"
          />
          {/* Progress arc */}
          <circle
            cx={cx}
            cy={cy}
            r={r}
            fill="none"
            stroke={color}
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={`${progress} ${gap}`}
            style={{ transition: 'stroke-dasharray 0.6s ease, stroke 0.4s ease' }}
          />
        </svg>
        {/* Score number in center */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span
            className="font-mono text-2xl font-bold leading-none"
            style={{ color }}
          >
            {(score * 10).toFixed(1)}
          </span>
          <span className="mt-0.5 text-xs text-drift-muted">/ 10</span>
        </div>
      </div>

      <div className="text-center">
        <span
          className="inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wider"
          style={{ background: `${color}22`, color }}
        >
          {SEVERITY_LABEL[severity] ?? severity}
        </span>
      </div>
    </div>
  );
}
