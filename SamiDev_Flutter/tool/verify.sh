#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 ../SamiDev_Platform/tools/refresh_integrity.py
python3 tool/sync_assets.py
flutter pub get
python3 tool/test_play_preflight.py
flutter analyze --no-pub --no-fatal-infos
flutter test
flutter build apk --debug --dart-define=SAMIDEV_SERVER_URL="${SAMIDEV_SERVER_URL:?Set your HTTPS backend origin}"
