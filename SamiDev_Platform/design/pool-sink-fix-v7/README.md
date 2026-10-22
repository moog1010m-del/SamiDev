> Animation update: the user rejected the 260 ms replacement. It was removed from the runtime, web shell, build and mobile bundle. Native ball rendering, movement, lighting and timing are restored; the existing pocket VFX is retained. Corner artwork and aim-geometry fixes remain. The replacement and its test are archived under `rejected-animation/`. The falling-ball recordings below show the rejected version and are historical only. New native animation verification is under `native-animation-restored/`.

# Pocket alignment and fall correction — V7

## Diagnosis

The previous generated corner cushion toe extended into the native pocket opening. The native aim guide also used a rectangular rail approximation. A shot could therefore appear to hit green rubber while the actual ray led through an opening.

After native capture, the ball is excluded from playable ball/rail collisions. Its internal sink force can reverse it toward the cloth before final pocket removal. Displaying that internal trajectory produced the reported visible return.

## Changes

- Refit existing generated cushion material to the actual native jaw polygons. Only 5,237 RGB pixels of the 433 × 773 mirrored quarter changed; alpha and both middle pockets are identical to V6. No new table generation.
- Correct the client aim-distance getter using swept circle contact with existing native rail/pocket-border polygons and the native pocket capture thresholds. No body, collision mask or shot input changes.
- Add a 260 ms render-only fall after `onSunk`. It moves and shrinks the visual receiver into the visible opening, clips it to the opening, and stays hidden until native sink completion. It does not write back to the ball view or physics body.
- Keep the original `main.js`, native UI/ball atlas, ball radius, pocket sensors, collision polygons, scoring, networking and mirrored quarter workflow unchanged. Exact before/after hashes are in `table-verification.json`.
- Include both presentation scripts in the web shell, versioned build manifest, asset cache and Flutter runtime bundle.

## Verification

- `pool_sink_presentation.js`: 9 checks. Actual native middle-pocket path reproduces 78 sinking steps including the internal reversal; the display never returns. Position, velocity, masks, scratch and turn results are unchanged.
- `pool_aim_presentation.js`: three actual native physics cases. Corner opening pots; both adjacent jaw shots hit a rail first. Guide contact is within six native units of the actual first event.
- `pool_runtime.js`: 39 checks, including legal wins and early-eight losses.
- `pool_desktop_controls.js`: 13 checks.
- `asset_cache_build.py`: passed. Flutter synchronized 761 files; 762 scanned, no findings.
- Bright cushion pixels outside native rail polygons, with 1 px edge tolerance: 592 before, 0 after (`jaw-alignment.json`).
- Actual browser shots on localhost: bottom-right corner and lower middle pocket. Screencast frames and timestamps are under `browser-free-corner/` and `browser-middle/`; GIFs are crops of those actual frames, with no synthesized motion. Both descend and disappear without returning to cloth. Cue-ball scratches still transfer the turn and restore ball in hand.
- Real mobile emulation at 390 × 844 confirms the portrait table and corrected corners (`browser-phone.png`). Emulation was removed after checking.

The earlier browser-corner capture stalled before acknowledgement; use `browser-free-corner` for the complete corner-shot recording.

## Native animation restoration validation

Removed the replacement from the served web shell/runtime, cache and mobile bundle. `pool_runtime.js` (39), native aim cases (3) and asset cache passed. Flutter: 760 files; 761 scanned; no findings. The original engine and native UI/ball atlas hashes match the V7 baseline. A foreground local free-pool corner scratch was captured in 54 frames: `native-animation-restored/verified/`. The ball uses the original full-size native movement/clipping; no 260 ms size change or synthetic disappearance remains. This deliberately restores the old sink trajectory too, rather than claiming the original reversal was fixed. The retained pocket VFX file has not changed.
