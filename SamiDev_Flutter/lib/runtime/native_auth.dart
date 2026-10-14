import 'dart:convert';

import 'api.dart';

class AuthFailure implements Exception {
  const AuthFailure(this.message);
  final String message;
}

/// Uses the existing server session cookie. Passwords never enter a WebView.
class NativeAuth {
  NativeAuth(this.api);
  final PlatformApi api;

  Map<String, dynamic> _user(ApiResponse response) {
    Map<String, dynamic> data;
    try {
      data = response.json;
    } catch (_) {
      throw const AuthFailure('تعذر قراءة رد الخادم. حاول مجددًا.');
    }
    if (response.status != 200 || data['ok'] == false) {
      final message = data['message'];
      throw AuthFailure(
        message is String && message.isNotEmpty && message.length <= 300
            ? message
            : 'تعذر إكمال تسجيل الدخول. حاول مجددًا.',
      );
    }
    final user = data['user'];
    if (user is! Map ||
        user['id'] is! String ||
        (user['id'] as String).isEmpty) {
      throw const AuthFailure('لم يرسل الخادم بيانات حساب صالحة.');
    }
    return Map<String, dynamic>.from(user);
  }

  Future<Map<String, dynamic>?> restore() async {
    if (!api.signedIn) return null;
    final response = await api.request('GET', '/api/me');
    if (response.status == 401 || response.status == 403) {
      await api.clearSession();
      return null;
    }
    return _user(response);
  }

  Future<Map<String, dynamic>> submit({
    required bool register,
    required String username,
    required String password,
    String displayName = '',
  }) async {
    final response = await api.request(
      'POST',
      register ? '/api/auth/register' : '/api/auth/login',
      body: utf8.encode(
        jsonEncode({
          'username': username.trim(),
          'password': password,
          if (register && displayName.trim().isNotEmpty)
            'displayName': displayName.trim(),
        }),
      ),
    );
    final user = _user(response);
    if (!api.signedIn) {
      throw const AuthFailure('لم تُحفظ جلسة الدخول. حاول مجددًا.');
    }
    return user;
  }
}
