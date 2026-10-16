import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:samidev/runtime/api.dart';
import 'package:samidev/runtime/firebase_client.dart';
import 'package:samidev/runtime/native_auth.dart';
import 'package:samidev/runtime/policy.dart';

import 'firebase_auth_test.dart' show GoogleFixtureClient;
import 'session_test.dart' show MemoryVault;

void main() {
  test(
    'Google exchanges Firebase token and links guest after username setup',
    () async {
      final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
      final api = PlatformApi(
        RuntimePolicy(
          'http://127.0.0.1:${server.port}',
          allowLocalDevelopment: true,
        ),
        MemoryVault(),
      );
      final auth = NativeAuth(
        api,
        linkGuest: true,
        googleTokenProvider: () async => 'google-provider-id',
      );
      var exchanges = 0, idp = 0;
      server.listen((request) async {
        final raw = await utf8.decoder.bind(request).join();
        final body = raw.isEmpty
            ? <String, dynamic>{}
            : request.headers.contentType?.mimeType ==
                  'application/x-www-form-urlencoded'
            ? Uri.splitQueryString(raw)
            : jsonDecode(raw) as Map<String, dynamic>;
        request.response.headers.contentType = ContentType.json;
        Map<String, dynamic> result = {};
        switch (request.uri.path) {
          case '/api/auth/config':
            result = {
              'provider': 'firebase',
              'apiKey': 'public-fixture',
              'projectId': 'google-project',
            };
          case '/v1/accounts:signInWithIdp':
            idp++;
            expect(Uri.splitQueryString(body['postBody']), {
              'providerId': 'google.com',
              'id_token': 'google-provider-id',
            });
            expect(
              body['requestUri'],
              'https://google-project.firebaseapp.com',
            );
            expect(request.headers.value('Cookie'), isNull);
            result = {
              'idToken': 'firebase-id',
              'refreshToken': 'firebase-refresh',
            };
          case '/v1/token':
            result = {
              'id_token': 'firebase-fresh',
              'refresh_token': 'firebase-refresh',
            };
          case '/api/auth/firebase':
            exchanges++;
            expect(body['idToken'], 'firebase-fresh');
            if (exchanges == 1) {
              expect(body['linkGuest'], false);
              request.response.statusCode = 409;
              result = {
                'ok': false,
                'error': 'PROFILE_SETUP_REQUIRED',
                'message': 'اختر اسمًا',
              };
            } else {
              expect(body['linkGuest'], true);
              expect(body['username'], 'google_player');
              request.response.cookies.add(
                Cookie('samidev_session', 'S' * 43)..httpOnly = true,
              );
              result = {
                'ok': true,
                'user': {'id': 'preserved-guest', 'username': 'google_player'},
              };
            }
          default:
            fail('Unexpected request ${request.uri}');
        }
        request.response.write(jsonEncode(result));
        await request.response.close();
      });
      try {
        await auth.prepare();
        api.firebase!.close();
        api.firebase = FirebaseClient(
          'public-fixture',
          httpClient: GoogleFixtureClient(server.port),
        );
        await expectLater(
          auth.signInGoogle(),
          throwsA(
            isA<AuthFailure>().having(
              (e) => e.code,
              'code',
              'PROFILE_SETUP_REQUIRED',
            ),
          ),
        );
        expect(auth.hasPendingIdentity, true);
        expect(
          (await auth.finishPending(username: 'google_player'))['id'],
          'preserved-guest',
        );
        expect(idp, 1);
        expect(exchanges, 2);
        expect(auth.hasPendingIdentity, false);
        // Sensitive-action proof does not exchange or switch the app account.
        final proof=await auth.reauthenticate(google:true,email:'unused@example.test');
        expect(proof,'firebase-id');expect(exchanges,2);expect(idp,2);
        expect(auth.hasPendingIdentity,false);
      } finally {
        api.firebase?.close();
        api.close();
        await server.close(force: true);
      }
    },
  );
}
