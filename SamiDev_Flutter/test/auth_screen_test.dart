import 'dart:async';

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

PlatformApi testApi() =>
    PlatformApi(RuntimePolicy('https://auth.example.test'), MemoryVault());

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
  }) {
    calls++;
    registering = register;
    return (pending = Completer<Map<String, dynamic>>()).future;
  }
}

class SignedOutRuntime extends GameRuntime {
  SignedOutRuntime() : super(testApi());
  @override
  Future<void> start() async {}
}

void main() {
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
        await tester.enterText(
          find.byKey(const ValueKey('auth-confirm-password')),
          'different',
        );
        final submit = find.byKey(const ValueKey('auth-submit'));
        await tester.ensureVisible(submit);
        await tester.tap(submit);
        await tester.pumpAndSettle();
        expect(auth.calls, 0);
        expect(find.text('كلمتا المرور غير متطابقتين'), findsOneWidget);
        await tester.enterText(
          find.byKey(const ValueKey('auth-password')),
          'Native-password-123',
        );
        await tester.enterText(
          find.byKey(const ValueKey('auth-confirm-password')),
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
