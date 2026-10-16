import 'dart:convert';

import 'package:flutter/material.dart';

import '../runtime/api.dart';
import '../runtime/native_auth.dart';
import 'auth_screen.dart';

class AccountSettings extends StatefulWidget {
  const AccountSettings({
    super.key,
    required this.api,
    required this.user,
    required this.onChanged,
    this.onTheme,
    this.onAdmin,
  });
  final VoidCallback? onTheme, onAdmin;
  final PlatformApi api;
  final Map<String, dynamic> user;
  final Future<void> Function(Map<String, dynamic>) onChanged;
  @override
  State<AccountSettings> createState() => _AccountSettingsState();
}

class _AccountSettingsState extends State<AccountSettings> {
  late Map<String, dynamic> user = widget.user;
  late final name = TextEditingController(
    text: user['username']?.toString() ?? '',
  );
  bool busy = false;
  String? error;
  String section = '';
  Map<String, dynamic>? security;
  bool loading = false;
  @override
  void dispose() {
    name.dispose();
    super.dispose();
  }

  Future<void> rename() async {
    if (busy) return;
    if (!RegExp(r'^[A-Za-z0-9_]{3,20}$').hasMatch(name.text.trim())) {
      setState(
        () => error = 'استخدم ٣–٢٠ حرفًا إنجليزيًا أو رقمًا أو _ بدون @',
      );
      return;
    }
    final approved = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: const Text('تغيير اسم المستخدم'),
        content: Text(
          user['freeRenameAvailable'] == true
              ? 'هذا التغيير مجاني.'
              : 'ستُستهلك بطاقة تغيير اسم واحدة عند النجاح.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(c, false),
            child: const Text('إلغاء'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(c, true),
            child: const Text('تأكيد'),
          ),
        ],
      ),
    );
    if (approved != true || !mounted) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      final response = await widget.api.request(
        'PATCH',
        '/api/profile',
        body: utf8.encode(jsonEncode({'username': name.text.trim()})),
      );
      final data = response.json;
      if (response.status != 200) {
        throw StateError(data['message']?.toString() ?? 'تعذر تغيير الاسم');
      }
      final updated = Map<String, dynamic>.from(data['user']);
      await widget.onChanged(updated);
      if (mounted) {
        setState(() {
          user = updated;
          name.text = updated['username']?.toString() ?? '';
        });
      }
    } catch (e) {
      if (mounted) {
        setState(
          () => error = e is StateError ? e.message.toString() : 'تعذر الاتصال',
        );
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> logout() async {
    final accepted = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: const Text('تسجيل الخروج'),
        content: Text(
          user['isGuest'] == true
              ? 'سيُنشأ ضيف جديد. اربط بريدك أولًا إذا أردت استرداد تقدمك.'
              : 'ستعود للعب كضيف، ويمكنك الدخول لحسابك لاحقًا من الإعدادات.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(c, false),
            child: const Text('إلغاء'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(c, true),
            child: const Text('خروج'),
          ),
        ],
      ),
    );
    if (accepted != true || !mounted) return;
    setState(() => busy = true);
    try {
      final response = await widget.api.request(
        'POST',
        '/api/auth/logout',
        body: utf8.encode('{}'),
      );
      if (response.status != 200) throw StateError('تعذر الخروج');
      final guest = await NativeAuth(widget.api).guest();
      await widget.onChanged(guest);
      if (mounted) {
        setState(() {
          user = guest;
          name.text = guest['username']?.toString() ?? '';
        });
      }
    } catch (_) {
      if (mounted) setState(() => error = 'تعذر الخروج. حاول مجددًا');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> notifications() async {
    try {
      final response = await widget.api.request('GET', '/api/communities');
      if (response.status != 200) throw StateError('تعذر تحميل الإشعارات');
      final rows = (response.json['notifications'] as List? ?? [])
          .whereType<Map>()
          .toList();
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        builder: (c) => AlertDialog(
          title: const Text('الإشعارات'),
          content: SizedBox(
            width: 400,
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (rows.isEmpty) const Text('لا توجد إشعارات حاليًا'),
                  for (final n in rows)
                    ListTile(
                      title: Text(n['sender']?.toString() ?? 'سيتم'),
                      subtitle: Text(n['text']?.toString() ?? ''),
                    ),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(c),
              child: const Text('إغلاق'),
            ),
          ],
        ),
      );
    } catch (_) {
      if (mounted) setState(() => error = 'تعذر تحميل الإشعارات');
    }
  }

  Future<void> account() async {
    if (widget.api.firebase == null) {
      setState(
        () => error = 'ربط البريد يتطلب تفعيل Firebase على الخادم أولًا. اللعب كضيف متاح.',
      );
      return;
    }
    final auth = NativeAuth(widget.api, linkGuest: user['isGuest'] == true);
    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (c) => Scaffold(
          appBar: AppBar(title: const Text('تسجيل الدخول وربط الحساب')),
          body: AuthScreen(
            auth: auth,
            onAuthenticated: (updated) async {
              await widget.onChanged(updated);
              if (mounted) {
                setState(() {
                  user = updated;
                  name.text = updated['username']?.toString() ?? '';
                });
                if (c.mounted) Navigator.pop(c);
              }
            },
          ),
        ),
      ),
    );
    auth.clearPending();
  }

  Future<Map<String, dynamic>> request(
    String method,
    String path, [
    Map<String, dynamic>? body,
  ]) async {
    final response = await widget.api.request(
      method,
      path,
      body: body == null ? null : utf8.encode(jsonEncode(body)),
    );
    final data = response.json;
    if (response.status < 200 ||
        response.status >= 300 ||
        data['ok'] == false) {
      throw StateError(data['message']?.toString() ?? 'تعذر إكمال الطلب');
    }
    return data;
  }

  Future<void> openAccount() async {
    setState(() {
      section = 'الحساب';
      error = null;
      security = null;
    });
    if (user['isGuest'] == true) return;
    setState(() => loading = true);
    try {
      final info = await request('GET', '/api/account');
      if (mounted) setState(() => security = info);
    } catch (e) {
      if (mounted) {
        setState(
          () => error = e is StateError
              ? e.message.toString()
              : 'تعذر تحميل الحساب',
        );
      }
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> signedOut() async {
    // Never restore the previous user's UI after a successful remote revocation.
    await widget.api.clearSession();
    widget.api.firebase?.clear();
    final guest = await NativeAuth(widget.api).guest();
    await widget.onChanged(guest);
    if (mounted) {
      setState(() {
        user = guest;
        security = null;
        name.text = guest['username']?.toString() ?? '';
      });
    }
  }

  Future<void> passwordReset() async {
    if (busy || security == null) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await NativeAuth(widget.api)
          .resetPassword(security!['email']?.toString() ?? '');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'أرسلنا رابط تغيير كلمة المرور إلى بريد حسابك. بعد التغيير ستنتهي جلسات الدخول السابقة.',
            ),
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        setState(
          () => error = e is AuthFailure ? e.message : 'تعذر إرسال الرسالة',
        );
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> deleteAccount() async {
    final guest = user['isGuest'] == true;
    if (!guest && security == null) return;
    final providers = security?['providers'] as List? ?? [];
    final google = providers.contains('google.com'),
        firebase = providers.isNotEmpty;
    try {
      var password = await showDialog<String>(
        context: context,
        builder: (_) => _DeleteAccountDialog(guest: guest, google: google),
      );
      if (password == null || !mounted) return;
      setState(() {
        busy = true;
        error = null;
      });
      final body = <String, dynamic>{'confirm': 'DELETE'};
      if (!guest) {
        if (firebase) {
          body['idToken'] = await NativeAuth(widget.api).reauthenticate(
            google: google,
            email: security!['email']?.toString() ?? '',
            password: password,
          );
        } else {
          body['password'] = password;
        }
      }
      password = '';
      final data = await request('POST', '/api/account/delete', body);
      await signedOut();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              data['pending'] == true
                  ? 'تم استلام طلب الحذف وإيقاف الحساب. سيُستكمل الحذف تلقائيًا عند عودة خدمة المصادقة.'
                  : 'حُذف الحساب وبياناته من المنصة.',
            ),
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        setState(
          () => error = e is AuthFailure
              ? e.message
              : e is StateError
              ? e.message.toString()
              : 'تعذر حذف الحساب. حاول مجددًا',
        );
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Widget entry(IconData icon, String title, VoidCallback action) => ListTile(
    leading: Icon(icon),
    title: Text(title),
    trailing: const Icon(Icons.chevron_left),
    onTap: busy ? null : action,
  );
  List<Widget> accountItems() {
    final guest = user['isGuest'] == true,
        providers = security?['providers'] as List? ?? [];
    return [
      Text(
        guest
            ? 'تلعب كضيف. اربط حسابك لحفظ تقدمك والوصول إليه من جهاز آخر.'
            : 'إدارة حسابك وأمان الدخول.',
      ),
      if (guest)
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 16),
          child: FilledButton(
            onPressed: busy ? null : account,
            child: const Text('ربط الحساب أو تسجيل الدخول'),
          ),
        ),
      if (loading)
        const Padding(
          padding: EdgeInsets.all(16),
          child: Center(child: CircularProgressIndicator()),
        ),
      if (!guest && security != null)
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  user['username']?.toString() ?? '',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                Text(
                  security!['email']?.toString() ?? '',
                  textDirection: TextDirection.ltr,
                ),
                Text(
                  'طريقة الدخول: ${providers.map((p) => {'google.com': 'Google', 'password': 'البريد وكلمة المرور', 'apple.com': 'Apple'}[p] ?? p).join('، ')}',
                ),
                if (providers.contains('google.com') &&
                    !providers.contains('password'))
                  const Text('تُدار كلمة مرور Google من حسابك لدى Google.'),
                if (providers.contains('password'))
                  TextButton(
                    onPressed: busy ? null : passwordReset,
                    child: const Text('تغيير كلمة المرور عبر البريد'),
                  ),
              ],
            ),
          ),
        ),
      if (!guest && !loading && security == null)
        TextButton(
          onPressed: openAccount,
          child: const Text('إعادة تحميل بيانات الحساب'),
        ),
      const SizedBox(height: 24),
      TextField(
        controller: name,
        enabled: !busy,
        textDirection: TextDirection.ltr,
        decoration: const InputDecoration(labelText: 'اسم المستخدم بدون @'),
      ),
      const SizedBox(height: 12),
      Text(
        user['freeRenameAvailable'] == true
            ? 'تغيير مجاني مرة واحدة.'
            : 'بطاقات تغيير الاسم: ${user['renameCredits'] ?? 0} · تتوفر في المتجر.',
      ),
      TextButton(
        onPressed: busy ? null : rename,
        child: const Text('حفظ اسم المستخدم'),
      ),
      const Divider(),
      TextButton(
        onPressed: busy ? null : logout,
        child: const Text('تسجيل الخروج والعودة كضيف'),
      ),
      TextButton(
        onPressed: busy || (!guest && security == null) ? null : deleteAccount,
        child: Text(
          'حذف الحساب نهائيًا',
          style: TextStyle(color: Theme.of(context).colorScheme.error),
        ),
      ),
    ];
  }

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: section.isEmpty && !busy,
    onPopInvokedWithResult: (didPop, result) {
      if (!didPop && !busy && mounted) setState(() => section = '');
    },
    child: Scaffold(
      appBar: AppBar(
        title: Text(section.isEmpty ? 'الإعدادات' : section),
        leading: section.isEmpty
            ? null
            : BackButton(
                onPressed: busy ? null : () => setState(() => section = ''),
              ),
      ),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          if (section.isEmpty) ...[
            Card(
              child: Column(
                children: [
                  entry(Icons.person_outline, 'الحساب', openAccount),
                  entry(
                    Icons.devices,
                    'الأجهزة',
                    () => Navigator.push(
                      context,
                      MaterialPageRoute<void>(
                        builder: (_) => AccountDevices(
                          api: widget.api,
                          onSignedOut: signedOut,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ),
            Card(
              child: Column(
                children: [
                  if (widget.onTheme != null)
                    entry(Icons.palette_outlined, 'المظهر', widget.onTheme!),
                  entry(Icons.notifications_none, 'الإشعارات', notifications),
                  entry(
                    Icons.lock_outline,
                    'الخصوصية',
                    () => setState(() => section = 'الخصوصية'),
                  ),
                ],
              ),
            ),
            if (widget.onAdmin != null &&
                {'admin', 'moderator'}.contains(user['role']))
              Card(
                child: entry(
                  Icons.admin_panel_settings_outlined,
                  'الإدارة',
                  () {
                    Navigator.pop(context);
                    widget.onAdmin!();
                  },
                ),
              ),
          ] else if (section == 'الحساب')
            ...accountItems()
          else ...[
            const Text(
              'بيانات الحساب والخصوصية',
              style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 16),
            const Text(
              'نستخدم بريد حسابك للتحقق من هويتك واستعادة الدخول. يظهر اسم المستخدم والصورة والمقتنيات العامة للاعبين، ولا يظهر بريدك في ملفك العام.',
            ),
            const SizedBox(height: 16),
            const Text(
              'تسجل قائمة الأجهزة نوع الجهاز وآخر نشاط، والدولة التقريبية عند توفرها. لا نطلب الوصول إلى موقع GPS.',
            ),
            const SizedBox(height: 16),
            const Text(
              'يمكنك إنهاء جلسات أجهزتك من قسم الأجهزة، أو حذف حسابك وبياناته من قسم الحساب.',
            ),
            TextButton(
              onPressed: openAccount,
              child: const Text('إدارة الحساب وحذفه'),
            ),
          ],
          if (error != null)
            Padding(
              padding: const EdgeInsets.only(top: 16),
              child: Text(
                error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ),
          if (busy) const LinearProgressIndicator(),
        ],
      ),
    ),
  );
}

class AccountDevices extends StatefulWidget {
  const AccountDevices({
    super.key,
    required this.api,
    required this.onSignedOut,
  });
  final PlatformApi api;
  final Future<void> Function() onSignedOut;
  @override
  State<AccountDevices> createState() => _AccountDevicesState();
}

class _AccountDevicesState extends State<AccountDevices> {
  List<Map<String, dynamic>> devices = [];
  bool loading = true, busy = false;
  String? error;
  @override
  void initState() {
    super.initState();
    load();
  }

  Future<Map<String, dynamic>> request(String method, String path) async {
    final response = await widget.api.request(
      method,
      path,
      body: method == 'POST' ? utf8.encode('{}') : null,
    );
    if (response.status != 200) {
      throw StateError(
        response.json['message']?.toString() ?? 'تعذر إكمال الطلب',
      );
    }
    return response.json;
  }

  Future<void> load() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final data = await request('GET', '/api/account/devices');
      if (mounted) {
        setState(
          () => devices = (data['devices'] as List)
              .map((v) => Map<String, dynamic>.from(v))
              .toList(),
        );
      }
    } catch (_) {
      if (mounted) setState(() => error = 'تعذر تحميل الأجهزة. أعد المحاولة.');
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> revoke([Map<String, dynamic>? device]) async {
    final approved = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: const Text('تسجيل الخروج'),
        content: Text(
          device == null
              ? 'تسجيل الخروج من جميع الأجهزة، بما فيها هذا الجهاز؟'
              : 'تسجيل الخروج من ${device['device']}؟',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(c, false),
            child: const Text('إلغاء'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(c, true),
            child: const Text('تأكيد'),
          ),
        ],
      ),
    );
    if (approved != true || !mounted) return;
    setState(() => busy = true);
    try {
      final data = await request(
        device == null ? 'POST' : 'DELETE',
        device == null
            ? '/api/account/logout-all'
            : '/api/account/devices/${device['id']}',
      );
      if (data['signedOut'] == true) {
        await widget.onSignedOut();
        if (mounted) Navigator.pop(context);
      } else {
        await load();
      }
    } catch (_) {
      if (mounted) setState(() => error = 'تعذر تسجيل الخروج. أعد المحاولة.');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  String stamp(dynamic value) => value is num
      ? DateTime.fromMillisecondsSinceEpoch(value.toInt())
            .toLocal()
            .toString()
            .split('.')
            .first
      : 'غير متاح للجلسات القديمة';
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('الأجهزة'),
      actions: [
        IconButton(
          onPressed: busy || loading ? null : load,
          icon: const Icon(Icons.refresh),
          tooltip: 'تحديث الأجهزة',
        ),
      ],
    ),
    body: ListView(
      padding: const EdgeInsets.all(20),
      children: [
        const Icon(Icons.devices, size: 64),
        const SizedBox(height: 12),
        const Text(
          'أجهزتك المتصلة',
          textAlign: TextAlign.center,
          style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
        ),
        const Padding(
          padding: EdgeInsets.symmetric(vertical: 16),
          child: Text(
            'كل تسجيل دخول جلسة مستقلة. نوع الجهاز تقريبي، والموقع عند توفره مستنتج من الشبكة وقد يتأثر باستخدام VPN.',
          ),
        ),
        if (loading) const Center(child: CircularProgressIndicator()),
        for (final device in devices)
          Card(
            child: ListTile(
              isThreeLine: true,
              leading: Icon(
                device['client'] == 'تطبيق SamiDev'
                    ? Icons.phone_android
                    : Icons.computer,
              ),
              title: Text(
                '${device['device']}${device['current'] == true ? ' · هذا الجهاز' : ''}',
              ),
              subtitle: Text(
                '${device['client']}\nآخر نشاط: ${stamp(device['lastSeenAt'])}\nالموقع التقريبي: ${device['country'] == '' ? 'غير متاح' : device['country']}',
              ),
              trailing: IconButton(
                onPressed: busy ? null : () => revoke(device),
                icon: const Icon(Icons.logout),
                tooltip: 'تسجيل الخروج',
              ),
            ),
          ),
        if (!loading && devices.isEmpty && error == null)
          const Text('لا توجد جلسات نشطة.'),
        if (error != null)
          Text(
            error!,
            style: TextStyle(color: Theme.of(context).colorScheme.error),
          ),
        const SizedBox(height: 20),
        TextButton.icon(
          onPressed: busy || loading ? null : () => revoke(),
          icon: const Icon(Icons.logout),
          label: const Text('تسجيل الخروج من جميع الأجهزة'),
        ),
        if (busy) const LinearProgressIndicator(),
      ],
    ),
  );
}

class _DeleteAccountDialog extends StatefulWidget {
  const _DeleteAccountDialog({required this.guest, required this.google});
  final bool guest, google;
  @override
  State<_DeleteAccountDialog> createState() => _DeleteAccountDialogState();
}

class _DeleteAccountDialogState extends State<_DeleteAccountDialog> {
  final password = TextEditingController();
  String? error;
  @override
  void dispose() {
    password.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('حذف الحساب نهائيًا'),
    content: SingleChildScrollView(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Text(
            'سيُحذف ملفك وصورتك ومقتنياتك وتقدمك وروابط الصداقة ورسائلك المخزنة في المساحات. ستنتهي جلساتك على جميع الأجهزة. لا يمكن التراجع عن الحذف.',
          ),
          if (widget.google)
            const Text('أكد نفس حساب Google في الخطوة التالية.'),
          if (!widget.guest && !widget.google)
            TextField(
              controller: password,
              obscureText: true,
              autofillHints: const [AutofillHints.password],
              decoration: InputDecoration(
                labelText: 'كلمة المرور الحالية',
                errorText: error,
              ),
            ),
        ],
      ),
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('إلغاء'),
      ),
      TextButton(
        onPressed: () {
          if (!widget.guest && !widget.google && password.text.isEmpty) {
            setState(() => error = 'أدخل كلمة المرور الحالية');
            return;
          }
          final value = password.text;
          password.clear();
          Navigator.pop(context, value);
        },
        child: Text(
          'تأكيد الحذف النهائي',
          style: TextStyle(color: Theme.of(context).colorScheme.error),
        ),
      ),
    ],
  );
}
