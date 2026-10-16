Google web authentication uses Firebase 12.4.0, bundled locally with esbuild.
Rebuild from this directory with `npm ci && node build.mjs`.
The upstream Apache license notices are retained in the generated bundle.

Enable Google in Firebase Authentication and add the site's hostname under
Authentication / Settings / Authorized domains. The web popup uses the project's
standard `<projectId>.firebaseapp.com` auth domain. No OAuth secret goes to clients.

Native Google uses `google_sign_in` (the system account picker, not a WebView).
Set the public OAuth IDs on the server:
- `SAMIDEV_GOOGLE_WEB_CLIENT_ID`: Web client ID from the same Firebase project.
- `SAMIDEV_GOOGLE_IOS_CLIENT_ID`: iOS client ID matching the bundle identifier.
Register Android package name and signing SHA-1/SHA-256 in Firebase. For iOS,
add the iOS OAuth client's reversed ID to Runner's CFBundleURLTypes URL schemes
(or supply GoogleService-Info.plist and register its REVERSED_CLIENT_ID). Rebuild
and test on devices after this platform configuration. These IDs are public;
never distribute a client secret or service-account key.

Firebase ID tokens from either flow are verified by the existing Admin SDK on
our backend. New identities choose a username and can upgrade the guest in one
transaction; an existing identity opens its own profile, without merging guests.
Popup cancellation and failures preserve the guest. Web provider tokens are kept
in memory only, then cleared after the server establishes its HttpOnly session.
