#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 ../SamiDev_Platform/tools/refresh_integrity.py
python3 tool/sync_assets.py
flutter pub get
flutter analyze
flutter test
flutter build apk --debug --dart-define=SAMIDEV_SERVER_URL="${SAMIDEV_SERVER_URL:?Set your HTTPS backend origin}"
