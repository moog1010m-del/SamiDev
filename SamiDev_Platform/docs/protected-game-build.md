# Protected game distribution

From the repository root:

```sh
npm ci --ignore-scripts --prefix SamiDev_Platform/tools/js-protection
python SamiDev_Platform/tools/package_game_release.py
```

Output: `SamiDev_Platform/build/plazr-protected-games.zip` and SHA-256 sidecar.
GitHub Actions > Build protected games > Run workflow runs the same command and
retains these two artifacts for seven days. It does not deploy or publish.

The pinned Terser + JavaScript Obfuscator realtime profile applies local name
mangling, audited internal property renaming and seeded identifier obfuscation.
It preserves public bridges and reflected names. Source
maps are excluded. Original source files, atlas UVs and image bytes stay unchanged.
Integrity indexes, worker caches and build identifiers are regenerated from the
protected output. Packaging requires integrity and four-game runtime checks.
The packaging command also compares a protected pool shot against an original
shot on the same host and fails if it exceeds three times the baseline (100ms
minimum budget). This is a local regression gate, not a device frame-rate claim.

The earlier heavy profile remains available through `protect_game_release.py`,
but this packaging command deliberately excludes runtime string decoding,
numeric expression expansion and control-flow flattening from game engines.
Local native pool testing found the heavy profile took about 94.6 seconds for a
shot versus 0.325 seconds on original code. Do not ship that profile based on
integrity checks alone. Measure the realtime profile on target phones before
production rollout. No mobile graphical performance validation is implied.

The current engines are already bundled JavaScript. esbuild rebundling is not
needed. Binaryen/wasm-opt, wasm-tools and wasm-bindgen are not applied: there is no
Rust/WASM engine in this game tree. They do not turn arbitrary JS into a protected
WASM engine. Revisit those tools only if a real WASM module is introduced.

Unpack into a separate deployment directory and set backend `SAMIDEV_GAME_DIR`
to that directory. The backend and embedded Flutter games must use the SAME
protected release bytes, because engine hashes participate in the runtime
contract. Sync Flutter with `python SamiDev_Flutter/tool/sync_assets.py --web-root
<unpacked-directory>` before its build. Android `tool/build_play.py` already
builds and syncs a protected release automatically. The iOS Codemagic workflow
needs this preparation step before Flutter compilation; the workflow in this
file does not modify Codemagic settings.

Keep `protected-game-protection-report.json` private and outside the served
directory; it contains the reproducible release seed. It is excluded from the ZIP
and uploaded artifacts. Obfuscation increases reverse-engineering effort; it is
not encryption, and does not replace server authority or protect client secrets.
