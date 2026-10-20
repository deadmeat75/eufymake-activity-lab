# EufyMake Activity Lab v0.3.0

Adds the verified observational decoding to the existing Activity Lab recorder. Your recordings, notes, labels, capture settings and database stay in place.

- Independent Standard/Mini/Rotary bed and accessory codes, report times, raw replies and unknown-code visibility.
- Deduplicated detection descriptions and timestamp-aware historical messages; no false installations after reconnect.
- Print elapsed/remaining time, separate snapshot/maintenance progress, and stale/idle progress handling.
- Post-maintenance state residence is not continuous cleaning time.
- A fresh no-detection warning asks you to check the bed and locking latch. Zero detection does not establish whether the bed is absent or simply unlocked.
- Waste fullness uses a growing red bar, with the remaining-capacity figure preserved.
- Existing saved history and larger retention limits are preserved; numeric serial-number keys are redacted for new records.

## Update

Export JSON and back up Home Assistant. Update EufyMake Activity Lab to v0.3.0 through HACS, restart Home Assistant manually when convenient, and fully refresh the E1 Lab browser. Keep the existing integration entry and its database directory. The monitor has a separate version; this release does not modify it.

The complete eufymake_activity_lab.zip asset is available for manual installation. No partial YAML or credential changes are required.

## Validation and limits

35 standalone Python tests and both jsdom UI suites cover interpretation, persistence, privacy, capture, reconnects, history, UTC/Pacific/DST display, settings and annotations. The workflow reruns these checks before publishing. Real HA installation of this update, physical iPad rendering and a live rotary swap still require hardware validation. The 13/0 wording and protocol-wide reply semantics remain inferred/unknown. Existing redaction means this is not a full packet capture. No printer controls, automatic notifications, camera or fragment reassembly are introduced.
