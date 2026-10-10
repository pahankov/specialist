import apiClient from './http';

/** Download a CSV export through the authenticated client (blob).
 *
 * window.open() fails when the auth cookie isn't sent (cross-origin,
 * popup blockers) and shows errors in a dead tab. This carries the
 * Authorization header and toasts real errors instead.
 */
export async function downloadCsv(url: string, filename: string): Promise<void> {
  const resp = await apiClient.get(url, { responseType: 'blob' });
  const blob = new Blob([resp.data], { type: 'text/csv; charset=utf-8' });
  const objectUrl = URL.createObjectURL(blob);
  try {
    const a = document.createElement('a');
    a.href = objectUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
  } finally {
    setTimeout(() => URL.revokeObjectURL(objectUrl), 5000);
  }
}
