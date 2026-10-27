# EufyMake Activity Lab 0.4.0

- Bookmark retained records and filter bookmarks.
- Select two records to compare captured/redacted fields, including added or missing fields and array elements.
- Start/end named recording sessions with observations, and export retained records for one session only.
- Backfill bounded print, maintenance, connection and ink inventory summaries from retained history on upgrade.
- Preserve completed-print metrics after Idle; keep job quantity units and command-1140 meaning unverified.
- Show ink-supply history, estimated finish time, freshness, known bed dimensions and revised latch guidance.
- Color the growing waste-fill bar green below 60%, yellow below 80%, red at 80% and above.
- Keep normal polling to the latest 300 records. Load older records explicitly and display at most 300 rows per page.
- Preserve the existing SQLite journal, labels, notes, capture settings, event IDs, raw redaction and admin-only interface.

Bookmarks follow ordinary retention limits. Session export includes only retained session events; it cannot recover dropped records. See NEXT_RELEASE.md for upgrade checks and limits.
