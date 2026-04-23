import type { PyodideStatus } from '../utils/pyodide-runner';

interface LoadingOverlayProps {
  status: PyodideStatus;
  onRetry?: () => void;
}

export function LoadingOverlay({ status, onRetry }: LoadingOverlayProps) {
  if (status.state === 'ready') return null;

  const isError = status.state === 'error';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-drift-bg/90 backdrop-blur-sm">
      <div className="flex flex-col items-center gap-6 rounded-xl border border-drift-border bg-drift-panel px-10 py-10 text-center shadow-2xl">
        {isError ? (
          <>
            <div className="flex h-14 w-14 items-center justify-center rounded-full border border-drift-critical/40 bg-drift-critical/10 text-3xl text-drift-critical">
              ✕
            </div>
            <div>
              <p className="text-base font-semibold text-drift-text">
                Failed to load Python runtime
              </p>
              <p className="mt-2 max-w-xs text-sm text-drift-muted">
                {status.message ?? 'An unexpected error occurred while initialising Pyodide.'}
              </p>
            </div>
            {onRetry && (
              <button
                onClick={onRetry}
                className="rounded-md border border-drift-border bg-drift-bg px-5 py-2 text-sm font-medium text-drift-text transition-colors hover:border-drift-accent hover:text-drift-accent"
              >
                Retry
              </button>
            )}
          </>
        ) : (
          <>
            {/* Spinner */}
            <svg
              className="h-12 w-12 animate-spin text-drift-accent"
              viewBox="0 0 24 24"
              fill="none"
            >
              <circle
                className="opacity-20"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="3"
              />
              <path
                className="opacity-90"
                fill="currentColor"
                d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
              />
            </svg>

            <div>
              <p className="text-base font-semibold text-drift-text">
                {status.state === 'loading-runtime'
                  ? 'Loading Python runtime'
                  : status.state === 'installing-drift'
                  ? 'Installing drift-analyzer'
                  : 'Initialising…'}
              </p>
              <p className="mt-1 text-sm text-drift-muted">
                {status.state === 'loading-runtime'
                  ? 'Downloading Pyodide (~20 MB) — first load only'
                  : status.state === 'installing-drift'
                  ? 'Installing drift-analyzer and dependencies'
                  : 'Please wait…'}
              </p>
            </div>

            {/* Subtle step indicator */}
            <div className="flex gap-2">
              {(['loading-runtime', 'installing-drift'] as const).map((step) => (
                <span
                  key={step}
                  className={`h-1.5 w-8 rounded-full transition-colors ${
                    status.state === step
                      ? 'bg-drift-accent'
                      : status.state === 'installing-drift' && step === 'loading-runtime'
                      ? 'bg-drift-accent/40'
                      : 'bg-drift-border'
                  }`}
                />
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
