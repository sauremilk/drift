# Agent-Auftrag

## Ziel

> Architektonische Erosion in Python-Codebases erkennen und handlungsfähige Empfehlungen geben

Kategorie: **utility**

## Constraints (automatisch generiert)

Die folgenden Anforderungen MÜSSEN bei der Implementierung eingehalten werden.
Nach jedem Modul / jeder Funktion stoppen und auf Validierung warten.

- [🔴 CRITICAL] **persist-survive-restart**: Application state must be persisted to durable storage; in-memory-only state is insufficient.
  Signal: `exception_contract_drift`
- [🟡 HIGH] **persist-concurrent-safety**: Concurrent write access must use transactions or locking to prevent data races and lost updates.
  Signal: `exception_contract_drift`
- [🟡 HIGH] **persist-input-integrity**: Input validation must occur before persistence; malformed data must not corrupt stored state.
  Signal: `guard_clause_deficit`
- [🔴 CRITICAL] **sec-no-plaintext-secrets**: Passwords and sensitive credentials must be hashed or encrypted; plaintext storage is forbidden.
  Signal: `hardcoded_secret_candidate`
- [🟡 HIGH] **sec-input-validation**: All user inputs must be validated and sanitized before processing to prevent injection attacks.
  Signal: `guard_clause_deficit`
- [🟡 HIGH] **sec-external-data-validation**: Data from external sources must be validated for schema conformance and integrity before use.
  Signal: `guard_clause_deficit`
- [🟢 MEDIUM] **err-user-friendly-messages**: Exceptions must be caught and translated to user-facing messages; raw tracebacks must not leak.
  Signal: `broad_exception_monoculture`
- [🟡 HIGH] **err-empty-input-resilience**: Empty or null inputs must be handled gracefully without causing unhandled exceptions or crashes.
  Signal: `guard_clause_deficit`
- [🟡 HIGH] **err-network-data-safety**: Network failures must be caught; partial writes must be rolled back or retried to prevent silent data loss.
  Signal: `broad_exception_monoculture`
- [🟢 MEDIUM] **ext-python**: Support for Python functionality
  Signal: `guard_clause_deficit`
- [🟢 MEDIUM] **ext-architektonische**: Support for Architektonische functionality
  Signal: `guard_clause_deficit`
- [🟢 MEDIUM] **ext-codebases**: Support for Codebases functionality
  Signal: `guard_clause_deficit`
- [🟢 MEDIUM] **ext-erosion**: Support for Erosion functionality
  Signal: `guard_clause_deficit`
- [🟢 MEDIUM] **ext-empfehlungen**: Support for Empfehlungen functionality
  Signal: `guard_clause_deficit`

## Validierung

Nach jeder Änderung wird `drift intent --phase 4` ausgeführt.
Der Commit ist erst erlaubt, wenn alle Contracts den Status `fulfilled` haben.

## Ablauf

1. Implementiere die nächste Funktion / das nächste Modul
2. Stoppe und warte auf `drift intent --phase 4`
3. Behebe alle `violated`-Contracts
4. Wiederhole bis alle Contracts `fulfilled` sind
