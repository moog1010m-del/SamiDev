# Background table notifications

The gateway now sends `game_started` and `game_turn` through Firebase, using the
same opted-in device registrations as friends. It does not depend on the game
WebView or its suspended socket. Android uses the separate `plazr_games` channel.
A turn notification is produced only when ownership changes, expires after 30
seconds, and replaces the previous notification for that table. Only seated
accounts with a current registered session receive notifications.

Deployment requires both the updated backend and a newly built Android app:

- Backend: `SAMIDEV_PUSH_ENABLED=1`, working Firebase Admin credentials, and the
  public Firebase application configuration already used for friend pushes.
- Android build: matching `SAMIDEV_FIREBASE_ANDROID_APP_ID`,
  `SAMIDEV_FIREBASE_PROJECT_ID`, `SAMIDEV_FIREBASE_API_KEY`, and
  `SAMIDEV_FIREBASE_MESSAGING_SENDER_ID`. Build without these resources cannot
  register for push; the app reports that configuration problem rather than
  claiming success.
- User: enable phone notifications in the app and allow Android notifications.
  Check the separate matches/turns notification channel in Android settings.

On a real phone, create a table, switch to another app, let the match begin,
then let the opponent finish a turn. Check each OS notification and tap it to
return to the retained table. Revisions that keep the same owner must not cause
repeated alerts. Test logout and account switching as well. FCM delivery depends
on connectivity and Android notification/battery settings; Android force-stop
prevents normal delivery until the user launches the app again.

An existing retained table opens on a notification tap. If the process has lost
its table context, the app directs the user to their tables rather than joining
an arbitrary room from push data.

Friend conversation content is now a Flutter screen (list, composer, mute,
retry, live updates); the friend directory remains the existing platform view.
The web browser continues using the web conversation UI.
