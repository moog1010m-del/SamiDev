import 'dart:async';
import 'dart:convert';
import 'dart:math';
import 'package:flutter/material.dart';
import '../runtime/api.dart';

/// Native private conversation; all reads and writes use the authorized API.
class DirectConversation extends StatefulWidget {
  const DirectConversation({super.key, required this.api, required this.accountId, required this.peerId});
  final PlatformApi api;
  final String accountId, peerId;
  @override State<DirectConversation> createState() => _DirectConversationState();
}
class _DirectConversationState extends State<DirectConversation> with WidgetsBindingObserver {
  final input = TextEditingController();
  final scroll = ScrollController();
  StreamSubscription<Map<String, dynamic>>? events;
  Timer? retry;
  List<Map<String, dynamic>> messages = [];
  String name = 'المحادثة', error = '', pendingText = '', nonce = '';
  bool loading = true, sending = false, muted = false, paused = false, fetching = false, again = false, accessible = true;
  String get path => '/api/direct/${Uri.encodeComponent(widget.peerId)}';
  @override void initState() { super.initState(); WidgetsBinding.instance.addObserver(this); connect(); unawaited(refresh()); }
  void connect() {
    if (!mounted || paused || events != null) return;
    events = widget.api.events('/api/direct/events').listen((event) { if (event['type'] == 'access_denied') { unawaited(events?.cancel()); events = null; return; } unawaited(refresh()); }, onError: (_) => reconnect(), onDone: reconnect);
  }
  void reconnect() { final old = events; events = null; unawaited(old?.cancel()); retry?.cancel(); if (mounted && !paused) retry = Timer(const Duration(seconds:5), () { connect(); unawaited(refresh()); }); }
  Future<void> refresh() async {
    if (!mounted || paused) return;
    if (fetching) { again = true; return; }
    fetching = true;
    try {
      final response = await widget.api.request('GET', '$path/messages');
      if (!mounted || paused) return;
      if ({401, 403, 404}.contains(response.status)) { setState(() { messages = []; accessible = false; }); }
      if (response.status != 200) throw StateError(response.json['message']?.toString() ?? 'تعذر تحميل المحادثة');
      final data = response.json;
      final next = (data['messages'] as List? ?? []).whereType<Map>().map((m) => Map<String,dynamic>.from(m)).toList();
      final changed = messages.isEmpty || next.isNotEmpty && messages.last['id'] != next.last['id'];
      setState(() { messages = next; name = (data['user'] as Map?)?['username']?.toString() ?? 'المحادثة'; muted = data['muted'] == true; accessible = true; loading = false; error = ''; });
      if (changed) WidgetsBinding.instance.addPostFrameCallback((_) { if (mounted && scroll.hasClients) unawaited(scroll.animateTo(scroll.position.maxScrollExtent, duration:const Duration(milliseconds:180), curve:Curves.easeOut)); });
      await post('read', {'seq': data['seq'] ?? 0});
    } catch (_) { if (mounted) setState(() { loading = false; error = 'تعذر تحديث المحادثة. حاول مجددًا'; }); }
    finally { fetching = false; if (again) { again = false; unawaited(refresh()); } }
  }
  Future<void> post(String operation, Map<String,dynamic> body) async {
    final response = await widget.api.request('POST', '$path/$operation', body:utf8.encode(jsonEncode(body)));
    if (response.status != 200) throw StateError(response.json['message']?.toString() ?? 'تعذر تنفيذ الطلب');
  }
  Future<void> send() async {
    final text = input.text.trim(); if (text.isEmpty || text.length > 2000 || sending || !accessible) return;
    if (pendingText != text || nonce.isEmpty) { pendingText = text; nonce = List.generate(32, (_) => 'abcdefghijklmnopqrstuvwxyz0123456789'[Random.secure().nextInt(36)]).join(); }
    setState(() => sending = true);
    try { await post('messages', {'text':text, 'clientMessageId':nonce}); if (!mounted) return; if (input.text.trim() == text) input.clear(); pendingText = ''; nonce = ''; await refresh(); }
    catch (_) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content:Text('لم يتأكد إرسال الرسالة. أعد المحاولة'))); }
    finally { if (mounted) setState(() => sending = false); }
  }
  Future<void> toggleMute() async { try { await post('mute', {'muted':!muted}); if (mounted) setState(() => muted = !muted); } catch (_) { if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content:Text('تعذر تغيير الكتم'))); } }
  @override void didChangeAppLifecycleState(AppLifecycleState state) { if (state == AppLifecycleState.paused || state == AppLifecycleState.hidden) { paused = true; retry?.cancel(); final old = events; events = null; unawaited(old?.cancel()); } else if (state == AppLifecycleState.resumed) { paused = false; connect(); unawaited(refresh()); } }
  @override void dispose() { WidgetsBinding.instance.removeObserver(this); retry?.cancel(); unawaited(events?.cancel()); input.dispose(); scroll.dispose(); super.dispose(); }
  @override Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;
    return Directionality(textDirection:TextDirection.rtl, child:Scaffold(
      appBar:AppBar(title:Text(name), actions:[IconButton(tooltip:muted?'إلغاء كتم الصديق':'كتم الصديق', onPressed:accessible?toggleMute:null, icon:Icon(muted?Icons.notifications_off_outlined:Icons.notifications_outlined))]),
      body:SafeArea(child:Column(children:[
        if (error.isNotEmpty) MaterialBanner(content:Text(error), actions:[TextButton(onPressed:refresh, child:const Text('إعادة المحاولة'))]),
        Expanded(child:loading?const Center(child:CircularProgressIndicator()):messages.isEmpty?const Center(child:Text('لا توجد رسائل حتى الآن\nابدأ المحادثة برسالة', textAlign:TextAlign.center)):ListView.builder(controller:scroll, padding:const EdgeInsets.all(16), itemCount:messages.length, itemBuilder:(context,index) { final message = messages[index]; final mine = message['senderId'] == widget.accountId; return Align(alignment:mine?Alignment.centerRight:Alignment.centerLeft, child:Container(constraints:BoxConstraints(maxWidth:MediaQuery.sizeOf(context).width * .8), margin:const EdgeInsets.only(bottom:10), padding:const EdgeInsets.symmetric(horizontal:16,vertical:11), decoration:BoxDecoration(color:mine?colors.primaryContainer:colors.surfaceContainerHighest, borderRadius:BorderRadius.circular(18)), child:SelectableText(message['text']?.toString()??'', style:TextStyle(color:mine?colors.onPrimaryContainer:colors.onSurfaceVariant, height:1.45)))); })),
        Padding(padding:const EdgeInsets.fromLTRB(12,8,12,12), child:Row(crossAxisAlignment:CrossAxisAlignment.end, children:[Expanded(child:TextField(controller:input, enabled:accessible, minLines:1, maxLines:5, maxLength:2000, decoration:InputDecoration(hintText:'اكتب رسالة…', counterText:'', filled:true, border:OutlineInputBorder(borderRadius:BorderRadius.circular(24), borderSide:BorderSide.none)))), const SizedBox(width:8), IconButton.filled(tooltip:'إرسال', onPressed:sending||!accessible?null:send, icon:sending?const SizedBox(width:20,height:20,child:CircularProgressIndicator(strokeWidth:2)):const Icon(Icons.send_rounded))])),
      ])),
    ));
  }
}
