import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:samidev/runtime/api.dart';
import 'package:samidev/runtime/firebase_client.dart';
import 'package:samidev/runtime/native_auth.dart';
import 'package:samidev/runtime/policy.dart';

import 'session_test.dart' show MemoryVault;

// Test-only transport: assert the original Google HTTPS destinations before
// routing to an isolated local HTTP fixture. Production URLs remain fixed.
class GoogleFixtureClient implements HttpClient {
  GoogleFixtureClient(this.port);
  final int port;
  final HttpClient delegate = HttpClient();
  final List<Uri> requested = [];
  @override
  set connectionTimeout(Duration? value) => delegate.connectionTimeout = value;
  @override
  Future<HttpClientRequest> postUrl(Uri url) {
    expect(url.scheme, 'https');
    expect({
      'identitytoolkit.googleapis.com',
      'securetoken.googleapis.com',
    }, contains(url.host));
    requested.add(url);
    return delegate.postUrl(
      Uri.parse('http://127.0.0.1:$port${url.path}?${url.query}'),
    );
  }

  @override
  void close({bool force = false}) => delegate.close(force: force);
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  test('Firebase native lifecycle: verify, retry, local exchange, reset and session outage', () async {
    final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    final vault = MemoryVault();
    final api = PlatformApi(
      RuntimePolicy(
        'http://127.0.0.1:${server.port}',
        allowLocalDevelopment: true,
      ),
      vault,
    );
    final auth = NativeAuth(api,linkGuest:true), transport = GoogleFixtureClient(server.port);
    var verified = false, providerDown = false, mailDown = false;
    var resets = 0, verifies = 0, exchanges = 0;
    server.listen((request) async {
      final raw = await utf8.decoder.bind(request).join();
      final body = raw.isEmpty
          ? <String, dynamic>{}
          : request.headers.contentType?.mimeType ==
                'application/x-www-form-urlencoded'
          ? Uri.splitQueryString(raw)
          : jsonDecode(raw) as Map<String, dynamic>;
      final path = request.uri.path;
      request.response.headers.contentType = ContentType.json;
      var response = <String, dynamic>{};
      if (path == '/api/auth/config') {
        response = {'provider': 'firebase', 'apiKey': 'public-fixture'};
      } else if (path == '/api/auth/guest') {
        request.response.cookies.add(Cookie('samidev_session','G'*43)..httpOnly=true);
        response={'ok':true,'user':{'id':'same-local-player','isGuest':true}};
      } else if (path == '/v1/accounts:signUp' ||
          path == '/v1/accounts:signInWithPassword') {
        expect(body['email'], 'player@example.test');
        expect(body['password'], 'New-password-123456');
        expect(request.headers.value('Cookie'), isNull);
        response = {'idToken': 'google-id', 'refreshToken': 'google-refresh'};
      } else if (path == '/v1/token') {
        expect(
          request.headers.contentType?.mimeType,
          'application/x-www-form-urlencoded',
        );
        expect(body, {
          'grant_type': 'refresh_token',
          'refresh_token': 'google-refresh',
        });
        response = {
          'id_token': 'fresh-google-id',
          'refresh_token': 'google-refresh',
        };
      } else if (path == '/v1/accounts:sendOobCode') {
        if (body['requestType'] == 'VERIFY_EMAIL') {
          verifies++;
          expect(body['idToken'], isNotEmpty);
          if (mailDown) {
            request.response.statusCode = 503;
            response = {
              'error': {'message': 'TEMPORARY_FAILURE'},
            };
          }
        } else {
          resets++;
          expect(body['requestType'], 'PASSWORD_RESET');
          expect(body['email'], 'missing@example.test');
          request.response.statusCode = 400;
          response = {
            'error': {'message': 'EMAIL_NOT_FOUND'},
          };
        }
      } else if (path == '/api/auth/firebase') {
        exchanges++;
        expect(body['idToken'], 'fresh-google-id');
        expect(body['linkGuest'],true);
        expect(request.headers.value('Cookie'),'samidev_session=${'G'*43}');
        expect(body.containsKey('password'), isFalse);
        expect(body.containsKey('refreshToken'), isFalse);
        if (!verified) {
          request.response.statusCode = 403;
          response = {'error': 'EMAIL_NOT_VERIFIED', 'message': 'verify email'};
        } else {
          expect(body['username'], 'new_player');
          request.response.cookies.add(
            Cookie('samidev_session', 'F' * 43)..httpOnly = true,
          );
          response = {
            'ok': true,
            'user': {'id': 'same-local-player'},
          };
        }
      } else if (path == '/api/me') {
        request.response.statusCode = providerDown ? 503 : 200;
        response = providerDown
            ? {'error': 'AUTH_PROVIDER_UNAVAILABLE', 'message': 'try later'}
            : {
                'ok': true,
                'user': {'id': 'same-local-player'},
              };
      } else {
        fail('Unexpected route: $path');
      }
      request.response.write(jsonEncode(response));
      await request.response.close();
    });
    try {
      await auth.prepare();
      expect(auth.usesFirebase, isTrue);
      expect((await auth.guest())['id'],'same-local-player');
      api.firebase!.close();
      api.firebase = FirebaseClient('public-fixture', httpClient: transport);
      mailDown = true;
      await expectLater(
        auth.submit(
          register: true,
          username: 'new_player',
          password: 'New-password-123456',
          email: ' player@example.test ',
        ),
        throwsA(
          isA<AuthFailure>().having(
            (e) => e.code,
            'code',
            'EMAIL_NOT_VERIFIED',
          ),
        ),
      );
      expect(auth.hasPendingIdentity, isTrue);
      expect(exchanges, 0);
      expect(vault.data.values.single,'G'*43);
      mailDown = false;
      await auth.resendVerification();
      expect(verifies, 2);
      await expectLater(
        auth.finishPending(username: 'new_player'),
        throwsA(
          isA<AuthFailure>().having(
            (e) => e.code,
            'code',
            'EMAIL_NOT_VERIFIED',
          ),
        ),
      );
      expect(vault.data.values.single,'G'*43);
      verified = true;
      final user = await auth.finishPending(username: 'new_player');
      expect(user['id'], 'same-local-player');
      expect(api.signedIn, isTrue);
      expect(vault.data.values.single, 'F' * 43);
      expect(auth.hasPendingIdentity, isFalse);
      expect(vault.data.toString(), isNot(contains('google-')));
      providerDown = true;
      await expectLater(
        auth.restore(),
        throwsA(
          isA<AuthFailure>().having(
            (e) => e.code,
            'code',
            'AUTH_PROVIDER_UNAVAILABLE',
          ),
        ),
      );
      expect(api.signedIn, isTrue);
      expect(vault.data, isNotEmpty);
      await auth.resetPassword('missing@example.test');
      expect(resets, 1);
      expect(
        transport.requested.every(
          (uri) => uri.queryParameters['key'] == 'public-fixture',
        ),
        isTrue,
      );
    } finally {
      api.close();
      await server.close(force: true);
    }
  });
}
