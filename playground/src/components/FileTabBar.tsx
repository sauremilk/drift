interface FileTabBarProps {
  files: Record<string, string>;
  activeFile: string;
  onSelectFile: (name: string) => void;
  onAddFile: () => void;
  onRemoveFile: (name: string) => void;
}

const MAX_TABS = 5;

export function FileTabBar({
  files,
  activeFile,
  onSelectFile,
  onAddFile,
  onRemoveFile,
}: FileTabBarProps) {
  const fileNames = Object.keys(files);
  const canAdd = fileNames.length < MAX_TABS;

  return (
    <div className="flex items-center gap-0 overflow-x-auto border-b border-drift-border bg-drift-bg">
      {fileNames.map((name) => {
        const isActive = name === activeFile;
        return (
          <div
            key={name}
            className={`group flex min-w-0 shrink-0 cursor-pointer items-center gap-1.5 border-b-2 px-3 py-2 text-sm transition-colors ${
              isActive
                ? 'border-drift-accent bg-drift-panel text-drift-text'
                : 'border-transparent text-drift-muted hover:bg-drift-panel/60 hover:text-drift-text'
            }`}
            onClick={() => onSelectFile(name)}
          >
            <span className="max-w-[120px] truncate font-mono text-xs">{name}</span>
            {fileNames.length > 1 && (
              <button
                className="ml-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded text-drift-muted opacity-0 transition-opacity hover:bg-drift-border hover:text-drift-text group-hover:opacity-100"
                onClick={(e) => {
                  e.stopPropagation();
                  onRemoveFile(name);
                }}
                title={`Close ${name}`}
              >
                <svg viewBox="0 0 10 10" className="h-2.5 w-2.5" fill="currentColor">
                  <path d="M1 1l8 8M9 1l-8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" fill="none" />
                </svg>
              </button>
            )}
          </div>
        );
      })}

      {canAdd && (
        <button
          onClick={onAddFile}
          title="Add new file (max 5)"
          className="flex h-9 w-9 shrink-0 items-center justify-center text-drift-muted transition-colors hover:bg-drift-panel/60 hover:text-drift-text"
        >
          <svg viewBox="0 0 14 14" className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
            <path d="M7 2v10M2 7h10" />
          </svg>
        </button>
      )}
    </div>
  );
}
