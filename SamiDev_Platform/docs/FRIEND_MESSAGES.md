# Friends and private messages

The friends tab contains friends, conversations, requests, add-by-username and a seven-day invitation link. A new link replaces the previous link. Opening a link asks the signed-in user to send a request; visiting it never accepts friendship automatically. Desktop notifications open the conversations view from the toolbar. Phone navigation opens the same workspace with nested conversation/request/add screens. No game/table invitation behavior was added.

Messages require friendship and no block in either direction. Text is limited to 2,000 characters; each conversation keeps the latest 500 messages. Idempotency uses the sender and client message ID within the retained history. Read markers are monotonic, and per-friend mute is stored on the server. PostgreSQL persists histories, read/mute state, invitation hashes and registered push devices. Account deletion removes all of these records, including conversations containing the deleted account. Direct messages are not end-to-end encrypted. Blocking/removing friendship prevents future history access and messages.

Personal SSE uses its own Redis channel namespace, bounded queues, periodic repair and session revalidation. Events carry IDs, never message bodies. The client fetches content through authorized endpoints. Website banners last 5.5 seconds and dismiss upwards with touch or mouse; muted conversations remain visible without banners. Flutter uses a foreground banner and the existing friends workspace, without opening a second personal SSE connection in its WebView.

## Native notifications activation

No Firebase project configuration for Plazr was supplied to this workspace. Push is **disabled by default**, and successful APK compilation is not a device delivery test.

1. In the existing Firebase project, register the exact Android package `com.samidev.platform`. Keep any current authentication project; do not create a conflicting identity project. Obtain its public app ID, project ID, public API key and messaging sender ID.
2. Configure server environment (not committed secret files):
   - `SAMIDEV_FIREBASE_PROJECT_ID`
   - `SAMIDEV_FIREBASE_API_KEY` (public Firebase app configuration)
   - `SAMIDEV_FIREBASE_MESSAGING_SENDER_ID`
   - `SAMIDEV_FIREBASE_ANDROID_APP_ID`
   - `SAMIDEV_FIREBASE_IOS_APP_ID` if enabling iOS
   - Server-only Application Default Credentials for the **same project**, via the deployment's existing secure credential binding or `GOOGLE_APPLICATION_CREDENTIALS`. Grant the FCM sending permission and enable the FCM API. Never bundle service-account JSON in Flutter, the website or Git.
   - Set `SAMIDEV_PUSH_ENABLED=1` only after this configuration is ready.
3. Supply the same four public Android Firebase values above as environment variables **during the Flutter Android build**, too. Gradle generates native `google_app_id`, `google_api_key`, `gcm_defaultSenderId` and `project_id` resources; these are public app configuration and contain no server credential. These native resources are required for FCM reception after Android process death. A build made without them cannot be described as configured for outside-app delivery. Build/install the updated app. In Friends choose **تفعيل إشعارات الهاتف** and grant the OS notification permission. FCM initialization/registration in the social application requires opt-in; automatic messaging initialization and default data collection are disabled. Native Firebase core may read the public build configuration at process startup, but this does not enable automatic FCM registration. The local children's experience never creates the social notification service.
4. Verify on a real Android device: foreground, background, process terminated, permission denied, friend muted, logout/session revoked, and tap-to-open. Force-stopped Android apps do not receive notifications until opened again. OS delivery and battery policies can delay notifications.
5. iOS additionally requires Push Notifications and Remote notifications capabilities in the signing target, a matching APNs credential uploaded to Firebase and proper provisioning. Validate on a signed physical device; this Linux environment cannot validate APNs or compile iOS. Do not claim iOS delivery based on Android tests.

FCM uses the current Firebase installation registration API. Device registration is account/session-bound, capped at ten devices per account, and ignored when the session is revoked or the registration is older than 30 days. The server sends a generic lock-screen alert without private text, plus IDs to open the authorized conversation. Push delivery runs in a bounded worker and provider failure does not fail an already-committed message. SSE and persistent inbox repair foreground missed notifications; the in-memory push queue is not a durable guaranteed-delivery outbox. Native push supports private messages and new friendship requests; tapping a request opens the requests view.

## Verification

- `python tests/direct_messages_regression.py`
- `python tests/direct_messages_postgres.py` with disposable `SAMIDEV_TEST_DATABASE_URL` and `SAMIDEV_TEST_REDIS_URL` on loopback.
- `SAMIDEV_PLAYWRIGHT_MODULE=/path/to/playwright-core/index.mjs python tests/friends_browser.py`
- Flutter tests include banner dismissal/timeout and exact private API route permissions.

Regenerate/version platform assets, refresh integrity, then sync Flutter assets before builds. Existing PostgreSQL tables are reused; no destructive migration or changes to game physics/bot permissions are required. A running deployment needs the new backend and web assets together. Pushing GitHub alone does not restart the Windows/Linux server or the Cloudflare tunnel.
