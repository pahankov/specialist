/** Shared API error formatting (single source of truth for toasts/error states).
 *
 * Backend contract: `{ detail: string | string[] | { msg|message } }`
 * (string[] comes from the custom 422 handler: "loc -> msg" items).
 */

interface ErrorItem {
  msg?: string
  message?: string
}

function itemToString(item: unknown): string | null {
  if (typeof item === 'string') return item
  if (typeof item === 'object' && item !== null) {
    const e = item as ErrorItem
    return e.msg ?? e.message ?? null
  }
  return null
}

export function getApiErrorMessage(err: unknown, fallback = 'Ошибка сервера'): string {  if (typeof err === 'string') return err
  if (typeof err !== 'object' || err === null) return fallback

  const response = (err as { response?: { data?: { detail?: unknown; message?: unknown } } }).response
  const data = response?.data
  if (!data) {
    const message = (err as Error).message
    return typeof message === 'string' && message ? message : fallback
  }

  const detail = data.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const parts = detail.map(itemToString).filter((s): s is string => s !== null)
    if (parts.length > 0) return parts.join(', ')
  } else {
    const single = itemToString(detail)
    if (single) return single
  }

  if (typeof data.message === 'string') return data.message
  return fallback
}

/** HTTP status of an axios-shaped error, if present. */
export function getApiErrorStatus(err: unknown): number | undefined {
  if (typeof err !== 'object' || err === null) return undefined
  const status = (err as { response?: { status?: unknown } }).response?.status
  return typeof status === 'number' ? status : undefined
}
