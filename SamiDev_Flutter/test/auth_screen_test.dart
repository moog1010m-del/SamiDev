import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'package:samidev/main.dart';
import 'package:samidev/runtime/api.dart';
import 'package:samidev/runtime/game_runtime.dart';
import 'package:samidev/runtime/native_auth.dart';
import 'package:samidev/runtime/policy.dart';
import 'package:samidev/ui/auth_screen.dart';

import 'session_test.dart' show MemoryVault;

class ConfigApi extends PlatformApi {
  ConfigApi()
    : super(RuntimePolicy('https://auth.example.test'), MemoryVault());
  @override
  Future<ApiResponse> request(
    String method,
    String path, {
    String? query,
    List<int>? body,
  }) async {
    if (path == '/api/auth/config') {
      return ApiResponse(
        200,
        'application/json',
        Uint8List.fromList(utf8.encode('{"provider":"local"}')),
      );
    }
    throw StateError('Unexpected request: $path');
  }
}

PlatformApi testApi() => ConfigApi();

class FakeAuth extends NativeAuth {
  FakeAuth() : super(testApi());
  int calls = 0;
  bool? registering;
  Completer<Map<String, dynamic>>? pending;
  @override
  Future<Map<String, dynamic>> submit({
    required bool register,
    required String username,
    required String password,
    String displayName = '',
    String email = '',
  }) {
    calls++;
    registering = register;
    return (pending = Completer<Map<String, dynamic>>()).future;
  }
}

class FakeFirebaseAuth extends FakeAuth {
  bool identity = false;
  int finishes = 0, resets = 0, resends = 0;
  @override
  bool get usesFirebase => true;
  @override
  bool get hasPendingIdentity => identity;
  @override
  void clearPending() {
    identity = false;
  }

  @override
  Future<void> resetPassword(String email) async {
    resets++;
  }

  @override
  Future<void> resendVerification() async {
    resends++;
  }

  @override
  Future<Map<String, dynamic>> finishPending({
    String username = '',
    String displayName = '',
  }) async {
    finishes++;
    expect(username, 'native_player');
    identity = false;
    return {'id': 'native-player'};
  }
}

class SignedOutRuntime extends GameRuntime {
  SignedOutRuntime() : super(testApi());
  @override
  Future<void> start() async {}
}

void main() {
  testWidgets(
    'native Firebase verification keeps the form usable after a mail failure',
    (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final auth = FakeFirebaseAuth();
      addTearDown(auth.api.close);
      Map<String, dynamic>? user;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: AuthScreen(
              auth: auth,
              onAuthenticated: (value) async {
                user = value;
              },
            ),
          ),
        ),
      );
      expect(find.text('الدخول بالطريقة القديمة مؤقتًا'), findsNothing);
      expect(find.byKey(const ValueKey('auth-legacy-username')), findsNothing);
      await tester.tap(find.text('حساب جديد'));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const ValueKey('auth-email')),
        'player@example.test',
      );
      await tester.enterText(
        find.byKey(const ValueKey('auth-username')),
        'native_player',
      );
      await tester.enterText(
        find.byKey(const ValueKey('auth-password')),
        'Native-password-123',
      );
      expect(find.byKey(const ValueKey('auth-display-name')),findsNothing);
      expect(find.byKey(const ValueKey('auth-confirm-password')),findsNothing);
      final submit = find.byKey(const ValueKey('auth-submit'));
      await tester.ensureVisible(submit);
      await tester.tap(submit);
      await tester.pump();
      auth.identity = true;
      auth.pending!.completeError(
        const AuthFailure(
          'تعذر إرسال رسالة التوثيق',
          code: 'EMAIL_NOT_VERIFIED',
        ),
      );
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('auth-password')), findsNothing);
      expect(find.byType(WebViewWidget), findsNothing);
      final resend = find.text('إعادة إرسال رسالة التوثيق');
      await tester.ensureVisible(resend);
      await tester.tap(resend);
      await tester.pumpAndSettle();
      expect(auth.resends, 1);
      await tester.ensureVisible(submit);
      await tester.tap(submit);
      await tester.pumpAndSettle();
      expect(auth.finishes, 1);
      expect(user?['id'], 'native-player');
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'signed-out application renders native auth without any WebView',
    (tester) async {
      final runtime = SignedOutRuntime();
      await tester.pumpWidget(
        MaterialApp(home: PlatformScreen(runtimeFactory: () => runtime)),
      );
      await tester.pumpAndSettle();
      expect(find.byType(AuthScreen), findsOneWidget);
      expect(find.byType(WebViewWidget), findsNothing);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      await tester.pumpAndSettle();
    },
  );
  for (final brightness in Brightness.values) {
    testWidgets(
      'native form validates, locks requests and handles retry in $brightness',
      (tester) async {
        tester.view.physicalSize = const Size(360, 640);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        final auth = FakeAuth();
        addTearDown(auth.api.close);
        Map<String, dynamic>? signedIn;
        await tester.pumpWidget(
          MaterialApp(
            theme: ThemeData(brightness: brightness),
            home: Scaffold(
              body: Directionality(
                textDirection: TextDirection.rtl,
                child: AuthScreen(
                  auth: auth,
                  onAuthenticated: (user) async {
                    signedIn = user;
                  },
                ),
              ),
            ),
          ),
        );
        await tester.tap(find.text('حساب جديد'));
        await tester.pumpAndSettle();
        await tester.enterText(
          find.byKey(const ValueKey('auth-username')),
          'native_player',
        );
        await tester.enterText(
          find.byKey(const ValueKey('auth-password')),
          'short',
        );
        final submit = find.byKey(const ValueKey('auth-submit'));
        await tester.ensureVisible(submit);
        await tester.tap(submit);
        await tester.pumpAndSettle();
        expect(auth.calls, 0);
        expect(find.text('كلمة المرور يجب ألا تقل عن ١٥ حرفًا'), findsOneWidget);
        expect(find.byKey(const ValueKey('auth-display-name')),findsNothing);
        expect(find.byKey(const ValueKey('auth-confirm-password')),findsNothing);
        await tester.enterText(
          find.byKey(const ValueKey('auth-password')),
          'Native-password-123',
        );
        await tester.ensureVisible(submit);
        await tester.tap(submit);
        await tester.pump();
        expect(auth.calls, 1);
        expect(auth.registering, isTrue);
        expect(tester.widget<FilledButton>(submit).onPressed, isNull);
        auth.pending!.completeError(
          const AuthFailure('اسم المستخدم مستخدم بالفعل'),
        );
        await tester.pumpAndSettle();
        expect(find.text('اسم المستخدم مستخدم بالفعل'), findsOneWidget);
        await tester.ensureVisible(find.text('تسجيل الدخول'));
        await tester.tap(find.text('تسجيل الدخول'));
        await tester.pumpAndSettle();
        expect(
          find.byKey(const ValueKey('auth-confirm-password')),
          findsNothing,
        );
        await tester.enterText(
          find.byKey(const ValueKey('auth-username')),
          'native_player',
        );
        await tester.enterText(
          find.byKey(const ValueKey('auth-password')),
          'Native-password-123',
        );
        await tester.ensureVisible(submit);
        await tester.tap(submit);
        await tester.pump();
        auth.pending!.complete({'id': 'native-player'});
        await tester.pumpAndSettle();
        expect(auth.registering, isFalse);
        expect(signedIn?['id'], 'native-player');
        expect(
          tester
              .widget<TextFormField>(
                find.byKey(const ValueKey('auth-password')),
              )
              .controller!
              .text,
          isEmpty,
        );
        expect(tester.takeException(), isNull);
      },
    );
  }
}
