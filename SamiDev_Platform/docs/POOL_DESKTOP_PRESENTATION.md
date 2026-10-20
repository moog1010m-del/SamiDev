# Desktop pool presentation

`game/pool-presentation.js` is a browser presentation adapter. The original client/authoritative `games/pool/main.js` and its physics coordinates are unchanged.

The adapter activates only on a non-touch desktop web surface at least 900 × 500 CSS pixels and wider than its height by 5%. Phones, native Flutter WebViews and narrow windows retain the original portrait scene. `poolLayout=portrait` in the game URL disables the adapter for comparison or rollback.

Only board drawing (table texture, balls, cue, aim layer and board effects) receives a 90-degree visual transform. Names, dialogs and controls remain upright. The original control animator still owns visibility and transitions; its visible positions use the side gutters. Collected balls use a footer and retain the active player's side, with two rows when needed.

DOM pointer coordinates first enter the existing canvas coordinate system, then inverse-transform only for board interactions. A pointer keeps its board/control route until release/cancellation, so dragging beyond the cloth cannot switch coordinate systems. Open dialogs retain normal coordinates. The native touch bridge still performs its original bottom-left Y conversion. No shot angle, physical position, velocity or network packet is rotated.

The board texture is rebuilt only when the surface geometry/active layout changes or the native theme requests it. Render-context hooks are restored in `finally` blocks and never mutate a physics body or the board nodes' native world transforms. The adapter relies on the existing scene renderer's row-major Matrix3 format and must be revalidated after a native engine update.

## Collision sound adjustment

The shared browser audio bridge applies a policy only to Pool `ball1..3.m4a` and `ball_soft1..3.m4a`: hard collision gain ×0.40, soft collision gain ×0.20, suppress the weakest soft-contact requests below 0.42 native gain, and limit the family to one playback every 45 ms. This removes chatter from tiny contacts and limits bursts. It does not replace sound recordings or change collisions. Cue/rack/rail/pocket effects, other games, and existing mute/suspend controls retain their behavior.

## Verification

- `node tests/pool_audio_policy.js`: gain, low-contact gate, burst limiting, mute/suspend and other-game isolation.
- `node tests/pool_desktop_presentation_browser.mjs`: real mouse ball placement, aim, power-meter shot, reversible mapping and resize preservation at 1366/1024/390 widths.
- `node tests/pool_pocketed_layout_browser.mjs`: both player views, all collection sizes, restored physics, unclipped and non-overlapping items.
- `node tests/pool_angle_adapter.js`: authoritative engine angle/shot contracts and a real winning pot.

Browser tests require Playwright/Chromium and loopback networking, with `SAMIDEV_PLAYWRIGHT_MODULE` available where the package is installed outside the test project. Regenerate the UI build/cache/integrity contract and sync Flutter assets after edits. No database migration or bot permission change is involved.
