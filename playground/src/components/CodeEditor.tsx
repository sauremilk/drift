import MonacoEditor, { loader } from '@monaco-editor/react';

// Load Monaco from CDN instead of bundling it — keeps the initial bundle small
loader.config({
  paths: { vs: 'https://cdn.jsdelivr.net/npm/monaco-editor@0.47.0/min/vs' },
});

interface CodeEditorProps {
  value: string;
  onChange: (value: string) => void;
  language?: string;
}

export function CodeEditor({ value, onChange, language = 'python' }: CodeEditorProps) {
  return (
    <div className="h-full w-full overflow-hidden rounded-b-md border border-t-0 border-drift-border">
      <MonacoEditor
        height="100%"
        language={language}
        theme="vs-dark"
        value={value}
        onChange={(v) => onChange(v ?? '')}
        options={{
          fontSize: 13,
          fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace",
          fontLigatures: true,
          lineNumbers: 'on',
          minimap: { enabled: false },
          scrollBeyondLastLine: false,
          wordWrap: 'off',
          renderWhitespace: 'none',
          tabSize: 4,
          insertSpaces: true,
          automaticLayout: true,
          padding: { top: 12, bottom: 12 },
          scrollbar: {
            verticalScrollbarSize: 6,
            horizontalScrollbarSize: 6,
          },
          overviewRulerLanes: 0,
          hideCursorInOverviewRuler: true,
          bracketPairColorization: { enabled: true },
        }}
      />
    </div>
  );
}
