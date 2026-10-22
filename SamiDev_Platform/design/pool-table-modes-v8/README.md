# Original and optional large pool table — V8

The original green table with brown rails/gold pocket caps is the default on every device. The current V7 design is preserved separately and becomes a match option, `largeTable=1`, labelled «الطاولة الكبيرة» in the invitation draft, web/local room creation and native app creation sheet. It is available on phones and computers.

The server clamps and stores the option at invitation send, carries it into the room on acceptance, and returns the same value to both seats, spectators and reconnecting clients. An accepting client cannot override the sender's choice. Old invitations/rooms without the field default to the original table.

Online artwork loading waits for authoritative room assignment. A URL hint cannot override the room mode. The visual option is removed before passing settings into the unchanged native rules engine. Local games use the explicitly selected/query mode.

The wide renderer is enabled only for a large-table match. Portrait phones retain the native tall layout and touch controls with the selected artwork; landscape phones and computers use the wide layout. Selection is stable when the device rotates.

## Assets and quality

- Original table and native preview copied byte-for-byte from `../pool-classic-mahogany-v4/backup/`; hashes in `original-assets.json`. This is the old green/brown/gold version, not the earlier blue or red-wood versions.
- Eight current artwork files copied byte-for-byte into `game/images/pool-large/` before restoring the default. Hashes in `large-assets.json`; no full-size asset was recompressed, resized or regenerated.
- The original 433 × 773 quarter/mirroring workflow, UI/ball atlas, native engine, ball radius and physics remain unchanged. Only the store thumbnail is resampled from the restored table.
- Original native sinking and existing pocket VFX remain in both modes. The rejected fixed-duration shrink wrapper is absent.
- Prior source files saved under `before/` for rollback.

## Validation

See `verification.json`. Pool runtime (39 checks), mode/assignment/orientation (11), desktop controls (13), invitation acceptance, authenticated two-seat WebSocket play/reconnect, Flutter mode-selection widget and asset-cache contract passed. Flutter bundle: 769 files; 770 scanned; no findings. Served files, startup build and mobile bundle match.

Actual browser renders are under `proof/`: original/large desktop; original phone; portrait/landscape large phone. Temporary emulation overrides were removed. Invitation screenshots render the exact production draft builder in `invitation-preview.html` with a local-only send stub; no real invitation was sent. The temporary preview server was stopped.
