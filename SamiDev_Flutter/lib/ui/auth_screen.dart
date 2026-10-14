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
  final Future<void> Function(Map<String, dynamic> user) onAuthenticated;
  @override
  State<AuthScreen> createState() => _AuthScreenState();
}

class _AuthScreenState extends State<AuthScreen> {
  final _form = GlobalKey<FormState>();
  final _username = TextEditingController(),
      _password = TextEditingController();
  final _displayName = TextEditingController(),
      _confirmation = TextEditingController();
  bool _register = false, _busy = false, _obscured = true;
  String? _error;

  @override
  void dispose() {
    for (final controller in [
      _username,
      _password,
      _displayName,
      _confirmation,
    ]) {
      controller.clear();
      controller.dispose();
    }
    super.dispose();
  }

  void _switch(bool register) {
    if (_busy || register == _register) return;
    FocusScope.of(context).unfocus();
    setState(() {
      _register = register;
      _error = null;
      _obscured = true;
      _password.clear();
      _confirmation.clear();
      _form.currentState?.reset();
    });
  }

  Future<void> _submit() async {
    if (_busy || !(_form.currentState?.validate() ?? false)) return;
    FocusScope.of(context).unfocus();
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final user = await widget.auth.submit(
        register: _register,
        username: _username.text,
        password: _password.text,
        displayName: _displayName.text,
      );
      if (!mounted) return;
      TextInput.finishAutofillContext();
      _password.clear();
      _confirmation.clear();
      await widget.onAuthenticated(user);
    } catch (error) {
      if (mounted) {
        setState(
          () => _error = error is AuthFailure
              ? error.message
              : RuntimeFailure.from(error).message,
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

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return AutofillGroup(
      child: LayoutBuilder(
        builder: (context, constraints) => SingleChildScrollView(
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
                    style: TextStyle(
                      color: colors.onSurfaceVariant,
                      fontSize: 14,
                    ),
                  ),
                  const SizedBox(height: 28),
                  SegmentedButton<bool>(
                    showSelectedIcon: false,
                    segments: const [
                      ButtonSegment(value: false, label: Text('تسجيل الدخول')),
                      ButtonSegment(value: true, label: Text('حساب جديد')),
                    ],
                    selected: {_register},
                    onSelectionChanged: _busy
                        ? null
                        : (values) => _switch(values.single),
                  ),
                  const SizedBox(height: 24),
                  Form(
                    key: _form,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        if (_register) ...[
                          TextFormField(
                            key: const ValueKey('auth-display-name'),
                            controller: _displayName,
                            enabled: !_busy,
                            textInputAction: TextInputAction.next,
                            maxLength: 24,
                            autofillHints: const [AutofillHints.nickname],
                            decoration: field(
                              'الاسم الظاهر (اختياري)',
                              Icons.badge_outlined,
                            ),
                          ),
                          const SizedBox(height: 14),
                        ],
                        TextFormField(
                          key: const ValueKey('auth-username'),
                          controller: _username,
                          enabled: !_busy,
                          textDirection: TextDirection.ltr,
                          autocorrect: false,
                          enableSuggestions: false,
                          textInputAction: TextInputAction.next,
                          autofillHints: const [AutofillHints.username],
                          decoration: field(
                            'اسم المستخدم',
                            Icons.person_outline,
                          ),
                          validator: (value) =>
                              RegExp(r'^[A-Za-z0-9_]{3,20}$')
                                  .hasMatch((value ?? '').trim())
                              ? null
                              : 'استخدم ٣–٢٠ حرفًا إنجليزيًا أو رقمًا أو _',
                        ),
                        const SizedBox(height: 16),
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
                          textInputAction: _register
                              ? TextInputAction.next
                              : TextInputAction.done,
                          onFieldSubmitted: (_) {
                            if (!_register) _submit();
                          },
                          decoration: field('كلمة المرور', Icons.lock_outline)
                              .copyWith(
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
                          validator: (value) {
                            final length = (value ?? '').runes.length;
                            if (length == 0) return 'أدخل كلمة المرور';
                            if (length > 128) return 'الحد الأقصى ١٢٨ حرفًا';
                            if (_register && length < 15) {
                              return 'كلمة المرور يجب ألا تقل عن ١٥ حرفًا';
                            }
                            return null;
                          },
                        ),
                        if (_register) ...[
                          const SizedBox(height: 16),
                          TextFormField(
                            key: const ValueKey('auth-confirm-password'),
                            controller: _confirmation,
                            enabled: !_busy,
                            obscureText: _obscured,
                            textDirection: TextDirection.ltr,
                            autocorrect: false,
                            enableSuggestions: false,
                            textInputAction: TextInputAction.done,
                            onFieldSubmitted: (_) => _submit(),
                            decoration: field(
                              'تأكيد كلمة المرور',
                              Icons.lock_reset_outlined,
                            ),
                            validator: (value) => value == _password.text
                                ? null
                                : 'كلمتا المرور غير متطابقتين',
                          ),
                        ],
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
                                  _register ? 'إنشاء الحساب' : 'دخول',
                                  style: const TextStyle(
                                    fontWeight: FontWeight.w700,
                                  ),
                                ),
                        ),
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
