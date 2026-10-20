import 'dart:async';
import 'dart:convert';
import 'dart:math';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';
import 'package:webview_flutter/webview_flutter.dart';
import 'package:webview_flutter_android/webview_flutter_android.dart';
import 'package:webview_flutter_wkwebview/webview_flutter_wkwebview.dart';
import 'runtime/api.dart';
import 'runtime/game_runtime.dart';
import 'runtime/game_haptics.dart';
import 'runtime/policy.dart';
import 'runtime/failures.dart';
import 'runtime/retained_table.dart';
import 'ui/player_profile.dart';
import 'ui/community_hub.dart';
import 'ui/game_viewport.dart';
import 'ui/chat_cosmetic.dart';
import 'ui/chat_stickers.dart';
import 'ui/sticker_art.dart';
import 'ui/games_hub.dart';
import 'ui/auth_screen.dart';
import 'ui/account_settings.dart';
import 'ui/participation_gate.dart';
import 'ui/audience_gate.dart';
import 'runtime/native_auth.dart';
import 'runtime/friend_notifications.dart';
import 'ui/friend_banner.dart';

final appTheme=ValueNotifier<ThemeMode>(ThemeMode.system);
Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  try{final saved=await SecureSessionVault().read('samidev.appearance');appTheme.value=saved=='light'?ThemeMode.light:saved=='dark'?ThemeMode.dark:ThemeMode.system;}catch(_){}
  runApp(const SamiDevApp());
}
class SamiDevApp extends StatelessWidget {
  const SamiDevApp({super.key});
  ThemeData theme(Brightness brightness){
    final dark=brightness==Brightness.dark;
    final colors=ColorScheme.fromSeed(seedColor:const Color(0xff1976d2),brightness:brightness).copyWith(
      primary:const Color(0xff2385dc),surface:dark?const Color(0xff111111):const Color(0xfffafafa),
      surfaceContainerLow:dark?const Color(0xff171717):Colors.white,surfaceContainerHighest:dark?const Color(0xff303030):const Color(0xffe9edf0));
    return ThemeData(colorScheme:colors,scaffoldBackgroundColor:colors.surface,useMaterial3:true,
      appBarTheme:AppBarTheme(backgroundColor:colors.surface,surfaceTintColor:Colors.transparent),
      dividerColor:dark?const Color(0xff222222):const Color(0xffe2e5e8),
      navigationBarTheme:NavigationBarThemeData(backgroundColor:colors.surface,height:64,indicatorColor:colors.primary.withValues(alpha:.13)));
  }
  @override Widget build(BuildContext context)=>ValueListenableBuilder<ThemeMode>(valueListenable:appTheme,builder:(_,mode,__)=>MaterialApp(
    debugShowCheckedModeBanner:false,title:'Plazr',theme:theme(Brightness.light),darkTheme:theme(Brightness.dark),themeMode:mode,
    builder:(context,child)=>Directionality(textDirection:TextDirection.rtl,child:child!),home:const AudienceGate(child:ParticipationGate(child:PlatformScreen()))));
}
class PlatformScreen extends StatefulWidget {
  const PlatformScreen({super.key,this.runtimeFactory});
  final GameRuntime Function()? runtimeFactory;
  @override State<PlatformScreen> createState()=>_PlatformScreenState();
}
class _PlatformScreenState extends State<PlatformScreen> with WidgetsBindingObserver {
  GameRuntime? runtime;
  FriendNotifications? friendNotifications;
  OverlayEntry? friendBanner;
  String? pendingFriendId;
  bool pendingFriendRequests=false,changingPhoneNotifications=false;
  WebViewController? controller,gameController;
  final table=RetainedTable();
  final gameHaptics=GameHaptics();
  Uri? gameCurrent;
  int gameProgress=0;
  bool _openingGame=false,_profileOpen=false,_returnToGames=false,_awaitingGameSurface=false;
  Completer<bool>? _gameSurfaceReady;
  bool _entryFrameReady=false,_entryAdmitted=false;
  String? _entryFailure;
  StreamSubscription<Map<String,dynamic>>? subscription;
  final input=TextEditingController(),chatScroll=ScrollController();
  final List<Map<String,dynamic>> messages=[];
  String? error;
  String room='';
  String? notifiedMatch;
  bool? notifiedMineTurn;
  final chatPendingTimers=<String,Timer>{};
  bool loading=true,inGame=false,showChat=false,sending=false,authenticated=false;
  String? webPage;String role='user';int selectedTab=0;
  Map<String,dynamic>? gamesProfile;
  final hubKey=GlobalKey<CommunityHubState>(),gamesKey=GlobalKey<GamesHubState>(),chatFocus=FocusNode();
  bool _lastDark=true;
  bool get nativeGames=>authenticated&&(!inGame||_awaitingGameSurface)&&webPage=='games';
  bool get nativeHome=>authenticated&&(!inGame||_awaitingGameSurface)&&(webPage==null||nativeGames);
  int progress=0;
  Uri? current;
  bool _starting=false, _background=false;
  @override void initState(){super.initState();WidgetsBinding.instance.addObserver(this);chatFocus.addListener(()=>mounted?setState((){}):null);unawaited(start());}
  @override void didChangeDependencies(){super.didChangeDependencies();final dark=Theme.of(context).brightness==Brightness.dark;if(dark!=_lastDark){_lastDark=dark;unawaited(syncTheme());}if(MediaQuery.sizeOf(context).shortestSide<600){unawaited(SystemChrome.setPreferredOrientations([DeviceOrientation.portraitUp]));}}
  Future<void> start() async {
    if(_starting)return;_starting=true;
    if(mounted)setState((){error=null;loading=true;authenticated=false;controller=null;current=null;gamesProfile=null;webPage=null;selectedTab=0;role='user';});
    try {
      dismissFriendBanner();await friendNotifications?.stop();friendNotifications=null;
      await discardGame();await subscription?.cancel();await runtime?.close();
      final r=widget.runtimeFactory?.call()??GameRuntime(PlatformApi(
        RuntimePolicy(const String.fromEnvironment('SAMIDEV_SERVER_URL'),allowLocalDevelopment:const bool.fromEnvironment('SAMIDEV_LOCAL_DEV')),SecureSessionVault()));runtime=r;
      await r.start();if(!mounted)return;
      subscription=r.events.stream.listen(onEvent);
      await NativeAuth(r.api).prepare();
      final auth=NativeAuth(r.api);
      final user=await auth.restore()??await auth.guest();
      if(!mounted||runtime!=r)return;
      await completeAuthentication(r,user);
      if(_background)await r.suspend();
      if(mounted)setState(()=>loading=false);
    }catch(e){if(mounted)setState(()=>error=e is FormatException?e.message:e is StateError?e.message.toString():e is AuthFailure?e.message:RuntimeFailure.from(e).toString());}
    finally{_starting=false;}
  }
  Future<void> completeAuthentication(GameRuntime r,Map<String,dynamic> user) async {
    if(!mounted||runtime!=r||!r.api.signedIn)return;
    final fresh=controller==null;
    final c=controller??await makeController(r,game:false);
    if(!mounted||runtime!=r)return;
    controller=c;
    await c.loadRequest(fresh?r.launch:r.origin.replace(path:'/platform/'));
    if(!mounted||runtime!=r||!r.api.signedIn)return;
    setState((){authenticated=true;gamesProfile=user;role=user['role']?.toString()??'user';webPage=null;selectedTab=0;});
    if(friendNotifications?.accountId!=user['id']){
      await friendNotifications?.stop();dismissFriendBanner();
      final notifications=FriendNotifications(r.api,user['id'] as String,onMessage:showFriendBanner,onRequests:(){if(inGame)parkGame();setState(()=>selectedTab=1);pendingFriendId=null;pendingFriendRequests=true;unawaited(openPage('friends'));},onOpen:(id)=>unawaited(openFriendConversation(id)),onUpdate:(){if(mounted&&webPage=='friends')unawaited(controller?.runJavaScript('window.SamiDevMobilePlatform?.refreshFriends();').catchError((_){ }));});
      friendNotifications=notifications;unawaited(notifications.start());
    }
    unawaited(configurePlatform());
  }
  void dismissFriendBanner(){friendBanner?.remove();friendBanner=null;}
  void showFriendBanner(Map<String,dynamic> thread){
    if(!mounted||_background||!authenticated||webPage=='friends')return;
    final user=Map<String,dynamic>.from(thread['user'] as Map),message=Map<String,dynamic>.from(thread['lastMessage'] as Map);
    dismissFriendBanner();
    friendBanner=OverlayEntry(builder:(_)=>FriendBanner(username:user['username']?.toString()??'صديق',text:message['text']?.toString()??'رسالة جديدة',onDismiss:dismissFriendBanner,onOpen:(){dismissFriendBanner();unawaited(openFriendConversation(user['id'] as String));}));
    Overlay.of(context).insert(friendBanner!);
  }
  Future<void> openFriendConversation(String id) async {
    if(!mounted||runtime==null||!authenticated)return;
    if(inGame)parkGame();pendingFriendRequests=false;pendingFriendId=id;setState(()=>selectedTab=1);await openPage('friends');
  }
  Future<void> phoneNotifications(bool enable) async {
    if(changingPhoneNotifications)return;changingPhoneNotifications=true;
    try{final text=enable?await friendNotifications?.enable():await friendNotifications?.disable();if(mounted&&text!=null&&text.isNotEmpty)notify(text);}catch(_){if(mounted)notify('تعذر تفعيل الإشعارات. تحقق من اتصال الهاتف وإعدادات Firebase.');}finally{changingPhoneNotifications=false;}
  }
  Future<WebViewController> makeController(GameRuntime r,{required bool game}) async {
    PlatformWebViewControllerCreationParams params=const PlatformWebViewControllerCreationParams();
    if(WebViewPlatform.instance is WebKitWebViewPlatform){params=WebKitWebViewControllerCreationParams(allowsInlineMediaPlayback:true,mediaTypesRequiringUserAction:const <PlaybackMediaTypes>{});}
    final c=WebViewController.fromPlatformCreationParams(params);
    bool live()=>mounted&&runtime==r&&(game?gameController==c:controller==c);
    Uri? page()=>game?gameCurrent:current;
    await c.setJavaScriptMode(JavaScriptMode.unrestricted);await c.enableZoom(false);
    await c.setBackgroundColor(_lastDark?const Color(0xff111111):const Color(0xfffafafa));
    if(c.platform is AndroidWebViewController){
      await AndroidWebViewController.enableDebugging(!kReleaseMode);
      final android=c.platform as AndroidWebViewController;
      await android.setMediaPlaybackRequiresUserGesture(false);
      await android.setOnShowFileSelector((params) async {
        if(!live()||game||page()==null||!r.owns(page()!))return [];
        final photo=await ImagePicker().pickImage(source:ImageSource.gallery,maxWidth:1024,maxHeight:1024,imageQuality:90);
        return photo==null?<String>[]:[Uri.file(photo.path).toString()];
      });
    }
    await c.addJavaScriptChannel('SamiDevMobile',onMessageReceived:(message){
      if(!live()||page()==null||!r.owns(page()!)||message.message.length>5000)return;
      try{final data=jsonDecode(message.message) as Map;
        if(data['type']=='copy'&&data['text'] is String){unawaited(copyText(data['text'] as String));}
        if(game&&data['type']=='game_surface_ready'&&_gameSurfaceReady?.isCompleted==false){_entryFrameReady=true;completeGameEntry();}
        if(game&&data['type']=='game_surface_error'&&_gameSurfaceReady?.isCompleted==false){_entryFailure=data['code']=='MATCH_COOLDOWN'?'حاول بعد دقيقة':'تعذر فتح الطاولة. حاول مجددًا.';_gameSurfaceReady!.complete(false);}
        if(game&&data['type']=='game_haptic'){if(data['action']=='cancel'){gameHaptics.cancel();}else if(!_background&&inGame){gameHaptics.play(data);}}
        if(game&&data['type']=='room_background'){parkGame();}
        if(game&&data['type']=='game_runtime_ready'){
          final suspend=_background||!inGame?' window.audio?.suspend?.();':'';
          unawaited(c.runJavaScript("document.querySelector('.sd-inventory-trigger')?.setAttribute('hidden','');$suspend").catchError((_){ }));
        }
        if(game&&data['type']=='open_player_profile'&&data['userId'] is String){
          final id=data['userId'] as String;
          if(table.roster.any((p)=>p['accountId']==id))openProfile(id);
        }
        if(!game&&data['type']=='platform_ready'&&authenticated&&r.api.signedIn){unawaited(configurePlatform());}
        if(!game&&data['type']=='open_settings'&&authenticated){unawaited(openAccountSettings());}
        if(!game&&data['type']=='friend_push_enable'&&authenticated){unawaited(phoneNotifications(true));}
        if(!game&&data['type']=='friend_push_disable'&&authenticated){unawaited(phoneNotifications(false));}
        if(!game&&data['type']=='native_home'){setState((){webPage=null;selectedTab=0;});unawaited(configurePlatform());}
      }catch(_){}
    });
    await c.setNavigationDelegate(NavigationDelegate(
      onNavigationRequest:(request){
        final uri=Uri.tryParse(request.url);
        // Only controller disposal may replace the old document with an inert page.
        if(!live())return request.url=='about:blank'?NavigationDecision.navigate:NavigationDecision.prevent;
        if(uri==null||!request.isMainFrame||!r.allowsNavigation(uri))return NavigationDecision.prevent;
        if(!game&&RuntimePolicy.isGame(uri.path)){unawaited(openGameUri(uri));return NavigationDecision.prevent;}
        if(game&&!RuntimePolicy.isGame(uri.path)){unawaited(discardGame());return NavigationDecision.prevent;}
        final cid=uri.queryParameters['community'];if(RuntimePolicy.isCommunityId(cid))r.community=cid!;
        return NavigationDecision.navigate;
      },
      onPageStarted:(url){if(!live())return;final uri=Uri.tryParse(url);if(uri==null)return;
        setState((){if(game){gameCurrent=uri;gameProgress=0;}else{current=uri;progress=0;}});
      },
      onProgress:(value){if(live())setState((){if(game){gameProgress=value;}else{progress=value;}});},
      onPageFinished:(_) async {
        if(!live())return;
        try{
          await c.runJavaScript("document.querySelector('.sd-inventory-trigger')?.setAttribute('hidden',''); window.__SAMIDEV_MOBILE_APP=true; if(navigator.clipboard){navigator.clipboard.writeText=async function(text){SamiDevMobile.postMessage(JSON.stringify({type:'copy',text:String(text)}));};}");
          await syncTheme();if(!game)await configurePlatform();
          if(_background||game&&!inGame)await c.runJavaScript('window.audio?.suspend?.();');
        }catch(_){}
      },
      onWebResourceError:(e){if(e.isForMainFrame==true&&live()){if(game){unawaited(discardGame());notify('تعذر فتح الطاولة. تحقق من الاتصال وحاول مجددًا.');}else{setState(()=>error='تعذر فتح الصفحة. تحقق من الاتصال وأعد المحاولة.');}}},
    ));
    return c;
  }
  Future<void> manageTable(String operation,int? target) async {
    if(gameController==null||table.begun||table.ownerSeat!=table.seat)return;
    final accepted=await showDialog<bool>(context:context,builder:(context)=>AlertDialog(
      title:Text(operation=='close'?'إغلاق الطاولة؟':'إخراج اللاعب قبل بدء اللعب؟'),actions:[
        TextButton(onPressed:()=>Navigator.pop(context,false),child:const Text('إلغاء')),
        FilledButton(onPressed:()=>Navigator.pop(context,true),child:const Text('تأكيد'))]));
    if(accepted!=true||!mounted||gameController==null)return;
    final packet={'type':'manage_table','action':operation,'targetSeat':target??-1};
    try{final sent=await gameController!.runJavaScriptReturningResult('window.SamiDevNetwork?.send(${jsonEncode(packet)})??false');if(sent==false||sent=='false')notify('انقطع الاتصال؛ أعد المحاولة بعد عودته');}catch(_){if(mounted)notify('تعذر إرسال الإجراء؛ حاول مجددًا');}
  }
  void notifyGame(String message){
    if(!mounted||gameController==null)return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content:Text(message),duration:const Duration(seconds:5),action:!inGame?SnackBarAction(label:'العودة للمباراة',onPressed:resumeGame):null));
  }
  void parkGame(){
    gameHaptics.cancel();
    if(!mounted||gameController==null)return;
    chatFocus.unfocus();
    setState((){inGame=false;showChat=false;webPage=_returnToGames?'games':null;selectedTab=_returnToGames?2:0;});
    final cid=table.communityId.isNotEmpty?table.communityId:runtime!.community;
    if(!_returnToGames){hubKey.currentState?.restoreCommunity(cid);}else{unawaited(refreshGamesProfile());}
    unawaited(gameController!.runJavaScript('window.audio?.suspend?.();').catchError((_){ }));
    unawaited(configurePlatform());
  }
  void resumeGame(){
    if(!mounted||gameController==null)return;
    FocusManager.instance.primaryFocus?.unfocus();
    setState(()=>inGame=true);unawaited(gameController!.runJavaScript('window.audio?.resume?.();').catchError((_){ }));unawaited(configurePlatform());
  }
  Future<void> discardGame() async {
    gameHaptics.cancel();
    final old=gameController;
    if(_gameSurfaceReady?.isCompleted==false)_gameSurfaceReady!.complete(false);
    _awaitingGameSurface=false;
    if(old==null)return;
    chatFocus.unfocus();
    for(final timer in chatPendingTimers.values){timer.cancel();}chatPendingTimers.clear();
    if(mounted)setState((){gameController=null;gameCurrent=null;inGame=false;room='';messages.clear();table.clear();showChat=false;webPage=_returnToGames?'games':null;selectedTab=_returnToGames?2:0;});
    // Dispose the old JavaScript context too, so its automatic reconnect cannot
    // recreate a socket after logout/explicit exit. Parking never calls this.
    try{await old.runJavaScript("window.SamiDevGameRuntime?.dispose?.(); window.audio?.suspend?.(); if(window.SamiDevNetwork){window.SamiDevNetwork.state.intentionalClose=true;window.SamiDevNetwork.state.ws?.close(1000,'view closed');}");await old.loadHtmlString('<!doctype html><html><body></body></html>');}catch(_){}
    await configurePlatform();
    if(_returnToGames&&authenticated)unawaited(refreshGamesProfile());
  }
  void notify(String message){if(mounted)ScaffoldMessenger.of(context).showSnackBar(SnackBar(content:Text(message),behavior:message=='حاول بعد دقيقة'?SnackBarBehavior.floating:null));}
  void completeGameEntry(){
    if(_entryFrameReady&&_entryAdmitted&&_gameSurfaceReady?.isCompleted==false){setState(()=>_awaitingGameSurface=false);_gameSurfaceReady!.complete(true);}
  }
  void onEvent(Map<String,dynamic> event){
    if(!mounted)return;
    if(_awaitingGameSurface&&event['type']=='error'&&_gameSurfaceReady?.isCompleted==false){_entryFailure=event['code']=='MATCH_COOLDOWN'?'حاول بعد دقيقة':(event['message']?.toString()??'تعذر فتح الطاولة');_gameSurfaceReady!.complete(false);return;}
    if(_awaitingGameSurface&&{'created','joined','watching'}.contains(event['type'])&&(event['roomId']?.toString().isNotEmpty??false)){_entryAdmitted=true;completeGameEntry();}
    final firstBegin=event['type']=='begin_match'&&notifiedMatch!=event['roomId'];
    if(firstBegin)notifiedMatch=event['roomId']?.toString();
    if({'created','joined','watching','room_state','begin_match'}.contains(event['type'])&&gameController!=null){
      final newcomers=table.apply(event);
      setState(()=>room=table.roomId);
      if(RuntimePolicy.isCommunityId(table.communityId)){runtime?.community=table.communityId;if(!_returnToGames)hubKey.currentState?.restoreCommunity(table.communityId);}
      if(!inGame&&!_background&&newcomers.isNotEmpty){
        final names=newcomers.map((p)=>p['name'].toString()).join('، ');
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content:Text('انضم $names إلى طاولتك'),
          duration:const Duration(seconds:6),action:SnackBarAction(label:'العودة للطاولة',onPressed:resumeGame)));
        unawaited(HapticFeedback.lightImpact());
      }
    }
    if(firstBegin&&gameController!=null&&!_background){notifyGame('بدأت المباراة');unawaited(HapticFeedback.lightImpact());}
    switch(event['type']){
      case 'game_turn':if(gameController!=null){final mine=event['gameOver']!=true&&(event['turn'] as List? ?? []).contains(table.seat);if(mine&&notifiedMineTurn!=true&&!_background&&(!inGame||showChat)){notifyGame('دورك الآن في المباراة');unawaited(HapticFeedback.lightImpact());}notifiedMineTurn=mine;}

      case 'chat_history':if(gameController!=null){setState((){messages.clear();messages.addAll((event['messages'] as List? ?? []).whereType<Map>().map((x)=>Map<String,dynamic>.from(x)).take(80));});scrollChat();}
      case 'chat_pending':if(gameController!=null){final nonce=event['clientMessageId'];if(!messages.any((m)=>m['clientMessageId']==nonce)){final pending=<String,dynamic>{...event,'id':'pending_$nonce','seat':table.seat,'pending':true,'chatBubble':gamesProfile?['chatBubble'],'stickerAsset':event['previewAsset']};setState(()=>messages.add(pending));scrollChat();chatPendingTimers[nonce]?.cancel();chatPendingTimers[nonce]=Timer(const Duration(seconds:8),(){chatPendingTimers.remove(nonce);if(mounted&&messages.contains(pending)){setState(()=>pending['failed']=true);}});}}
      case 'chat_message':if(gameController!=null){chatPendingTimers.remove(event['clientMessageId'])?.cancel();setState((){messages.removeWhere((m)=>m['pending']==true&&m['seat']==event['seat']&&m['clientMessageId']==event['clientMessageId']);messages.add(event);if(messages.length>80)messages.removeAt(0);});scrollChat();}
      case 'invite_created':final token=event['inviteToken'];if(token is String&&RegExp(r'^[A-Za-z0-9_-]{20,64}$').hasMatch(token)){unawaited(copyText(runtime!.api.policy.backend.replace(path:'/platform/',queryParameters:{'invite':token}).toString()));}
      case 'left_room':if({'ROOM_WAIT_EXPIRED','TABLE_CLOSED','TABLE_KICKED','COMMUNITY_BANNED','COMMUNITY_KICKED','COMMUNITY_DISABLED'}.contains(event['reason'])){unawaited(discardGame());notify(event['message']?.toString()??'أُغلقت الطاولة');}
      case 'error':if(event['clientMessageId']!=null){setState((){for(final m in messages){if(m['pending']==true&&m['clientMessageId']==event['clientMessageId'])m['failed']=true;}});}notify(event['message']?.toString()??'تعذر تنفيذ العملية');
      case 'auth_expired':final hadSession=authenticated||gameController!=null;unawaited(discardGame());setState((){authenticated=false;gamesProfile=null;webPage=null;selectedTab=0;});unawaited(controller?.runJavaScript('window.SamiDevMobilePlatform?.setNativeActive(true);'));if(hadSession){notify('انتهت الجلسة. يمكنك الدخول إلى حسابك من الإعدادات.');}unawaited(start());
    }
  }
  void scrollChat(){WidgetsBinding.instance.addPostFrameCallback((_){if(chatScroll.hasClients)unawaited(chatScroll.animateTo(chatScroll.position.maxScrollExtent,duration:const Duration(milliseconds:160),curve:Curves.easeOut));});}
  Future<void> copyText(String text) async {
    if(text.length>4096)return;
    final uri=Uri.tryParse(text);if(uri!=null&&runtime!.owns(uri))text=runtime!.api.policy.backend.replace(path:uri.path,query:uri.query).toString();
    await Clipboard.setData(ClipboardData(text:text));notify('تم النسخ');
  }
  Future<void> sendGameSticker() async {
    final r=runtime,c=gameController;if(r==null||c==null)return;
    final item=await pickChatSticker(context,r.api);if(item==null||!mounted||gameController!=c)return;
    try{final sent=await c.runJavaScriptReturningResult('window.SamiDevNetwork?.sendSticker(${jsonEncode(item['id'])},${jsonEncode(item['asset'])})??false');if(sent==true||sent=='true'){unawaited(SystemSound.play(SystemSoundType.click));}else{notify('تعذر إرسال الملصق؛ تحقق من الاتصال');}}catch(_){notify('تعذر إرسال الملصق');}
  }
  Future<void> sendChat() async {
    final text=input.text.trim();if(text.isEmpty||text.length>160||sending)return;
    setState(()=>sending=true);
    try {final sent=await gameController!.runJavaScriptReturningResult('Boolean(window.SamiDevNetwork?.sendChat(${jsonEncode(text)}))');if(sent==true||sent=='true'){input.clear();unawaited(SystemSound.play(SystemSoundType.click));}else{notify('لم تُرسل الرسالة. تحقق من الاتصال.');}}
    catch(_){notify('تعذر إرسال الرسالة');}finally{if(mounted)setState(()=>sending=false);}
  }
  Future<void> syncTheme() async {
    final theme=appTheme.value==ThemeMode.system?(_lastDark?'dark':'light'):appTheme.value==ThemeMode.dark?'dark':'light';
    for(final c in [controller,gameController]){
      try{await c?.runJavaScript('document.documentElement.dataset.theme=${jsonEncode(theme)}; window.SamiDevMobilePlatform?.setTheme(${jsonEncode(theme)});');}catch(_){}
    }
  }
  Future<void> chooseTheme() async {
    final mode=await showModalBottomSheet<ThemeMode>(context:context,useSafeArea:true,builder:(context)=>Column(mainAxisSize:MainAxisSize.min,children:[
      const Padding(padding:EdgeInsets.all(18),child:Text('المظهر',style:TextStyle(fontSize:20,fontWeight:FontWeight.w700))),
      for(final entry in {ThemeMode.system:'حسب الجهاز',ThemeMode.light:'نهاري',ThemeMode.dark:'ليلي'}.entries)
        ListTile(title:Text(entry.value),trailing:appTheme.value==entry.key?const Icon(Icons.check):null,onTap:()=>Navigator.pop(context,entry.key)),const SizedBox(height:12),
    ]));
    if(mode==null)return;appTheme.value=mode;await SecureSessionVault().write('samidev.appearance',mode.name);await syncTheme();
  }
  Future<void> configurePlatform() async {
    if(controller==null)return;
    try{
      await controller!.runJavaScript('window.SamiDevMobilePlatform?.closeProfile(); window.SamiDevMobilePlatform?.setNativeActive(${nativeHome||inGame?'true':'false'});');
      if(!inGame&&webPage!=null)await controller!.runJavaScript('window.SamiDevMobilePlatform?.navigate(${jsonEncode(webPage)});');
      if(!inGame&&webPage=='friends'&&pendingFriendRequests){
        final ready=await controller!.runJavaScriptReturningResult('typeof window.SamiDevMobilePlatform?.openFriendRequests === "function"');
        if(ready==true||ready.toString()=='true'){pendingFriendRequests=false;await controller!.runJavaScript('window.SamiDevMobilePlatform.openFriendRequests();');}
      }
      if(!inGame&&webPage=='friends'&&pendingFriendId!=null){
        final id=pendingFriendId;
        final ready=await controller!.runJavaScriptReturningResult('typeof window.SamiDevMobilePlatform?.openConversation === "function"');
        if(ready==true||ready.toString()=='true'){pendingFriendId=null;await controller!.runJavaScript('window.SamiDevMobilePlatform.openConversation(${jsonEncode(id)});');}
      }
    }catch(_){}
  }
  Future<void> openPage(String page) async {
    if(!mounted||runtime==null)return;
    setState(()=>webPage=page);chatFocus.unfocus();
    if(current==null||!current!.path.startsWith('/platform'))await controller!.loadRequest(runtime!.origin.replace(path:'/platform/'));
    else await configurePlatform();
  }
  Future<void> openAccountSettings() async {
    if(runtime==null||gamesProfile==null)return;
    await Navigator.of(context).push(MaterialPageRoute<void>(builder:(_)=>AccountSettings(api:runtime!.api,onAdmin:{'admin','moderator'}.contains(role)?()=>openPage('admin'):null,onTheme:chooseTheme,user:gamesProfile!,onChanged:(user)async{await completeAuthentication(runtime!,user);})));
  }
  void openProfile(String id){
    if(_profileOpen||runtime==null||!RegExp(r'^[A-Za-z0-9_-]{1,64}$').hasMatch(id))return;
    _profileOpen=true;
    unawaited(showPlayerProfile(context,api:runtime!.api,id:id,roomId:room,communityId:inGame?runtime!.community:(hubKey.currentState?.community?['id']?.toString()??''),onUnauthorized:()=>onEvent({'type':'auth_expired'}))
      .whenComplete((){_profileOpen=false;if(mounted&&gameController!=null){unawaited(gameController!.runJavaScript('window.SamiDevNetwork?.requestChatHistory();').catchError((_){ }));}}));
  }
  Future<void> refreshGamesProfile()async{
    final r=runtime;if(r==null||!authenticated)return;
    try{final response=await r.api.request('GET','/api/me');if(!mounted||runtime!=r||!authenticated)return;
      if(response.status==200&&response.json['user'] is Map)setState(()=>gamesProfile=Map<String,dynamic>.from(response.json['user'] as Map));
    }catch(_){}
  }
  Future<void> openGame(String game,Map<String,String> query) async {
    const entries={'pool':'/games/pool/index.html','crazy8':'/games/crazy8/index.html','carrom':'/index.html','tablesoccer':'/games/tablesoccer/index.html'};
    final r=runtime;if(r==null||!entries.containsKey(game))return;
    if(!RuntimePolicy.isCommunityId(query['community']))return;
    if(gameController==null)_returnToGames=nativeGames;
    if(!await openGameUri(r.origin.replace(path:entries[game],queryParameters:query)))throw StateError(_entryFailure??'تعذر تجهيز الطاولة');
  }
  Future<bool> openGameUri(Uri uri) async {
    final r=runtime;if(r==null||!r.allowsNavigation(uri)||!RuntimePolicy.isGame(uri.path)||_openingGame)return false;
    if(gameController!=null){
      if(uri.queryParameters['room']==table.roomId&&table.roomId.isNotEmpty){resumeGame();return true;}
      else{notify('لديك طاولة مفتوحة. عد إليها أو غادرها من قائمة الثلاث نقاط أولًا.');}
      return false;
    }
    _entryFrameReady=false;_entryAdmitted=false;_entryFailure=null;
    _openingGame=true;FocusManager.instance.primaryFocus?.unfocus();
    try{
      final cid=uri.queryParameters['community'];if(RuntimePolicy.isCommunityId(cid))r.community=cid!;
      final c=await makeController(r,game:true);if(!mounted||runtime!=r)return false;
      final surface=Completer<bool>();_gameSurfaceReady=surface;
      setState((){_awaitingGameSurface=true;gameController=c;gameCurrent=uri;gameProgress=0;inGame=true;room='';notifiedMatch=null;notifiedMineTurn=null;messages.clear();table.clear();});
      await configurePlatform();
      // The gateway supplies a one-time ticket; no session or ticket enters a URL.
      await c.loadRequest(uri);
      if(!await surface.future.timeout(const Duration(seconds:45)))throw StateError(_entryFailure??'تعذر تجهيز الطاولة');
      return true;
    }catch(_){_entryFailure??='تعذر فتح الطاولة. حاول مجددًا.';await discardGame();notify(_entryFailure!);return false;}
    finally{_openingGame=false;if(mounted)setState(()=>_awaitingGameSurface=false);}
  }
  Future<void> back() async {
    if(inGame){parkGame();return;}
    if(nativeGames&&gamesKey.currentState?.back()==true)return;
    if(webPage!=null){setState((){webPage=null;selectedTab=0;});await configurePlatform();return;}
    await hubKey.currentState?.back();
  }
  Future<void> openInvite() async {
    if(gameController!=null){notify('لديك طاولة مفتوحة. غادرها أولًا من قائمة الثلاث نقاط.');return;}
    final field=TextEditingController();
    final value=await showDialog<String>(context:context,builder:(context)=>AlertDialog(title:const Text('دخول بدعوة'),content:TextField(controller:field,maxLength:2048,decoration:const InputDecoration(labelText:'رابط الدعوة أو رمزها')),actions:[TextButton(onPressed:()=>Navigator.pop(context),child:const Text('إلغاء')),FilledButton(onPressed:()=>Navigator.pop(context,field.text.trim()),child:const Text('دخول'))]));
    // Dispose after the dialog's exit animation has detached its editable text.
    Future<void>.delayed(const Duration(milliseconds:300),field.dispose);
    if(value==null||value.isEmpty||!mounted)return;
    try{var token=value;if(!RegExp(r'^[A-Za-z0-9_-]{20,64}$').hasMatch(token)){final uri=Uri.parse(value);if(!uri.hasAuthority||uri.origin!=runtime!.api.policy.backend.origin||uri.path!='/platform/')throw const FormatException();token=uri.queryParameters['invite']??'';}if(!RegExp(r'^[A-Za-z0-9_-]{20,64}$').hasMatch(token))throw const FormatException();await controller!.loadRequest(runtime!.origin.replace(path:'/platform/',queryParameters:{'invite':token}));}catch(_){notify('رابط الدعوة غير صالح');}
  }
  @override void didChangeAppLifecycleState(AppLifecycleState state){
    if(state!=AppLifecycleState.resumed)gameHaptics.cancel();
    final r=runtime;if(r==null||controller==null)return;
    if(state==AppLifecycleState.paused||state==AppLifecycleState.hidden){
      setState(()=>_background=true);dismissFriendBanner();unawaited(friendNotifications?.background(true));
      for(final c in [controller,gameController]){unawaited(c?.runJavaScript('window.audio?.suspend?.();').catchError((_){ }));}
      unawaited(r.suspend());
    }else if(state==AppLifecycleState.resumed&&_background){
      setState(()=>_background=false);r.resume();unawaited(friendNotifications?.background(false));
      // Reconnect the retained table even if the community is in the foreground.
      unawaited(gameController?.reload());if(!nativeHome&&!inGame)unawaited(controller?.reload());
    }
  }
  @override void dispose(){gameHaptics.dispose();unawaited(friendNotifications?.stop());dismissFriendBanner();for(final timer in chatPendingTimers.values){timer.cancel();}WidgetsBinding.instance.removeObserver(this);unawaited(subscription?.cancel());unawaited(runtime?.close());input.dispose();chatScroll.dispose();chatFocus.dispose();unawaited(SystemChrome.setPreferredOrientations(DeviceOrientation.values));super.dispose();}
  Widget chatHistory(){
    final colors=Theme.of(context).colorScheme;
    return ConstrainedBox(constraints:BoxConstraints(maxHeight:min(230,MediaQuery.sizeOf(context).height*.28)),child:Material(color:colors.surface.withValues(alpha:.97),elevation:6,child:messages.isEmpty?
      const Padding(padding:EdgeInsets.all(18),child:Text('لا توجد رسائل بعد. قل مرحبًا.')):
      ListView.builder(controller:chatScroll,shrinkWrap:true,padding:const EdgeInsets.all(14),itemCount:messages.length,itemBuilder:(context,i){final m=messages[i];return Padding(padding:const EdgeInsets.only(bottom:10),child:Align(alignment:m['seat']==table.seat?Alignment.centerRight:Alignment.centerLeft,child:Column(crossAxisAlignment:m['seat']==table.seat?CrossAxisAlignment.end:CrossAxisAlignment.start,children:[Text(table.roster.where((p)=>p['seat']==m['seat']).map((p)=>p['name']?.toString()??'لاعب').firstOrNull??'لاعب',style:TextStyle(fontSize:11,color:colors.primary)),if(m['pending']==true)Text(m['failed']==true?'تعذر تأكيد الإرسال':'جارٍ الإرسال',style:const TextStyle(fontSize:10)),const SizedBox(height:4),if(m['stickerId']!=null)StickerArtwork(asset:m['stickerAsset']?.toString()??'',size:100)else ChatCosmetic(id:m['chatBubble']?.toString()??'',child:Text(m['text']?.toString()??'',style:const TextStyle(fontSize:15,height:1.4)))])));})));
  }
  Widget gameSurface()=>GameViewport(active:inGame,dim:chatFocus.hasFocus&&MediaQuery.viewInsetsOf(context).bottom>0,
    overlay:showChat?chatHistory():null,child:WebViewWidget(key:const ValueKey('game-view'),controller:gameController!));
  @override Widget build(BuildContext context){
    final ready=!loading&&error==null&&runtime!=null;
    return PopScope(canPop:!inGame&&webPage==null&&hubKey.currentState?.community==null,onPopInvokedWithResult:(didPop,result){if(!didPop)unawaited(back());},child:Scaffold(
      bottomNavigationBar:authenticated&&(!inGame||_awaitingGameSurface)&&ready&&(nativeGames||hubKey.currentState?.community==null)?NavigationBar(selectedIndex:selectedTab,onDestinationSelected:(index){setState(()=>selectedTab=index);if(index==0){setState(()=>webPage=null);unawaited(configurePlatform());}else if(index==2){setState(()=>webPage='games');unawaited(refreshGamesProfile());unawaited(configurePlatform());}else{unawaited(openPage(['lobby','friends','games','store','profile'][index]));}},destinations:const [
        NavigationDestination(icon:Icon(Icons.public_outlined),selectedIcon:Icon(Icons.public),label:'المساحات'),
        NavigationDestination(icon:Icon(Icons.people_outline),selectedIcon:Icon(Icons.people),label:'الأصدقاء'),
        NavigationDestination(icon:Icon(Icons.sports_esports_outlined),selectedIcon:Icon(Icons.sports_esports),label:'الألعاب'),
        NavigationDestination(icon:Icon(Icons.storefront_outlined),label:'المتجر'),
        NavigationDestination(icon:Icon(Icons.person_outline),selectedIcon:Icon(Icons.person),label:'البروفايل'),
      ]):null,
      body:SafeArea(bottom:true,child:error!=null?Center(child:Padding(padding:const EdgeInsets.all(24),child:Column(mainAxisSize:MainAxisSize.min,children:[const Icon(Icons.cloud_off,size:48),const SizedBox(height:16),Text(error!,textAlign:TextAlign.center),const SizedBox(height:20),FilledButton(onPressed:start,child:const Text('إعادة المحاولة'))]))):!ready?const Center(child:CircularProgressIndicator()):!authenticated?AuthScreen(key:ValueKey(runtime),auth:NativeAuth(runtime!.api),onAuthenticated:(user)=>completeAuthentication(runtime!,user)):Column(children:[
        if(!_awaitingGameSurface&&(inGame?gameProgress:progress)<100&&(inGame||!nativeHome))LinearProgressIndicator(value:(inGame?gameProgress:progress)/100,minHeight:2),
        if(inGame&&!_awaitingGameSurface&&!table.begun&&!table.finished&&table.seat>=0&&table.ownerSeat==table.seat)Align(
          alignment:Alignment.centerRight,child:PopupMenuButton<int>(tooltip:'إدارة الطاولة قبل اللعب',
            onSelected:(seat)=>unawaited(manageTable(seat==-1?'close':'kick',seat==-1?null:seat)),
            itemBuilder:(_)=>[const PopupMenuItem(value:-1,child:Text('إغلاق الطاولة')),
              for(final player in table.roster.where((p)=>p['seat']!=table.seat))PopupMenuItem(value:(player['seat'] as num).toInt(),child:Text('إخراج ${player['name']}'))],
            child:const Padding(padding:EdgeInsets.symmetric(horizontal:16,vertical:8),child:Text('إدارة الطاولة')))),
        if(!inGame&&gameController!=null)Material(color:Theme.of(context).colorScheme.primaryContainer,child:ListTile(dense:true,
          leading:const Icon(Icons.sports_esports_outlined),title:const Text('العودة إلى طاولتك',style:TextStyle(fontWeight:FontWeight.w700)),
          subtitle:Text(table.finished?'انتهت المباراة':table.begun?'المباراة جارية — دورك يستمر أثناء التصفح':table.started?'تجهيز المباراة':'بانتظار انضمام اللاعبين'),
          trailing:const Icon(Icons.chevron_left),onTap:resumeGame)),
        Expanded(child:Stack(fit:StackFit.expand,children:[
          if(controller!=null)Offstage(key:const ValueKey('platform-surface'),offstage:nativeHome||inGame,child:WebViewWidget(controller:controller!)),
          if(gameController!=null)Offstage(key:const ValueKey('retained-game'),offstage:!inGame,child:gameSurface()),
          if(authenticated)Offstage(key:const ValueKey('native-games'),offstage:!nativeGames,child:GamesHub(key:gamesKey,user:gamesProfile,onGame:openGame,onSelectionChanged:(){if(mounted)setState((){});})),
          if(authenticated)Offstage(key:const ValueKey('native-community'),offstage:!nativeHome||nativeGames,child:ColoredBox(color:Theme.of(context).scaffoldBackgroundColor,child:CommunityHub(key:hubKey,user:gamesProfile,api:runtime!.api,active:nativeHome&&!nativeGames&&!_background,initialCommunity:current?.queryParameters['community'],onGame:openGame,onProfile:openProfile,onTheme:chooseTheme,onAccount:openAccountSettings,onInvite:openInvite,onNavigationChanged:(){if(mounted)setState((){});},onUnauthorized:()=>onEvent({'type':'auth_expired'})))),
        ])),
        if(inGame&&!_awaitingGameSurface)ChatComposer(controller:input,focusNode:chatFocus,sending:sending,onSend:sendChat,onStickers:sendGameSticker,onToggle:(){setState(()=>showChat=!showChat);if(showChat)scrollChat();},expanded:showChat),
      ])),
    ));
  }
}
