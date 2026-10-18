import 'dart:convert';

import 'package:flutter/material.dart';

import '../runtime/api.dart';
import '../runtime/native_auth.dart';
import 'auth_screen.dart';
import 'settings_components.dart';

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
  List<Map<String, dynamic>> notices = [];
  Map<String, dynamic>? security;
  bool loading = false;
  @override
  void dispose() {
    name.dispose();
    super.dispose();
  }

  Future<void> editBio() async {
    final field=TextEditingController(text:user['bio']?.toString()??'');
    final value=await showDialog<String>(context:context,builder:(context)=>AlertDialog(title:const Text('نبذة عني'),content:TextField(controller:field,maxLength:160,minLines:2,maxLines:4,decoration:const InputDecoration(hintText:'اكتب نبذة قصيرة عنك')),actions:[TextButton(onPressed:()=>Navigator.pop(context),child:const Text('إلغاء')),FilledButton(onPressed:()=>Navigator.pop(context,field.text),child:const Text('حفظ'))]));
    if(value==null||!mounted)return;
    setState(()=>busy=true);
    try{final response=await widget.api.request('PATCH','/api/profile',body:utf8.encode(jsonEncode({'bio':value})));
      if(response.status!=200)throw StateError(response.json['message']?.toString()??'تعذر حفظ النبذة');
      final updated=Map<String,dynamic>.from(response.json['user']);await widget.onChanged(updated);if(mounted)setState(()=>user=updated);
    }catch(_){if(mounted)setState(()=>error='تعذر حفظ النبذة. حاول مجددًا.');}finally{if(mounted)setState(()=>busy=false);}
  }
  Future<void> rename({bool confirmed = false}) async {
    if (busy) return;
    if (!RegExp(r'^[A-Za-z0-9_]{3,20}$').hasMatch(name.text.trim())) {
      setState(
        () => error = 'استخدم ٣–٢٠ حرفًا إنجليزيًا أو رقمًا أو _ بدون @',
      );
      return;
    }
    final approved = confirmed
        ? true
        : await showDialog<bool>(
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
    setState(() {
      section = 'الإشعارات';
      loading = true;
      error = null;
    });
    try {
      final response = await widget.api.request('GET', '/api/communities');
      if (response.status != 200) throw StateError('تعذر تحميل الإشعارات');
      final rows = (response.json['notifications'] as List? ?? [])
          .whereType<Map>()
          .map((v) => Map<String, dynamic>.from(v))
          .toList();
      if (mounted) setState(() => notices = rows);
    } catch (_) {
      if (mounted) setState(() => error = 'تعذر تحميل الإشعارات. حاول مجددًا.');
    } finally {
      if (mounted) setState(() => loading = false);
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
    if (mounted) await openAccount();
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

  Future<void> editUsername() async {
    name.text = user['username']?.toString() ?? '';
    String? validation;
    final accepted = await showDialog<bool>(
      context: context,
      builder: (c) => StatefulBuilder(
        builder: (c, update) => AlertDialog(
          title: const Text('تغيير اسم المستخدم'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                user['freeRenameAvailable'] == true
                    ? 'هذا التغيير مجاني.'
                    : 'ستُستهلك بطاقة تغيير اسم واحدة عند الحفظ.',
              ),
              const SizedBox(height: 18),
              TextField(
                controller: name,
                autofocus: true,
                textDirection: TextDirection.ltr,
                autofillHints: const [AutofillHints.username],
                maxLength: 20,
                decoration: InputDecoration(
                  labelText: 'الاسم الجديد',
                  helperText: 'بدون @',
                  errorText: validation,
                ),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(c, false),
              child: const Text('إلغاء'),
            ),
            FilledButton(
              onPressed: () {
                if (!RegExp(r'^[A-Za-z0-9_]{3,20}$')
                    .hasMatch(name.text.trim())) {
                  update(
                    () => validation =
                        'استخدم ٣–٢٠ حرفًا إنجليزيًا أو رقمًا أو _ بدون @',
                  );
                  return;
                }
                Navigator.pop(c, true);
              },
              child: const Text('حفظ الاسم'),
            ),
          ],
        ),
      ),
    );
    if (accepted == true && mounted) await rename(confirmed: true);
  }

  Widget entry(IconData icon, String title, VoidCallback action) =>
      settingsEntry(
        context,
        icon: icon,
        title: title,
        onTap: busy ? null : action,
      );
  List<Widget> accountItems() {
    final guest = user['isGuest'] == true,
        providers = security?['providers'] as List? ?? [];
    return [
      Container(
        padding: const EdgeInsets.all(22),
        decoration: BoxDecoration(
          color: settingsSurface(context),
          borderRadius: BorderRadius.circular(14),
        ),
        child: Column(
          children: [
            SettingsAvatar(user: user),
            const SizedBox(height: 12),
            Text(
              user['username']?.toString() ?? '',
              style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 6),
            Text(
              guest
                  ? 'احفظ تقدمك لتجده على أي جهاز'
                  : security?['email']?.toString() ?? '',
              textDirection: guest ? TextDirection.rtl : TextDirection.ltr,
              style: TextStyle(fontSize: 13, color: settingsMuted(context)),
            ),
            if (guest) ...[
              const SizedBox(height: 18),
              FilledButton(
                onPressed: busy ? null : account,
                child: const Text('ربط الحساب أو تسجيل الدخول'),
              ),
            ],
            if (!guest && providers.isNotEmpty) ...[
              const SizedBox(height: 18),
              Divider(color: settingsMuted(context).withValues(alpha: .12)),
              const SizedBox(height: 8),
              Text(
                'طريقة الدخول: ${providers.map((p) => {'google.com': 'Google', 'password': 'البريد وكلمة المرور', 'apple.com': 'Apple'}[p] ?? p).join('، ')}',
                style: TextStyle(fontSize: 12, color: settingsMuted(context)),
              ),
            ],
          ],
        ),
      ),
      if (loading)
        const Padding(
          padding: EdgeInsets.all(16),
          child: Center(child: CircularProgressIndicator()),
        ),
      if (!guest && !loading && security == null)
        TextButton(
          onPressed: openAccount,
          child: const Text('إعادة تحميل بيانات الحساب'),
        ),
      const SizedBox(height: 22),
      settingsGroup(context, [
        settingsEntry(
          context,
          icon: Icons.alternate_email,
          title: 'اسم المستخدم',
          subtitle: user['username']?.toString() ?? '',
          onTap: busy ? null : editUsername,
        ),
        settingsEntry(context,icon:Icons.notes_outlined,title:'نبذة عني',subtitle:user['bio']?.toString()??'',onTap:busy?null:editBio),
        if (providers.contains('password'))
          settingsEntry(
            context,
            icon: Icons.lock_outline,
            title: 'تغيير كلمة المرور عبر البريد',
            onTap: busy ? null : passwordReset,
          ),
      ]),
      Padding(
        padding: const EdgeInsets.fromLTRB(4, 10, 4, 22),
        child: Text(
          user['freeRenameAvailable'] == true
              ? 'تغيير مجاني مرة واحدة. اختر اسمك عندما تكون مستعدًا.'
              : 'بطاقات تغيير الاسم: ${user['renameCredits'] ?? 0} · تتوفر في المتجر.',
          style: TextStyle(fontSize: 12, color: settingsMuted(context)),
        ),
      ),
      if (providers.contains('google.com') && !providers.contains('password'))
        Padding(
          padding: const EdgeInsets.only(bottom: 18),
          child: Text(
            'تُدار كلمة مرور Google من حسابك لدى Google.',
            style: TextStyle(fontSize: 12, color: settingsMuted(context)),
          ),
        ),
      settingsGroup(context, [
        settingsEntry(
          context,
          icon: Icons.logout,
          title: 'تسجيل الخروج والعودة كضيف',
          onTap: busy ? null : logout,
          color: const Color(0xffed4d58),
          trailing: const SizedBox.shrink(),
        ),
        settingsEntry(
          context,
          icon: Icons.delete_outline,
          title: 'حذف الحساب نهائيًا',
          onTap: busy || (!guest && security == null) ? null : deleteAccount,
          color: const Color(0xffb4777e),
          trailing: const SizedBox.shrink(),
        ),
      ]),
    ];
  }

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: section.isEmpty && !busy,
    onPopInvokedWithResult: (didPop, result) {
      if (!didPop && !busy && mounted) setState(() => section = '');
    },
    child: SettingsFrame(
      title: section.isEmpty ? 'الإعدادات' : section,
      onBack: section.isEmpty
          ? null
          : () {
              if (!busy) setState(() => section = '');
            },
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 20, 16, 28),
        children: [
          if (section.isEmpty) ...[
            settingsGroup(context, [
              entry(Icons.person_outline, 'الحساب', openAccount),
              entry(
                Icons.devices_outlined,
                'الأجهزة',
                () => Navigator.push(
                  context,
                  MaterialPageRoute<void>(
                    builder: (_) => AccountDevices(
                      api: widget.api,
                      user: user,
                      onSignedOut: signedOut,
                    ),
                  ),
                ),
              ),
            ]),
            const SizedBox(height: 22),
            settingsGroup(context, [
              if (widget.onTheme != null)
                entry(Icons.palette_outlined, 'المظهر', widget.onTheme!),
              entry(Icons.notifications_none, 'الإشعارات', notifications),
              entry(
                Icons.lock_outline,
                'الخصوصية',
                () => setState(() => section = 'الخصوصية'),
              ),
            ]),
            if (widget.onAdmin != null &&
                {'admin', 'moderator'}.contains(user['role'])) ...[
              const SizedBox(height: 22),
              settingsGroup(context, [
                entry(Icons.admin_panel_settings_outlined, 'الإدارة', () {
                  Navigator.pop(context);
                  widget.onAdmin!();
                }),
              ]),
            ],
            const SizedBox(height: 36),
            Text(
              'Plazr',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 12,
                letterSpacing: 1.4,
                color: settingsMuted(context),
              ),
            ),
          ] else if (section == 'الحساب')
            ...accountItems()
          else if (section == 'الإشعارات') ...[
            if (loading)
              const Center(child: CircularProgressIndicator())
            else if (notices.isEmpty)
              Container(
                padding: const EdgeInsets.symmetric(
                  vertical: 40,
                  horizontal: 20,
                ),
                decoration: BoxDecoration(
                  color: settingsSurface(context),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Column(
                  children: [
                    Icon(
                      Icons.notifications_none,
                      size: 42,
                      color: settingsMuted(context),
                    ),
                    const SizedBox(height: 14),
                    const Text('لا توجد إشعارات حاليًا'),
                    const SizedBox(height: 6),
                    Text(
                      'ستجد هنا جديد حسابك ورسائل المنصة.',
                      style: TextStyle(
                        fontSize: 12,
                        color: settingsMuted(context),
                      ),
                    ),
                  ],
                ),
              )
            else
              settingsGroup(context, [
                for (final notice in notices)
                  ListTile(
                    leading: const Icon(Icons.notifications_none),
                    title: Text(notice['sender']?.toString() ?? 'سيتم'),
                    subtitle: Text(notice['text']?.toString() ?? ''),
                  ),
              ]),
          ] else ...[
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: settingsSurface(context),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'بيانات الحساب والخصوصية',
                    style: TextStyle(fontSize: 17, fontWeight: FontWeight.w600),
                  ),
                  const SizedBox(height: 16),
                  Text(
                    'نستخدم بريد حسابك للتحقق من هويتك واستعادة الدخول. يظهر اسم المستخدم والصورة والمقتنيات العامة للاعبين، ولا يظهر بريدك في ملفك العام.',
                    style: TextStyle(
                      fontSize: 14,
                      height: 1.8,
                      color: settingsMuted(context),
                    ),
                  ),
                  const SizedBox(height: 16),
                  Text(
                    'تسجل قائمة الأجهزة نوع الجهاز وآخر نشاط، والدولة التقريبية عند توفرها. لا نطلب الوصول إلى موقع GPS.',
                    style: TextStyle(
                      fontSize: 14,
                      height: 1.8,
                      color: settingsMuted(context),
                    ),
                  ),
                  const SizedBox(height: 16),
                  Text(
                    'يمكنك إنهاء جلسات أجهزتك من قسم الأجهزة، أو حذف حسابك وبياناته من قسم الحساب.',
                    style: TextStyle(
                      fontSize: 14,
                      height: 1.8,
                      color: settingsMuted(context),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 18),
            settingsGroup(context, [
              entry(
                Icons.manage_accounts_outlined,
                'إدارة الحساب وحذفه',
                openAccount,
              ),
            ]),
          ],
          if (error != null)
            Padding(
              padding: const EdgeInsets.only(top: 16),
              child: Text(
                error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ),
          if (busy)
            const Padding(
              padding: EdgeInsets.only(top: 16),
              child: LinearProgressIndicator(),
            ),
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
    this.user = const {},
  });
  final PlatformApi api;
  final Future<void> Function() onSignedOut;
  final Map<String, dynamic> user;
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

  Future<void> revoke([
    Map<String, dynamic>? device,
    bool confirmed = false,
  ]) async {
    final approved = confirmed
        ? true
        : await showDialog<bool>(
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
  Future<void> details(Map<String, dynamic> device) async {
    final approved = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      showDragHandle: false,
      backgroundColor: settingsSurface(context),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(22)),
      ),
      builder: (c) => Directionality(
        textDirection: TextDirection.rtl,
        child: SafeArea(
          child: SingleChildScrollView(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(22, 14, 22, 22),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Align(
                    alignment: Alignment.centerLeft,
                    child: IconButton(
                      tooltip: 'إغلاق التفاصيل',
                      onPressed: () => Navigator.pop(c, false),
                      icon: Icon(Icons.close, color: settingsMuted(c)),
                    ),
                  ),
                  CircleAvatar(
                    radius: 31,
                    backgroundColor: settingsDeviceColor(device),
                    child: Icon(
                      settingsDeviceIcon(device),
                      color: Colors.white,
                      size: 32,
                    ),
                  ),
                  const SizedBox(height: 14),
                  Text(
                    device['device']?.toString() ?? '',
                    style: const TextStyle(
                      fontSize: 21,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 6),
                  if (device['current'] == true)
                    Text(
                      'هذا الجهاز',
                      style: TextStyle(fontSize: 12, color: settingsMuted(c)),
                    ),
                  const SizedBox(height: 22),
                  for (final row in [
                    ('طريقة الاتصال', device['client']?.toString() ?? ''),
                    ('آخر نشاط', stamp(device['lastSeenAt'])),
                    (
                      'الموقع التقريبي',
                      (device['country'] ?? '') == ''
                          ? 'غير متاح'
                          : device['country'].toString(),
                    ),
                  ])
                    Container(
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      decoration: BoxDecoration(
                        border: Border(
                          top: BorderSide(
                            color: settingsMuted(c).withValues(alpha: .13),
                          ),
                        ),
                      ),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            row.$1,
                            style: TextStyle(
                              fontSize: 13,
                              color: settingsMuted(c),
                            ),
                          ),
                          const SizedBox(width: 18),
                          Expanded(
                            child: Text(
                              row.$2,
                              textAlign: TextAlign.end,
                              style: const TextStyle(fontSize: 13),
                            ),
                          ),
                        ],
                      ),
                    ),
                  const SizedBox(height: 18),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton(
                      onPressed: () => Navigator.pop(c, true),
                      style: FilledButton.styleFrom(
                        backgroundColor: const Color(0xffff414c),
                        foregroundColor: Colors.white,
                        minimumSize: const Size.fromHeight(48),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(11),
                        ),
                      ),
                      child: const Text('تسجيل الخروج'),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
    if (approved == true && mounted) await revoke(device, true);
  }

  @override
  Widget build(BuildContext context) => SettingsFrame(
    title: 'الأجهزة',
    actions: [
      IconButton(
        onPressed: busy || loading ? null : load,
        icon: const Icon(Icons.refresh, size: 22),
        tooltip: 'تحديث الأجهزة',
      ),
    ],
    child: ListView(
      padding: const EdgeInsets.fromLTRB(16, 18, 16, 28),
      children: [
        Center(child: SettingsDevicesIllustration(user: widget.user)),
        const SizedBox(height: 12),
        const Text(
          'حساب واحد، أينما كنت',
          textAlign: TextAlign.center,
          style: TextStyle(fontSize: 22, fontWeight: FontWeight.w600),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 10, 12, 24),
          child: Text(
            'أجهزتك المتصلة بحساب Plazr.\nاختر جهازًا لعرض تفاصيله أو تسجيل خروجه.',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 13,
              height: 1.8,
              color: settingsMuted(context),
            ),
          ),
        ),
        if (loading) const Center(child: CircularProgressIndicator()),
        if (devices.isNotEmpty)
          settingsGroup(context, [
            for (final device in devices)
              ListTile(
                contentPadding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 6,
                ),
                minTileHeight: 76,
                horizontalTitleGap: 14,
                leading: CircleAvatar(
                  radius: 23,
                  backgroundColor: settingsDeviceColor(device),
                  child: Icon(
                    settingsDeviceIcon(device),
                    color: Colors.white,
                    size: 25,
                  ),
                ),
                title: Text(
                  '${device['device']}${device['current'] == true ? ' · هذا الجهاز' : ''}',
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                subtitle: Text(
                  device['client']?.toString() ?? '',
                  style: TextStyle(fontSize: 12, color: settingsMuted(context)),
                ),
                trailing: Icon(
                  Icons.chevron_right,
                  color: settingsMuted(context),
                  size: 22,
                ),
                onTap: busy ? null : () => details(device),
              ),
          ]),
        if (!loading && devices.isEmpty && error == null)
          const Text('لا توجد جلسات نشطة.'),
        if (error != null)
          Text(
            error!,
            style: TextStyle(color: Theme.of(context).colorScheme.error),
          ),
        Padding(
          padding: const EdgeInsets.fromLTRB(4, 12, 4, 22),
          child: Text(
            'الموقع تقريبي وقد يتأثر باستخدام VPN.',
            style: TextStyle(fontSize: 12, color: settingsMuted(context)),
          ),
        ),
        settingsGroup(context, [
          settingsEntry(
            context,
            icon: Icons.logout,
            title: 'تسجيل الخروج من جميع الأجهزة',
            onTap: busy || loading ? null : () => revoke(),
            color: const Color(0xffed4d58),
            trailing: const SizedBox.shrink(),
          ),
        ]),
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
