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

# 0.3.0

- Decode independent bed/accessory codes, raw reply values and timestamps; keep unknown values visible.
- Add read-only interpretations of print, snapshot, maintenance and hardware observations, preserving raw redacted records and user labels.
- Avoid duplicate detection events, old-message state reversions and false installations after reconnect/restart.
- Associate progress with its operation; suppress historical/stale print progress and avoid early completion at 100%.
- Describe post-maintenance duration as state residence, not continuous cleaning.
- Warn to check installation/locking latch on fresh no-detection reports without claiming measured latch position.
- Show waste-tank fullness as a growing red bar, retaining remaining capacity and raw data.
- Retain notes, labels, settings, event IDs and the existing SQLite database. Respect larger saved retention limits at startup.
- Strengthen serial-number redaction, preserve admin-only actions, and retain UTC records with Pacific/DST display.
- No controls, automatic maintenance, camera access or fragmented-frame reassembly are added.

# 0.2.0

- Add safe decoded telemetry and unfamiliar-command capture, with deduplication and sampling.
- Count checksum failures, fragments and malformed or oversized messages.
- Add live telemetry cards, decoded-field details, observation markers and prefilled pair labels.
- Add capture controls and adjustable bounded history.
- Use incremental SQLite storage outside the integration directory.
- Reuse an existing EufyMake monitor's credentials through guided setup.
- Package for HACS installation with independent domain and update path.

# 0.1.0

Local prototype: state/step timeline, notes, labels and exports. Not publicly released.
