import 'dart:convert';
import 'dart:io';

class FirebaseClientFailure implements Exception {
  const FirebaseClientFailure(this.code, this.message);
  final String code, message;
}

/// Calls only Google's fixed authentication endpoints. No service credentials.
class FirebaseClient {
  FirebaseClient(this.apiKey, {HttpClient? httpClient})
    : client = httpClient ?? HttpClient() {
    client.connectionTimeout = const Duration(seconds: 15);
  }
  final String apiKey;
  final HttpClient client;
  String? _idToken, _refreshToken;
  bool get hasIdentity => _idToken != null;

  Future<Map<String, dynamic>> _request(
    String action,
    Map<String, dynamic> body, {
    bool refresh = false,
  }) async {
    final uri = refresh
        ? Uri.https('securetoken.googleapis.com', '/v1/token', {'key': apiKey})
        : Uri.https('identitytoolkit.googleapis.com', '/v1/accounts:$action', {
            'key': apiKey,
          });
    final request = await client
        .postUrl(uri)
        .timeout(const Duration(seconds: 20));
    request.followRedirects = false;
    request.headers.contentType = refresh
        ? ContentType('application', 'x-www-form-urlencoded')
        : ContentType.json;
    request.write(
      refresh
          ? Uri(
              queryParameters: body.map(
                (key, value) => MapEntry(key, value.toString()),
              ),
            ).query
          : jsonEncode(body),
    );
    final response = await request.close().timeout(const Duration(seconds: 20));
    final bytes = <int>[];
    await for (final chunk in response.timeout(const Duration(seconds: 20))) {
      bytes.addAll(chunk);
      if (bytes.length > 1024 * 1024) {
        throw const FirebaseClientFailure(
          'AUTH_RESPONSE_INVALID',
          'رد خدمة المصادقة غير صالح.',
        );
      }
    }
    final data = jsonDecode(utf8.decode(bytes)) as Map<String, dynamic>;
    if (response.statusCode != 200) {
      final code =
          (data['error'] is Map ? data['error']['message'] : null)
              ?.toString()
              .split(' : ')
              .first ??
          'AUTH_FAILED';
      final message = switch (code) {
        'EMAIL_EXISTS' =>
          'البريد مستخدم بالفعل. سجّل الدخول أو استعد كلمة المرور.',
        'INVALID_EMAIL' => 'أدخل بريدًا إلكترونيًا صالحًا.',
        'INVALID_LOGIN_CREDENTIALS' ||
        'EMAIL_NOT_FOUND' ||
        'INVALID_PASSWORD' => 'البريد أو كلمة المرور غير صحيحة.',
        'TOO_MANY_ATTEMPTS_TRY_LATER' =>
          'محاولات كثيرة؛ انتظر قليلًا ثم حاول مجددًا.',
        'WEAK_PASSWORD' || 'PASSWORD_DOES_NOT_MEET_REQUIREMENTS' =>
          'كلمة المرور لا تحقق متطلبات الأمان.',
        'USER_DISABLED' => 'هذا الحساب موقوف.',
        'TOKEN_EXPIRED' ||
        'INVALID_REFRESH_TOKEN' ||
        'USER_NOT_FOUND' => 'انتهت الجلسة. سجّل الدخول مجددًا.',
        _ => 'تعذر الاتصال بخدمة المصادقة. حاول لاحقًا.',
      };
      throw FirebaseClientFailure(code, message);
    }
    return data;
  }

  void _remember(Map<String, dynamic> data) {
    final token = data['idToken'] ?? data['id_token'],
        refresh = data['refreshToken'] ?? data['refresh_token'];
    if (token is! String ||
        refresh is! String ||
        token.isEmpty ||
        refresh.isEmpty) {
      throw const FirebaseClientFailure(
        'AUTH_RESPONSE_INVALID',
        'رد خدمة المصادقة غير صالح.',
      );
    }
    _idToken = token;
    _refreshToken = refresh;
  }

  Future<void> signIn(String email, String password) async {
    clear();
    _remember(
      await _request('signInWithPassword', {
        'email': email.trim(),
        'password': password,
        'returnSecureToken': true,
      }),
    );
  }

  Future<void> signUp(String email, String password) async {
    clear();
    _remember(
      await _request('signUp', {
        'email': email.trim(),
        'password': password,
        'returnSecureToken': true,
      }),
    );
  }

  Future<void> sendVerification() async {
    if (_idToken == null) {
      throw const FirebaseClientFailure('AUTH_REQUIRED', 'سجّل الدخول أولًا.');
    }
    await _request('sendOobCode', {
      'requestType': 'VERIFY_EMAIL',
      'idToken': _idToken,
    });
  }

  Future<void> resetPassword(String email) async {
    try {
      await _request('sendOobCode', {
        'requestType': 'PASSWORD_RESET',
        'email': email.trim(),
      });
    } on FirebaseClientFailure catch (error) {
      if (error.code != 'EMAIL_NOT_FOUND') rethrow;
    }
  }

  Future<String> token({bool forceRefresh = false}) async {
    if (_idToken == null || _refreshToken == null) {
      throw const FirebaseClientFailure('AUTH_REQUIRED', 'سجّل الدخول أولًا.');
    }
    if (forceRefresh) {
      _remember(
        await _request('', {
          'grant_type': 'refresh_token',
          'refresh_token': _refreshToken,
        }, refresh: true),
      );
    }
    return _idToken!;
  }

  void clear() {
    _idToken = null;
    _refreshToken = null;
  }

  void close() {
    clear();
    client.close(force: true);
  }
}
