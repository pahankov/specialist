import { usePersistentState } from './persistentState'

/**
 * 3-state server-side sort (asc → desc → none), persisted in sessionStorage.
 * Single copy — was duplicated verbatim in ClientsPage/MastersPage.
 */
export function useAdminSort<K extends string>(storageKey: string) {
  const [sortKey, setSortKey] = usePersistentState<K | null>(`${storageKey}.sort`, null)
  const [sortDir, setSortDir] = usePersistentState<'asc' | 'desc'>(`${storageKey}.dir`, 'asc')

  const toggleSort = (key: K) => {
    if (sortKey !== key) {
      setSortKey(key)
      setSortDir('asc')
    } else if (sortDir === 'asc') {
      setSortDir('desc')
    } else {
      setSortKey(null)
      setSortDir('asc')
    }
  }

  const sortArrow = (key: K) => (sortKey !== key ? ' ⇅' : sortDir === 'asc' ? ' ▲' : ' ▼')

  return { sortKey, sortDir, toggleSort, sortArrow }
}
