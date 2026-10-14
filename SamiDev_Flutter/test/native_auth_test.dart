import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:samidev/runtime/api.dart';
import 'package:samidev/runtime/native_auth.dart';
import 'package:samidev/runtime/policy.dart';

import 'session_test.dart' show MemoryVault;

void main() {
  test(
    'native HTTP auth persists cookie only, restores session and clears expiry',
    () async {
      final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
      final vault = MemoryVault();
      final policy = RuntimePolicy(
        'http://127.0.0.1:${server.port}',
        allowLocalDevelopment: true,
      );
      final api = PlatformApi(policy, vault), calls = <String>[];
      final auth = NativeAuth(api);
      var expires = false, reject = false;
      var expiredStatus = 401;
      server.listen((request) async {
        calls.add(request.uri.path);
        final body = await request
            .cast<List<int>>()
            .transform(utf8.decoder)
            .join();
        request.response.headers.contentType = ContentType.json;
        if (request.uri.path.startsWith('/api/auth/')) {
          final data = jsonDecode(body) as Map;
          expect(data['username'], 'native_player');
          expect(data['password'], 'Native-password-123');
          if (request.uri.path.endsWith('register')) {
            expect(data['displayName'], 'سامي');
          }
          if (reject) {
            request.response.statusCode = 401;
            request.response.write(
              '{"ok":false,"message":"اسم المستخدم أو كلمة المرور غير صحيحة"}',
            );
          } else {
            request.response.cookies.add(
              Cookie('samidev_session', 'N' * 43)..httpOnly = true,
            );
            request.response.write(
              '{"ok":true,"user":{"id":"native-player","role":"user"}}',
            );
          }
        } else {
          expect(
            request.headers.value('Cookie'),
            'samidev_session=${'N' * 43}',
          );
          request.response.statusCode = expires ? expiredStatus : 200;
          request.response.write(
            expires
                ? '{"ok":false}'
                : '{"ok":true,"user":{"id":"native-player"}}',
          );
        }
        await request.response.close();
      });
      try {
        expect(await auth.restore(), isNull);
        expect(calls, isEmpty);
        await auth.submit(
          register: true,
          username: ' native_player ',
          password: 'Native-password-123',
          displayName: ' سامي ',
        );
        expect(vault.data.values.single, 'N' * 43);
        expect(vault.data.toString(), isNot(contains('Native-password-123')));
        final restoredApi = PlatformApi(policy, vault);
        try {
          await restoredApi.restore();
          expect(
            (await NativeAuth(restoredApi).restore())?['id'],
            'native-player',
          );
        } finally {
          restoredApi.close();
        }
        await auth.submit(
          register: false,
          username: 'native_player',
          password: 'Native-password-123',
        );
        expires = true;
        expect(await auth.restore(), isNull);
        expect(api.signedIn, isFalse);
        expect(vault.data, isEmpty);
        await auth.submit(
          register: false,
          username: 'native_player',
          password: 'Native-password-123',
        );
        expiredStatus = 403;
        expect(await auth.restore(), isNull);
        expect(api.signedIn, isFalse);
        reject = true;
        await expectLater(
          auth.submit(
            register: false,
            username: 'native_player',
            password: 'Native-password-123',
          ),
          throwsA(
            isA<AuthFailure>().having(
              (e) => e.message,
              'message',
              contains('غير صحيحة'),
            ),
          ),
        );
        expect(api.signedIn, isFalse);
      } finally {
        api.close();
        await server.close(force: true);
      }
    },
  );
}
