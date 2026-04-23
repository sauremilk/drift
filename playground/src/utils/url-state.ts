/**
 * Phase 2 stub — shareable URL state via URL hash encoding.
 *
 * TODO(phase-2): Implement encodeStateToURL / decodeStateFromURL for
 * shareable playground links. Design:
 *   - Serialize files map + active scenario ID as JSON
 *   - Compress with LZ-string (handles large files exceeding raw URL limits)
 *   - Base64url-encode and store in window.location.hash
 *   - On load, decode and restore state before Pyodide init
 *
 * Risk: even LZ-compressed files can exceed browser URL length limits
 * (~8 KB) for large examples; consider a server-side paste service in Phase 3.
 */

export function encodeStateToURL(_files: Record<string, string>): string {
  // Phase 2 stub — not implemented
  return '';
}

export function decodeStateFromURL(): Record<string, string> | null {
  // Phase 2 stub — not implemented
  return null;
}
