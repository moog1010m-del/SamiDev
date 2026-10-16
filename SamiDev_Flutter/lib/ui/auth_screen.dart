import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../runtime/native_auth.dart';
import '../runtime/failures.dart';

class AuthScreen extends StatefulWidget {
  const AuthScreen({
    super.key,
    required this.auth,
    required this.onAuthenticated,
  });
  final NativeAuth auth;
  final Future<void> Function(Map<String, dynamic>) onAuthenticated;
  @override
  State<AuthScreen> createState() => _AuthScreenState();
}

class _AuthScreenState extends State<AuthScreen> {
  final _form = GlobalKey<FormState>();
  final _username = TextEditingController(),
      _password = TextEditingController();
  final _email = TextEditingController();
  bool _register = false, _busy = false, _obscured = true, _pending = false;
  String? _error;
  bool get firebase => widget.auth.usesFirebase;
  bool get finishing => firebase && _pending && widget.auth.hasPendingIdentity;
  @override
  void dispose() {
    for (final c in [_username, _password, _email]) {
      c.clear();
      c.dispose();
    }
    super.dispose();
  }

  void _switch(bool register) {
    if (_busy || register == _register) return;
    FocusScope.of(context).unfocus();
    widget.auth.clearPending();
    setState(() {
      _register = register;
      _pending = false;
      _error = null;
      _obscured = true;
      _password.clear();
    });
  }

  Future<void> _google() async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final user = await widget.auth.signInGoogle();
      if (mounted) await widget.onAuthenticated(user);
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = e is AuthFailure
              ? e.message
              : 'تعذر الدخول باستخدام Google.';
        });
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _submit() async {
    if (_busy || !(_form.currentState?.validate() ?? false)) return;
    FocusScope.of(context).unfocus();
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final user = finishing
          ? await widget.auth.finishPending(
              username: firebase ? '' : _username.text,
            )
          : await widget.auth.submit(
              register: _register,
              username: firebase ? '' : _username.text,
              password: _password.text,
              email: _email.text,
            );
      if (!mounted) return;
      TextInput.finishAutofillContext();
      _password.clear();
      await widget.onAuthenticated(user);
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = e is AuthFailure
              ? e.message
              : RuntimeFailure.from(e).message;
          if (e is AuthFailure && e.code == 'EMAIL_NOT_VERIFIED') {
            _pending = true;
            _password.clear();
          }
          if (e is AuthFailure &&
              [
                'INVALID_ID_TOKEN',
                'TOKEN_EXPIRED',
                'INVALID_REFRESH_TOKEN',
              ].contains(e.code)) {
            widget.auth.clearPending();
            _pending = false;
            _register = false;
          }
        });
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _mail({bool reset = false}) async {
    if (_busy) return;
    if (reset &&
        !RegExp(r'^[^\s@]+@[^\s@]+\.[^\s@]+$').hasMatch(_email.text.trim())) {
      setState(() => _error = 'أدخل بريدك الإلكتروني أولًا.');
      return;
    }
    setState(() => _busy = true);
    try {
      if (reset) {
        await widget.auth.resetPassword(_email.text);
      } else {
        await widget.auth.resendVerification();
      }
      if (mounted) {
        setState(
          () => _error = reset
              ? 'إذا كان البريد مسجلًا فستصلك رسالة لاستعادة كلمة المرور.'
              : 'أعدنا إرسال رسالة التوثيق. تحقق من صندوق البريد والرسائل غير المرغوبة.',
        );
      }
    } catch (e) {
      if (mounted) {
        setState(
          () => _error = e is AuthFailure
              ? e.message
              : RuntimeFailure.from(e).message,
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  InputDecoration field(String label, IconData icon) => InputDecoration(
    labelText: label,
    prefixIcon: Icon(icon),
    filled: true,
    border: OutlineInputBorder(borderRadius: BorderRadius.circular(16)),
    contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 18),
  );
  Widget usernameField() => TextFormField(
    key: const ValueKey('auth-username'),
    controller: _username,
    enabled: !_busy,
    textDirection: TextDirection.ltr,
    autocorrect: false,
    enableSuggestions: false,
    textInputAction: TextInputAction.next,
    autofillHints: const [AutofillHints.username],
    decoration: field('اسم المستخدم (بدون @)', Icons.person_outline),
    validator: (v) => RegExp(r'^[A-Za-z0-9_]{3,20}$').hasMatch((v ?? '').trim())
        ? null
        : 'استخدم ٣–٢٠ حرفًا إنجليزيًا أو رقمًا أو _',
  );
  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return PopScope(
      canPop: !_busy,
      child: AutofillGroup(
        child: SingleChildScrollView(
          key: const ValueKey('native-auth-scroll'),
          keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 28),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 440),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const SizedBox(height: 16),
                  Center(
                    child: Container(
                      width: 72,
                      height: 72,
                      decoration: BoxDecoration(
                        color: colors.primaryContainer,
                        borderRadius: BorderRadius.circular(24),
                      ),
                      child: Icon(
                        Icons.sports_esports_rounded,
                        color: colors.primary,
                        size: 38,
                      ),
                    ),
                  ),
                  const SizedBox(height: 18),
                  const Text(
                    'SamiDev',
                    textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 30, fontWeight: FontWeight.w800),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'لعبتك وجمعتك في مكان واحد',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: colors.onSurfaceVariant),
                  ),
                  const SizedBox(height: 28),
                  SegmentedButton<bool>(
                    showSelectedIcon: false,
                    segments: const [
                      ButtonSegment(value: false, label: Text('تسجيل الدخول')),
                      ButtonSegment(value: true, label: Text('حساب جديد')),
                    ],
                    selected: {_register},
                    onSelectionChanged: _busy ? null : (v) => _switch(v.single),
                  ),
                  const SizedBox(height: 24),
                  Form(
                    key: _form,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        if (firebase && !finishing) ...[
                          OutlinedButton.icon(
                            key: const ValueKey('auth-google'),
                            onPressed: _busy ? null : _google,
                            icon: const Text(
                              'G',
                              style: TextStyle(
                                color: Color(0xff4285f4),
                                fontSize: 22,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                            label: const Text('المتابعة باستخدام Google'),
                            style: OutlinedButton.styleFrom(
                              minimumSize: const Size.fromHeight(48),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(12),
                              ),
                            ),
                          ),
                          const SizedBox(height: 16),
                          TextFormField(
                            key: const ValueKey('auth-email'),
                            controller: _email,
                            enabled: !_busy && !finishing,
                            keyboardType: TextInputType.emailAddress,
                            textDirection: TextDirection.ltr,
                            autocorrect: false,
                            autofillHints: const [AutofillHints.email],
                            textInputAction: TextInputAction.next,
                            decoration: field(
                              'البريد الإلكتروني',
                              Icons.alternate_email,
                            ),
                            validator: (v) =>
                                RegExp(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
                                    .hasMatch((v ?? '').trim())
                                ? null
                                : 'أدخل بريدًا إلكترونيًا صالحًا',
                          ),
                          const SizedBox(height: 16),
                        ],
                        if (!firebase) ...[
                          usernameField(),
                          const SizedBox(height: 16),
                        ],
                        if (!finishing) ...[
                          TextFormField(
                            key: const ValueKey('auth-password'),
                            controller: _password,
                            enabled: !_busy,
                            obscureText: _obscured,
                            textDirection: TextDirection.ltr,
                            autocorrect: false,
                            enableSuggestions: false,
                            autofillHints: [
                              _register
                                  ? AutofillHints.newPassword
                                  : AutofillHints.password,
                            ],
                            textInputAction: TextInputAction.done,
                            onFieldSubmitted: (_) {
                              _submit();
                            },
                            decoration:
                                field(
                                  firebase
                                      ? 'كلمة مرور حساب SamiDev'
                                      : 'كلمة المرور',
                                  Icons.lock_outline,
                                ).copyWith(
                                  helperText: _register
                                      ? '١٥ حرفًا على الأقل، وحتى ١٢٨ حرفًا'
                                      : null,
                                  suffixIcon: IconButton(
                                    onPressed: _busy
                                        ? null
                                        : () => setState(
                                            () => _obscured = !_obscured,
                                          ),
                                    tooltip: _obscured
                                        ? 'إظهار كلمة المرور'
                                        : 'إخفاء كلمة المرور',
                                    icon: Icon(
                                      _obscured
                                          ? Icons.visibility_outlined
                                          : Icons.visibility_off_outlined,
                                    ),
                                  ),
                                ),
                            validator: (v) {
                              final n = (v ?? '').runes.length;
                              if (n == 0) return 'أدخل كلمة المرور';
                              if (n > 128) return 'الحد الأقصى ١٢٨ حرفًا';
                              if (_register && n < 15) {
                                return 'كلمة المرور يجب ألا تقل عن ١٥ حرفًا';
                              }
                              return null;
                            },
                          ),
                        ],
                        if (_pending)
                          const Padding(
                            padding: EdgeInsets.only(top: 16),
                            child: Text(
                              'افتح رسالة التوثيق في بريدك، ثم ارجع هنا واضغط تحققت من بريدي.',
                            ),
                          ),
                        if (_error != null)
                          Padding(
                            padding: const EdgeInsets.only(top: 18),
                            child: Semantics(
                              liveRegion: true,
                              child: Text(
                                _error!,
                                key: const ValueKey('auth-error'),
                                style: TextStyle(
                                  color: colors.error,
                                  height: 1.6,
                                ),
                              ),
                            ),
                          ),
                        const SizedBox(height: 24),
                        FilledButton(
                          key: const ValueKey('auth-submit'),
                          onPressed: _busy ? null : _submit,
                          style: FilledButton.styleFrom(
                            minimumSize: const Size.fromHeight(52),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(16),
                            ),
                          ),
                          child: _busy
                              ? SizedBox(
                                  width: 22,
                                  height: 22,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                    color: colors.onPrimary,
                                  ),
                                )
                              : Text(
                                  _pending
                                      ? 'تحققت من بريدي'
                                      : _register
                                      ? 'إنشاء الحساب'
                                      : 'دخول',
                                ),
                        ),
                        if (firebase) ...[
                          if (_pending)
                            TextButton(
                              onPressed: _busy ? null : () => _mail(),
                              child: const Text('إعادة إرسال رسالة التوثيق'),
                            ),
                          TextButton(
                            onPressed: _busy ? null : () => _mail(reset: true),
                            child: const Text('نسيت كلمة المرور؟'),
                          ),
                        ],
                      ],
                    ),
                  ),
                  const SizedBox(height: 24),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
