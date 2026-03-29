/**
 * Shared UTC date utilities.
 * Server returns naive ISO timestamps (no timezone suffix) that are UTC.
 * JavaScript's `new Date("2026-03-29T12:00:00")` treats these as local time,
 * so we must append 'Z' to interpret them correctly as UTC.
 */

/** Parse a server ISO timestamp as UTC. */
export function parseUTC(iso) {
  if (!iso) return null
  return new Date(iso.endsWith('Z') ? iso : iso + 'Z')
}

/** Format a server ISO timestamp as a locale string. */
export function formatUTC(iso) {
  const d = parseUTC(iso)
  return d ? d.toLocaleString() : ''
}

/** Return a human-readable relative time string from a server ISO timestamp. */
export function relativeTime(iso) {
  const date = parseUTC(iso)
  if (!date) return ''
  const now = new Date()
  const diffMs = now - date
  const diffSec = Math.floor(diffMs / 1000)
  if (diffSec < 10) return 'just now'
  if (diffSec < 60) return `${diffSec}s ago`
  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin}m ago`
  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr}h ago`
  const diffDay = Math.floor(diffHr / 24)
  if (diffDay < 7) return `${diffDay}d ago`
  return date.toLocaleDateString()
}
