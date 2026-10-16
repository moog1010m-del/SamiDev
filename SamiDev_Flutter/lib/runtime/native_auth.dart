import 'dart:convert';
import 'dart:io';

import 'package:google_sign_in/google_sign_in.dart';

import 'api.dart';
import 'firebase_client.dart';

class AuthFailure implements Exception {
  const AuthFailure(this.message, {this.code = 'AUTH_FAILED'});
  final String message;
  final String code;
}

/// Uses the existing server session cookie. Passwords never enter a WebView.
class NativeAuth {
  NativeAuth(this.api, {this.linkGuest = false, this.googleTokenProvider});
  final Future<String> Function()? googleTokenProvider;
  static Future<void>? _googleInitialization;
  Map<String, dynamic> _config = {};
  final bool linkGuest;
  bool _linkPending = false;
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
        code: data['error']?.toString() ?? 'AUTH_FAILED',
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

  bool get usesFirebase => api.firebase != null;
  bool get hasPendingIdentity => api.firebase?.hasIdentity ?? false;
  Future<void> prepare() async {
    final response = await api.request('GET', '/api/auth/config');
    if (response.status != 200) {
      throw const AuthFailure('تعذر تحميل إعدادات المصادقة.');
    }
    final config = response.json;
    _config = config;
    if (config['provider'] == 'firebase') {
      final key = config['apiKey'];
      if (key is! String || key.isEmpty) {
        throw const AuthFailure('إعدادات Firebase غير مكتملة.');
      }
      api.firebase?.close();
      api.firebase = FirebaseClient(key);
    } else if (config['provider'] == 'local') {
      api.firebase?.close();
      api.firebase = null;
    } else {
      throw const AuthFailure('إعدادات المصادقة غير صالحة.');
    }
  }

  Future<String> googleIdentity() async {
    if (_config.isEmpty) await prepare();
    if (!usesFirebase) {
      throw const AuthFailure('فعّل Firebase على الخادم أولًا.');
    }
    try {
      String token;
      if (googleTokenProvider != null) {
        token = await googleTokenProvider!();
      } else {
        final clientId = _config['googleClientId']?.toString() ?? '';
        final iosId = _config['googleIosClientId']?.toString() ?? '';
        if (clientId.isEmpty || (Platform.isIOS && iosId.isEmpty)) {
          throw const AuthFailure(
            'إعدادات Google للتطبيق غير مكتملة. يلزم ربط معرّفات OAuth الخاصة بأندرويد وiOS.',
          );
        }
        _googleInitialization ??= GoogleSignIn.instance.initialize(
          serverClientId: clientId,
          clientId: Platform.isIOS ? iosId : null,
        );
        try {
          await _googleInitialization;
        } catch (_) {
          _googleInitialization = null;
          rethrow;
        }
        final account = await GoogleSignIn.instance.authenticate();
        token = account.authentication.idToken ?? '';
      }
      if (token.isEmpty) {
        throw const AuthFailure('لم ترسل Google إثبات هوية صالحًا.');
      }
      await api.firebase!.signInGoogle(
        token,
        _config['projectId']?.toString() ?? '',
      );
      return await api.firebase!.token();
    } on GoogleSignInException catch (e) {
      clearPending();
      throw AuthFailure(
        e.code == GoogleSignInExceptionCode.canceled
            ? 'أُلغي الدخول باستخدام Google.'
            : 'تعذر فتح Google. تحقق من إعدادات التطبيق.',
        code: 'GOOGLE_SIGN_IN_FAILED',
      );
    } on FirebaseClientFailure catch (e) {
      clearPending();
      throw AuthFailure(e.message, code: e.code);
    }
  }

  Future<Map<String, dynamic>> signInGoogle() async {
    clearPending();
    await googleIdentity();
    _linkPending = linkGuest;
    return await finishPending();
  }

  Future<String> reauthenticate({
    required bool google,
    required String email,
    String password = '',
  }) async {
    try {
      if (google) return await googleIdentity();
      if (api.firebase == null) await prepare();
      await api.firebase!.signIn(email, password);
      return await api.firebase!.token();
    } on FirebaseClientFailure catch (e) {
      throw AuthFailure(e.message, code: e.code);
    } finally {
      api.firebase?.clear();
    }
  }

  Future<void> resendVerification() async {
    try {
      await api.firebase!.sendVerification();
    } on FirebaseClientFailure catch (e) {
      throw AuthFailure(e.message, code: e.code);
    }
  }

  Future<void> resetPassword(String email) async {
    try {
      await api.firebase!.resetPassword(email);
    } on FirebaseClientFailure catch (e) {
      throw AuthFailure(e.message, code: e.code);
    }
  }

  void clearPending() {
    _linkPending = false;
    api.firebase?.clear();
  }

  Future<Map<String, dynamic>> finishPending({
    String username = '',
    String displayName = '',
  }) async {
    try {
      final token = await api.firebase!.token(forceRefresh: true);
      final response = await api.request(
        'POST',
        '/api/auth/firebase',
        body: utf8.encode(
          jsonEncode({
            'idToken': token,
            'username': username.trim(),
            'linkGuest': _linkPending,
          }),
        ),
      );
      final user = _user(response);
      if (!api.signedIn) throw const AuthFailure('لم تُحفظ جلسة الدخول.');
      api.firebase!.clear();
      return user;
    } on FirebaseClientFailure catch (e) {
      throw AuthFailure(e.message, code: e.code);
    }
  }

  Future<Map<String, dynamic>> guest() async {
    final user = _user(
      await api.request('POST', '/api/auth/guest', body: utf8.encode('{}')),
    );
    if (!api.signedIn) throw const AuthFailure('لم تُحفظ جلسة الضيف.');
    return user;
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
    String email = '',
  }) async {
    if (usesFirebase) {
      try {
        if (register) {
          _linkPending = linkGuest;
          await api.firebase!.signUp(email, password);
          try {
            await api.firebase!.sendVerification();
          } catch (_) {
            throw const AuthFailure(
              "أُنشئ الحساب، لكن تعذر إرسال رسالة التوثيق. اضغط إعادة إرسال رسالة التوثيق.",
              code: "EMAIL_NOT_VERIFIED",
            );
          }
          throw const AuthFailure(
            'أرسلنا رسالة توثيق إلى بريدك. افتحها ثم اضغط تحققت من بريدي.',
            code: 'EMAIL_NOT_VERIFIED',
          );
        }
        _linkPending = linkGuest;
        await api.firebase!.signIn(email, password);
        return await finishPending(
          username: username,
          displayName: displayName,
        );
      } on FirebaseClientFailure catch (e) {
        throw AuthFailure(e.message, code: e.code);
      }
    }
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
