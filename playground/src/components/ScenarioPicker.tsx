import type { Scenario } from '../scenarios';

interface ScenarioPickerProps {
  scenarios: Scenario[];
  activeId: string;
  onChange: (id: string) => void;
}

export function ScenarioPicker({ scenarios, activeId, onChange }: ScenarioPickerProps) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs font-medium uppercase tracking-wider text-drift-muted">
        Scenario
      </span>
      <div className="flex flex-wrap gap-1.5">
        {scenarios.map((scenario) => {
          const isActive = scenario.id === activeId;
          return (
            <button
              key={scenario.id}
              onClick={() => onChange(scenario.id)}
              title={scenario.description}
              className={`rounded-md border px-3 py-1.5 text-sm font-medium transition-all duration-150 ${
                isActive
                  ? 'border-drift-accent bg-drift-accent/10 text-drift-accent'
                  : 'border-drift-border bg-drift-panel text-drift-text hover:border-drift-accent/50 hover:text-drift-accent'
              }`}
            >
              {scenario.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
