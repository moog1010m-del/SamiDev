import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'package:webview_flutter_android/webview_flutter_android.dart';
import '../runtime/child_runtime.dart';
import '../runtime/game_haptics.dart';
import 'legal_page.dart';

class ChildrenHome extends StatelessWidget {
  const ChildrenHome({super.key});
  @override Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Plazr · اللعب المحلي')),
    body: Center(child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 760), child: ListView(padding: const EdgeInsets.all(24), children: [
      Text('نلعب على نفس الجهاز', style: Theme.of(context).textTheme.headlineSmall),
      const SizedBox(height: 12),
      const Text('مرّر الجهاز للاعب الآخر عندما يأتي دوره. لا تحتاج حسابًا أو اتصالًا بالإنترنت، ولا يوجد شات أو أشخاص من خارج الجهاز.', style: TextStyle(height: 1.8)),
      const SizedBox(height: 24),
      for (final game in const {'pool': 'البلياردو', 'carrom': 'الكيرم', 'tablesoccer': 'كرة الطاولة'}.entries)
        Padding(padding: const EdgeInsets.only(bottom: 14), child: Card(child: ListTile(
          contentPadding: const EdgeInsets.all(20), leading: const Icon(Icons.sports_esports_outlined),
          title: Text(game.value), subtitle: const Text('لعب محلي على نفس الجهاز'), trailing: const Icon(Icons.chevron_left),
          onTap: () => Navigator.push(context, MaterialPageRoute<void>(builder: (_) => ChildGameScreen(game: game.key, title: game.value))),
        ))),
      const SizedBox(height: 14),
      const Text('النتائج تبقى داخل جلسة اللعب ولا تُضاف إلى حساب أو عملات أو ترتيب عام. أونو غير متاحة في الوضع المحلي حاليًا.', style: TextStyle(height: 1.8)),
      const SizedBox(height: 16),
      const Text('للأهل: هذا الوضع لا يجمع اسمًا أو صورة أو بريدًا، ولا يتيح التواصل أو خدمات الذكاء الاصطناعي أو المتجر. لم نفتح الوصول الاجتماعي بمربع موافقة أو سؤال حسابي؛ يحتاج مسارًا مستقلاً للتحقق من ولي الأمر.', style: TextStyle(height: 1.8)),
      Wrap(children: [
        TextButton(onPressed: () => Navigator.push(context, MaterialPageRoute<void>(builder: (_) => const PlazrLegalPage(pageId: 'children'))), child: const Text('الأطفال والخصوصية')),
        TextButton(onPressed: () => Navigator.push(context, MaterialPageRoute<void>(builder: (_) => const PlazrLegalPage(pageId: 'contact'))), child: const Text('التواصل مع الدعم')),
      ]),
    ]))),
  );
}

class ChildGameScreen extends StatefulWidget {
  const ChildGameScreen({super.key, required this.game, required this.title});
  final String game, title;
  @override State<ChildGameScreen> createState() => _ChildGameScreenState();
}
class _ChildGameScreenState extends State<ChildGameScreen> with WidgetsBindingObserver {
  final gameHaptics=GameHaptics();
  bool _background=false;
  ChildRuntime? runtime;
  WebViewController? controller;
  bool loading = true;
  String? error;
  @override void initState() { super.initState(); WidgetsBinding.instance.addObserver(this); unawaited(start()); }
  Future<void> start() async {
    gameHaptics.cancel();
    final old = runtime;
    await old?.close();
    final r = ChildRuntime(widget.game); runtime = r;
    if (mounted) setState(() { controller = null; error = null; loading = true; });
    try {
      await r.start();
      if (!mounted || runtime != r) { await r.close(); return; }
      final c = WebViewController(onPermissionRequest: (request) => request.deny());
      await c.setJavaScriptMode(JavaScriptMode.unrestricted);
      await c.enableZoom(false);
      await c.setBackgroundColor(const Color(0xff171717));
      if (c.platform is AndroidWebViewController) {
        await AndroidWebViewController.enableDebugging(!kReleaseMode);
        final android = c.platform as AndroidWebViewController;
        await android.setMediaPlaybackRequiresUserGesture(true);
        await android.setOnShowFileSelector((_) async => <String>[]);
      }
      await c.addJavaScriptChannel('SamiDevMobile', onMessageReceived: (message) {
        if (!mounted || runtime != r) return;
        if(message.message.length>5000)return;
        try{final data=jsonDecode(message.message);if(data is Map&&data['type']=='game_haptic'){if(data['action']=='cancel'){gameHaptics.cancel();}else if(!_background){gameHaptics.play(data);}return;}}catch(_){}
        // Only local haptics: no profile, copy, invite, navigation or API bridge.
        if (message.message == '{"type":"game_surface_ready"}') setState(() => loading = false);
        if (message.message == '{"type":"game_surface_error"}') setState(() { loading = false; error = 'تعذر تشغيل اللعبة محليًا. حاول مجددًا.'; });
      });
      await c.setNavigationDelegate(NavigationDelegate(
        onNavigationRequest: (request) {
          final uri = Uri.tryParse(request.url);
          return mounted && runtime == r && uri != null && r.allowsNavigation(uri) ? NavigationDecision.navigate : NavigationDecision.prevent;
        },
        onWebResourceError: (failure) { if (mounted && runtime == r && failure.isForMainFrame == true) setState(() { loading = false; error = 'تعذر تحميل ملفات اللعبة من الجهاز.'; }); },
      ));
      if (!mounted || runtime != r) { await r.close(); return; }
      setState(() => controller = c);
      await c.loadRequest(r.launch);
    } catch (_) { if (mounted && runtime == r) setState(() { loading = false; error = 'تعذر تشغيل اللعبة. حاول مجددًا.'; }); }
  }
  @override void didChangeAppLifecycleState(AppLifecycleState state) {
    _background=state!=AppLifecycleState.resumed;if(_background)gameHaptics.cancel();
    final c = controller;
    if (c != null) unawaited(c.runJavaScript(state == AppLifecycleState.resumed ? 'window.audio?.resume?.();' : 'window.audio?.suspend?.();').catchError((_) {}));
  }
  @override void dispose() {
    gameHaptics.dispose();
    WidgetsBinding.instance.removeObserver(this);
    final c = controller, r = runtime;
    unawaited(() async { try { await c?.clearLocalStorage(); } catch (_) {} finally { await r?.close(); } }());
    super.dispose();
  }
  @override Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Text('محلي · ${widget.title}'), bottom: loading ? const PreferredSize(preferredSize: Size.fromHeight(4), child: LinearProgressIndicator()) : null),
    body: error != null ? Center(child: Column(mainAxisSize: MainAxisSize.min, children: [Text(error!), const SizedBox(height: 12), FilledButton(onPressed: start, child: const Text('إعادة المحاولة'))]))
      : controller == null ? const Center(child: Text('تحميل اللعبة من الجهاز…')) : WebViewWidget(controller: controller!),
  );
}
