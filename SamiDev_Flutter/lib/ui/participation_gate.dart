import 'package:flutter/material.dart';
import '../runtime/api.dart';
import 'legal_page.dart';

/// No account or network session is created by the child until the user agrees.
/// This is acceptance of community rules, not parental consent or age verification.
class ParticipationGate extends StatefulWidget {
  const ParticipationGate({super.key, required this.child, this.vault});
  final Widget child;
  final SessionVault? vault;
  static const revision = '2026-10-19.1';
  static const storageKey = 'plazr.community-rules.$revision';
  @override State<ParticipationGate> createState() => _ParticipationGateState();
}

class _ParticipationGateState extends State<ParticipationGate> {
  late final SessionVault vault = widget.vault ?? SecureSessionVault();
  bool loading = true, agreed = false, accepted = false, saving = false;
  String? error;
  @override void initState() { super.initState(); restore(); }
  Future<void> restore() async {
    try {
      final stored = await vault.read(ParticipationGate.storageKey);
      if (mounted) setState(() { accepted = stored == 'accepted'; loading = false; });
    } catch (_) {
      if (mounted) setState(() => loading = false);
    }
  }
  Future<void> accept() async {
    if (!agreed || saving) return;
    setState(() { saving = true; error = null; });
    try {
      await vault.write(ParticipationGate.storageKey, 'accepted');
      if (mounted) setState(() => accepted = true);
    } catch (_) {
      if (mounted) setState(() => error = 'تعذر حفظ الموافقة. حاول مجددًا.');
    } finally { if (mounted) setState(() => saving = false); }
  }
  @override Widget build(BuildContext context) {
    if (accepted) return widget.child;
    return Scaffold(
      appBar: AppBar(title: const Text('مرحبًا بك في Plazr')),
      body: loading ? const Center(child: CircularProgressIndicator()) : Center(
        child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 620),
          child: ListView(shrinkWrap: true, padding: const EdgeInsets.all(24), children: [
            Text('قبل المشاركة', style: Theme.of(context).textTheme.headlineSmall),
            const SizedBox(height: 16),
            const Text('Plazr منصة ألعاب اجتماعية. قد يرى اللاعبون اسمك وصورتك ونبذتك ورسائلك. لا تنشر معلوماتك الخاصة أو بيانات الآخرين.', style: TextStyle(height: 1.8)),
            const SizedBox(height: 14),
            const Text('نمنع الإساءة والتنمر والكراهية والمحتوى الجنسي والاستغلال والتحرش، خصوصًا أي استغلال أو استدراج للأطفال. يمكنك الإبلاغ عن الحساب أو حظره من بطاقة اللاعب. لا تشارك كلمات المرور أو أرقام التواصل في الشات.', style: TextStyle(height: 1.8)),
            Wrap(children: [
              for (final page in const {'terms': 'شروط الاستخدام', 'privacy': 'سياسة الخصوصية', 'community-guidelines': 'قواعد المجتمع'}.entries)
                TextButton(onPressed: () => Navigator.push(context, MaterialPageRoute<void>(builder: (_) => PlazrLegalPage(pageId: page.key))), child: Text(page.value)),
            ]),
            CheckboxListTile(contentPadding: EdgeInsets.zero, value: agreed,
              onChanged: saving ? null : (value) => setState(() => agreed = value == true),
              title: const Text('أوافق على شروط الاستخدام وقواعد المجتمع، واطلعت على سياسة الخصوصية.')),
            if (error != null) Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
            const SizedBox(height: 16),
            FilledButton(onPressed: agreed && !saving ? accept : null, child: Text(saving ? 'جارٍ الحفظ…' : 'متابعة')),
          ]),
        ),
      ),
    );
  }
}
