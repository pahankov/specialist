/** Explicit-entry gate for the inactive-master draft shell.
 *
 *  The old guard relied on React Router location.state, which survives a
 *  reload: an inactive client who once opened the draft (or restored a phone
 *  tab/PWA session) could land back in the master shell on startup. This flag
 *  deliberately lives only in memory. It is set by «Стать мастером» and the
 *  legacy /cabinet/become-master redirect; a full reload clears it, so a draft
 *  URL is never a valid client landing target.
 */
let masterDraftEntryAllowed = false;

export function allowMasterDraftEntry(): void {
  masterDraftEntryAllowed = true;
}

export function isMasterDraftEntryAllowed(): boolean {
  return masterDraftEntryAllowed;
}

export function clearMasterDraftEntry(): void {
  masterDraftEntryAllowed = false;
}
