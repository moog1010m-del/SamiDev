import 'package:flutter/material.dart';
import '../runtime/api.dart';
import 'children_home.dart';

/// Neutral, local-only age screen. It is not identity or parental verification.
class AudienceGate extends StatefulWidget {
  const AudienceGate({super.key, required this.child, this.vault, this.clock, this.restrictedChild});
  final Widget child;
  final Widget? restrictedChild;
  final SessionVault? vault;
  final DateTime Function()? clock;
  static const storageKey = 'plazr.audience-band.v1';
  static String? classify(String day, String month, String year, DateTime now) {
    String digits(String s) { const arabic = '٠١٢٣٤٥٦٧٨٩', persian = '۰۱۲۳۴۵۶۷۸۹'; return s.trim().split('').map((c) => arabic.contains(c) ? '${arabic.indexOf(c)}' : persian.contains(c) ? '${persian.indexOf(c)}' : c).join(); }
    final d = int.tryParse(digits(day)), m = int.tryParse(digits(month)), y = int.tryParse(digits(year));
    if (d == null || m == null || y == null || y < 1900 || y > now.year || m < 1 || m > 12 || d < 1 || d > 31) return null;
    final dob = DateTime(y, m, d), today = DateTime(now.year, now.month, now.day);
    if (dob.year != y || dob.month != m || dob.day != d || dob.isAfter(today)) return null;
    var age = today.year - y;
    if (today.month < m || (today.month == m && today.day < d)) age--;
    return age < 13 ? 'restricted' : 'general';
  }
  @override State<AudienceGate> createState() => _AudienceGateState();
}
class _AudienceGateState extends State<AudienceGate> {
  late final SessionVault vault = widget.vault ?? SecureSessionVault();
  final day = TextEditingController(), month = TextEditingController(), year = TextEditingController();
  bool loading = true, saving = false, storageFailed = false;
  String? band, error;
  @override void initState() { super.initState(); restore(); }
  Future<void> restore() async {
    setState(() { loading = true; error = null; storageFailed = false; });
    try {
      final stored = await vault.read(AudienceGate.storageKey);
      if (mounted) setState(() { band = {'restricted', 'general'}.contains(stored) ? stored : null; loading = false; });
    } catch (_) { if (mounted) setState(() { loading = false; storageFailed = true; error = 'تعذر قراءة الإعدادات المحلية. أعد المحاولة للمتابعة.'; }); }
  }
  Future<void> submit() async {
    if (saving || storageFailed) return;
    final value = AudienceGate.classify(day.text, month.text, year.text, widget.clock?.call() ?? DateTime.now());
    if (value == null) { setState(() => error = 'أدخل تاريخ ميلاد صحيحًا.'); return; }
    setState(() { saving = true; error = null; });
    try {
      await vault.write(AudienceGate.storageKey, value);
      // Never persist or transmit the date of birth.
      day.clear(); month.clear(); year.clear();
      if (mounted) setState(() => band = value);
    } catch (_) { if (mounted) setState(() { storageFailed = true; error = 'تعذر حفظ إعدادات التجربة. أعد المحاولة.'; }); }
    finally { if (mounted) setState(() => saving = false); }
  }
  @override void dispose() { day.dispose(); month.dispose(); year.dispose(); super.dispose(); }
  @override Widget build(BuildContext context) {
    if (band == 'restricted') return widget.restrictedChild ?? const ChildrenHome();
    if (band == 'general') return widget.child;
    return Scaffold(appBar: AppBar(title: const Text('مرحبًا بك في Plazr')), body: loading ? const Center(child: CircularProgressIndicator()) : Center(
      child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 560), child: ListView(shrinkWrap: true, padding: const EdgeInsets.all(24), children: [
        Text('تاريخ الميلاد', style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 16),
        const Text('نستخدمه داخل الجهاز لاختيار التجربة المناسبة. لا نحفظ تاريخ ميلادك ولا نرسله إلى الخادم؛ نحفظ فئة التجربة فقط.', style: TextStyle(height: 1.8)),
        const SizedBox(height: 24),
        Row(children: [
          Expanded(child: TextField(controller: day, keyboardType: TextInputType.number, maxLength: 2, decoration: const InputDecoration(labelText: 'اليوم', counterText: ''))), const SizedBox(width: 12),
          Expanded(child: TextField(controller: month, keyboardType: TextInputType.number, maxLength: 2, decoration: const InputDecoration(labelText: 'الشهر', counterText: ''))), const SizedBox(width: 12),
          Expanded(child: TextField(controller: year, keyboardType: TextInputType.number, maxLength: 4, decoration: const InputDecoration(labelText: 'السنة', counterText: ''))),
        ]),
        if (error != null) Padding(padding: const EdgeInsets.symmetric(vertical: 16), child: Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error))),
        const SizedBox(height: 24),
        FilledButton(onPressed: saving || storageFailed ? null : submit, child: Text(saving ? 'جارٍ الحفظ…' : 'متابعة')),
        if (storageFailed) TextButton(onPressed: restore, child: const Text('إعادة المحاولة')),
      ])),
    ));
  }
}
