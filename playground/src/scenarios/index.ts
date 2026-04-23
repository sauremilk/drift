import { godClassScenario } from './god-class';
import { circularDepsScenario } from './circular-deps';
import { deadCodeScenario } from './dead-code';
import { cleanArchScenario } from './clean-arch';

export interface Scenario {
  /** Unique identifier used in URL state. */
  id: string;
  /** Short display label for the picker button. */
  label: string;
  /** One-sentence description shown in the picker tooltip / header. */
  description: string;
  /** Map of filename → Python source content. */
  files: Record<string, string>;
}

export const SCENARIOS: Scenario[] = [
  godClassScenario,
  circularDepsScenario,
  deadCodeScenario,
  cleanArchScenario,
];

export const DEFAULT_SCENARIO_ID = godClassScenario.id;

/** Convenience lookup by id. */
export function getScenario(id: string): Scenario | undefined {
  return SCENARIOS.find((s) => s.id === id);
}
