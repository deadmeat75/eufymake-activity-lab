# Monitor 1.2.0 / Activity Lab 0.4.0 release

## Scope and compatibility

The user authorized committing and publishing Monitor 1.2.0 and Activity Lab 0.4.0 to GitHub. These remain separate existing integrations; install each only when you choose. Home Assistant installation and restart are not performed by publication. Existing entries, entity unique IDs, MQTT authentication, topics, query command/interval, readonly dates, per-printer unit preference, layouts and notes/labels remain. There is no competing integration, control action, camera feature or new third-party runtime dependency. Monitor adds the built-in HA persistent-notification dependency for optional local alerts.

## Approved behavior

- “Ink Supply” replaces “Ink Reserves.” Waste fullness remains 100 minus the existing remaining-capacity sensor. Growing bar: green below 60%, yellow at 60–<80%, red at 80–100%. Raw/native remaining-capacity values are unchanged.
- No-bed warning: “Bed not detected. Make sure a bed is installed and its locking latch is fully closed.” No independent latch sensor is claimed.
- Monitor names missing readings, explains inactive print metrics and missing expiration countdowns, and shows data age/staleness. Existing saved printer dates remain available offline.
- Independent bed/accessory reports remain. Known bed dimensions: Mini 335 × 90 mm / 13.19 × 3.54 in; Standard 335 × 420 mm / 13.19 × 16.54 in. Unknown dimensions are not inferred from job geometry.
- Unknown state/step meanings remain unconfirmed, with copy controls. Existing maintenance/print progress layout is retained; the separately proposed redesign was not approved.
- Last completed print is retained after Idle. Completion requires a fresh 100% report followed by Idle in the same observed connection. An earlier end is explicitly unconfirmed. This is evidence-based classification, not a new machine-control API.
- Estimated finish uses the receipt timestamp plus remaining seconds, only during Printing with a reading no older than 120 seconds. It is hidden during pause, Idle or stale data.
- Connection history, observed maintenance durations, print summaries and reported ink inventory are persisted and bounded. A connection gap clears active contexts, so no duration or completion is invented across that gap. Persistent 13/0 and 13/1 states are not counted as active maintenance.
- Cartridge identity changes are recognized only from explicit identity fields, including returning to a previously used cartridge. Private identities are locally HMAC-hashed; neither raw identities, hashes nor salt appear in public history. Volume/expiration still follow live printer reports. A level increase alone does not claim a replacement.
- Inventory charts retain up to 720 points, at most one regular point per five minutes, plus identity-change markers. Views show the actual available time range; this is not a promise of complete lifetime history.
- Usage estimates assume six 100 mL cartridges and compare fresh boundary inventory readings. Estimates may overlap adjacent activity and miss sub-resolution consumption; they are not exact per-operation accounting. Missing start/end data, observed gaps over 120 seconds, inventory increases or identity changes invalidate estimates. No endpoint sample after an operation starts means usage is unavailable, not zero.
- Job quantity fields from command 1068 are retained with **units unverified**, not labeled mL. Standalone cleaning does not inherit an old job’s quantities.

## Limits and evidence

The available October 27 attachment was read locally: **7,639 events**, ending 2026-10-27 12:14:07 PDT, before the latest print finished. Read-only replay backfilled bounded histories without changing the source file. The separate **7,869-event** export and completion at **12:24:05 PDT**, last elapsed **19m 54s**, 100% about 11 seconds before Idle with 17 seconds remaining, were reported by the user from another analysis; that second file is not present here. Those final values are exercised as synthetic regression cases, not claimed as a local replay of the second file.

Command 1140 occurs once in the available export. It remains an experimental signal with no proven physical-button meaning. Print start method remains **Unknown**. No device/app distinction is exposed without stronger controlled evidence.

Retained ink readings have a minimum of **47.6%**. `ink.remind` appears as 1 in four retained reports, but its meaning/threshold is unverified. The data cannot establish a native 10% threshold. Monitor’s configurable 10% default is explicitly an integration setting. Both percent and estimated mL thresholds have the same numeric value for a 100 mL cartridge.

Maintenance progress associations and post-maintenance wording retain their existing uncertainty. Print/maintenance accounting cannot yet be reconciled to verified mL fields. A later flash clean reportedly left job quantities unchanged; no standalone maintenance quantity decoder is invented.

Physical Home Assistant/printer deployment, real MQTT connectivity, mobile push delivery, physical legacy iPad testing, hassfest and HACS validation have not been performed for this prepared release. The automated HA boundary uses API doubles. No source data, credentials, recordings, databases or private identities belong in release packages.

## Validation and manual upgrade

See MANUAL_INSTALL.md for complete installation and verification steps. Test counts and final package hashes are recorded in VALIDATION_NEXT_RELEASE.md after checks finish.
