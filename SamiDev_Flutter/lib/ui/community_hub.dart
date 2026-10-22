import 'dart:async';
import 'dart:convert';
import 'dart:math';
import 'package:flutter/services.dart';
import 'chat_stickers.dart';
import 'package:flutter/material.dart';
import 'chat_cosmetic.dart';
import '../runtime/api.dart';
import '../runtime/policy.dart';
import 'player_profile.dart';
import 'sticker_art.dart';
import 'reputation_flame.dart';

class CommunityHub extends StatefulWidget {
  const CommunityHub({super.key,required this.api,required this.active,required this.onGame,required this.onProfile,required this.onTheme,required this.onInvite,required this.onNavigationChanged,required this.onUnauthorized,this.initialCommunity,this.onAccount,this.user});
  final Map<String,dynamic>? user;
  final VoidCallback? onAccount;
  final PlatformApi api;
  final bool active;
  final String? initialCommunity;
  final Future<void> Function(String game,Map<String,String> query) onGame;
  final void Function(String userId) onProfile;
  final VoidCallback onTheme,onInvite,onNavigationChanged,onUnauthorized;
  @override State<CommunityHub> createState()=>CommunityHubState();
}
class CommunityHubState extends State<CommunityHub> {
  Timer? timer,liveRetry;
  StreamSubscription<Map<String,dynamic>>? live;
  String? liveCid;
  Map<String,dynamic>? community;
  List<Map<String,dynamic>> spaces=[],rooms=[],members=[],messages=[];
  final input=TextEditingController(),scroll=ScrollController();
  bool busy=false,sending=false,navigating=false;
  List<Map<String,dynamic>> notifications=[];
  bool canModerate=false;
  String? error;
  int tab=0,generation=0;
  static const games={'pool':'البلياردو','carrom':'الكيرم','crazy8':'بلازر أونو','tablesoccer':'كرة الطاولة'};
  List<Map<String,dynamic>> rows(dynamic data)=>(data as List? ?? []).whereType<Map>().map((e)=>Map<String,dynamic>.from(e)).toList();
  Future<Map<String,dynamic>> request(String path,{String method='GET',String? query,Map<String,dynamic>? body}) async {
    final r=await widget.api.request(method,path,query:query,body:body==null?null:utf8.encode(jsonEncode(body)));
    final data=r.json;if(r.status==403&&{'COMMUNITY_BANNED','COMMUNITY_KICKED','COMMUNITY_DISABLED'}.contains(data['error'])){final denied=path.split('/').length>3?path.split('/')[3]:null;WidgetsBinding.instance.addPostFrameCallback((_){if(mounted&&community?['id']==denied)unawaited(back());});}if(r.status==401)widget.onUnauthorized();if(r.status!=200||data['ok']==false)throw StateError(data['message']?.toString()??'تعذر إكمال الطلب');return data;
  }
  @override void initState(){super.initState();final cid=widget.initialCommunity;if(RuntimePolicy.isCommunityId(cid))community={'id':cid};WidgetsBinding.instance.addPostFrameCallback((_){if(mounted)widget.onNavigationChanged();});restart();}
  @override void didUpdateWidget(covariant CommunityHub oldWidget){super.didUpdateWidget(oldWidget);if(oldWidget.active!=widget.active||oldWidget.user?['id']!=widget.user?['id']||oldWidget.user?['isGuest']!=widget.user?['isGuest']){stopLive();restart();}}
  void stopLive(){liveRetry?.cancel();unawaited(live?.cancel());live=null;liveCid=null;}
  void mergeMessages(List<Map<String,dynamic>> incoming){
    final all={for(final row in messages)row['id']:row};
    for(final row in incoming){if(row['clientMessageId']!=null)all.removeWhere((_,old)=>old['pending']==true&&old['userId']==row['userId']&&old['clientMessageId']==row['clientMessageId']);all[row['id']]=row;}
    messages=all.values.toList()..sort((a,b)=>(a['createdAt'] as num? ?? 0).compareTo(b['createdAt'] as num? ?? 0));
    if(messages.length>200)messages=messages.sublist(messages.length-200);
  }
  void startLive(String cid){
    if(!widget.active||liveCid==cid)return;stopLive();liveCid=cid;
    void retry(){if(!mounted||!widget.active||community?['id']!=cid||liveCid!=cid)return;live=null;liveCid=null;liveRetry=Timer(const Duration(seconds:2),()=>startLive(cid));}
    live=widget.api.events('/api/communities/$cid/events').listen((event){
      if(!mounted||community?['id']!=cid)return;
      if(event['type']=='access_denied'){stopLive();unawaited(refresh());return;}
      final incoming=event['type']=='message'?rows([event['message']]):rows(event['messages']);
      final nearEnd=!scroll.hasClients||scroll.position.maxScrollExtent-scroll.offset<80;
      setState(()=>mergeMessages(incoming));if(nearEnd)scrollToEnd();
    },onError:(Object error){retry();},onDone:retry,cancelOnError:true);
  }
  void restart(){timer?.cancel();if(widget.active){unawaited(refresh());timer=Timer.periodic(const Duration(seconds:3),(_)=>refresh());}else{stopLive();}}
  void report(Object e){if(mounted){final msg=e is StateError?e.message.toString():'تعذر الاتصال. اسحب للتحديث.';ScaffoldMessenger.of(context).showSnackBar(SnackBar(content:Text(msg),behavior:SnackBarBehavior.floating,duration:const Duration(seconds:3)));setState(()=>error=msg);}}
  Future<void> refresh() async {
    if(busy||!widget.active)return;busy=true;final version=generation,cid=community?['id'];
    try{
      final d=await request(cid==null?'/api/communities':'/api/communities/$cid',query:cid!=null&&liveCid==cid?'chat=0':null);
      if(!mounted||version!=generation)return;
      final nearEnd=!scroll.hasClients||scroll.position.maxScrollExtent-scroll.offset<80;
      final previous=messages.isEmpty?null:messages.last['id'];
      setState((){error=null;if(cid==null){spaces=rows(d['communities']);notifications=rows(d['notifications']);}else{canModerate=(d['capabilities'] as Map?)?['canModerate']==true;community=Map<String,dynamic>.from(d['community']);rooms=rows(d['rooms']);members=rows(d['members']);mergeMessages(rows(d['messages']));}});
      if(cid!=null)startLive(cid.toString());
      if(nearEnd&&(messages.isNotEmpty&&messages.last['id']!=previous))scrollToEnd();
    }catch(e){report(e);}finally{busy=false;}
  }
  void scrollToEnd(){WidgetsBinding.instance.addPostFrameCallback((_){if(scroll.hasClients)unawaited(scroll.animateTo(scroll.position.maxScrollExtent,duration:const Duration(milliseconds:160),curve:Curves.easeOut));});}
  Future<void> enter(Map<String,dynamic> value) async {
    if(navigating)return;navigating=true;
    try{await request('/api/communities/${value['id']}/enter',method:'POST',body:{});if(!mounted)return;
      generation++;setState((){community=value;rooms=[];members=[];messages=[];tab=0;error=null;});widget.onNavigationChanged();await refresh();
    }catch(e){report(e);}finally{navigating=false;}
  }
  void restoreCommunity(String cid){
    if(!RuntimePolicy.isCommunityId(cid)||community?['id']==cid)return;
    generation++;setState((){community={'id':cid};rooms=[];members=[];messages=[];tab=0;});
    WidgetsBinding.instance.addPostFrameCallback((_){if(mounted)widget.onNavigationChanged();});
    if(widget.active)unawaited(refresh());
  }
  Future<bool> back() async {
    if(community==null)return false;
    final cid=community!['id'];
    try{await request('/api/communities/$cid/leave',method:'POST',body:{});}catch(e){report(e);}
    if(!mounted)return true;stopLive();generation++;setState((){community=null;rooms=[];members=[];messages=[];error=null;});widget.onNavigationChanged();await refresh();return true;
  }
  Future<void> submitMessage(Map<String,dynamic> message) async {
    final cid=message['communityId'];
    try{final result=await request('/api/communities/$cid/chat',method:'POST',body:{'text':message['text'],'clientMessageId':message['clientMessageId'],if(message['stickerId']!=null)'stickerId':message['stickerId']});if(!mounted||community?['id']!=cid)return;setState(()=>mergeMessages(rows([result['message']])));}
    catch(e){if(mounted&&community?['id']==cid){setState(()=>message['failed']=true);report(e);}}
  }
  Future<void> send() async {
    final text=input.text.trim();if(text.isEmpty||community==null||widget.user==null)return;
    if(text.runes.length>280){report(StateError('الحد الأقصى ٢٨٠ حرفًا'));return;}
    final nonce='${DateTime.now().microsecondsSinceEpoch}_${List.generate(12,(_)=>Random.secure().nextInt(256).toRadixString(16).padLeft(2,'0')).join()}';
    final message=<String,dynamic>{'id':'pending_$nonce','clientMessageId':nonce,'communityId':community!['id'],'userId':widget.user!['id'],'username':widget.user!['username'],'displayName':widget.user!['username'],'nameBadgeAsset':widget.user!['nameBadgeAsset'],'chatBubble':widget.user!['chatBubble'],'text':text,'createdAt':DateTime.now().millisecondsSinceEpoch,'pending':true};
    setState((){input.clear();mergeMessages([message]);});scrollToEnd();unawaited(SystemSound.play(SystemSoundType.click));unawaited(submitMessage(message));
  }
  Future<void> sendSticker() async {
    final cid=community?['id'];if(cid==null||widget.user==null)return;
    final item=await pickChatSticker(context,widget.api);if(item==null||!mounted||community?['id']!=cid)return;
    final nonce='sticker_${DateTime.now().microsecondsSinceEpoch}_${Random.secure().nextInt(1<<30)}';
    final message=<String,dynamic>{'id':'pending_$nonce','clientMessageId':nonce,'communityId':cid,'userId':widget.user!['id'],'username':widget.user!['username'],'text':'','stickerId':item['id'],'stickerAsset':item['asset'],'createdAt':DateTime.now().millisecondsSinceEpoch,'pending':true};
    setState(()=>mergeMessages([message]));scrollToEnd();unawaited(SystemSound.play(SystemSoundType.click));unawaited(submitMessage(message));
  }
  String name(Map user)=>user['displayName']?.toString()??user['name']?.toString()??user['username']?.toString()??'لاعب';
  Widget avatar(Map user,{double radius=23})=>user.isEmpty
    ? CircleAvatar(radius:radius,backgroundColor:Theme.of(context).colorScheme.surfaceContainerHighest,child:Icon(Icons.event_seat_outlined,size:radius))
    : PlayerAvatar(api:widget.api,user:user,radius:radius);
  Widget mark(String game){
    final asset=switch(game){'pool'=>'pool','carrom'=>'carrom','crazy8'=>'cards','tablesoccer'=>'football',_=>'carrom'};
    return Container(width:58,height:58,padding:const EdgeInsets.all(3),decoration:BoxDecoration(color:const Color(0xff20232d),borderRadius:BorderRadius.circular(14)),child:Image.asset('assets/runtime/room-sprites/$asset.png',fit:BoxFit.contain,errorBuilder:(_,error,stack)=>const Icon(Icons.sports_esports_outlined,color:Colors.white70)));
  }
  String details(Map settings,int capacity){
    final live=settings['live']==0?'تناوب الأدوار':'مباشر';
    final special=['أساسية','جميع البطاقات','درع','أشعة','الأحمر','الأزرق'];
    final n=(settings['special'] as num?)?.toInt()??0;
    return '$live، $capacity لاعبين${settings['gameId']=='crazy8'?', ${special[n.clamp(0,5).toInt()]}':''}';
  }
  Future<void> confirmTable(Map<String,dynamic> room,String game,bool join) async {
    if(navigating)return;navigating=true;
    var loading=false;String? failure;
    try{await showDialog<void>(context:context,barrierDismissible:false,barrierColor:const Color(0x22000000),builder:(dialogContext)=>StatefulBuilder(builder:(context,update)=>PopScope(canPop:!loading,child:AlertDialog(
      shape:RoundedRectangleBorder(borderRadius:BorderRadius.circular(20)),
      title:Row(children:[mark(game),const SizedBox(width:14),Expanded(child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[Text('الطاولة ${room['roomId']}',style:Theme.of(context).textTheme.labelSmall),Text(games[game]??game,style:const TextStyle(fontSize:20,fontWeight:FontWeight.w700))]))]),
      content:loading?const Column(mainAxisSize:MainAxisSize.min,children:[SizedBox(height:8),SizedBox(width:30,height:30,child:CircularProgressIndicator(strokeWidth:3)),SizedBox(height:18),Text('نجهّز طاولتك…'),SizedBox(height:8),Text('بتدخل تلقائيًا عند جاهزيتها',style:TextStyle(fontSize:12))]):Text(failure??details(room['settings'] as Map? ?? {},(room['capacity'] as num?)?.toInt()??2)),
      actions:loading?[]:[TextButton(onPressed:()=>Navigator.pop(dialogContext),child:Text(failure==null?'إلغاء':'رجوع')),if(failure==null)FilledButton(onPressed:()async{
        if(loading)return;update(()=>loading=true);
        try{await widget.onGame(game,{'online':'1','action':join?'join':'watch','room':room['roomId'].toString(),'community':community!['id'].toString()});if(dialogContext.mounted)Navigator.pop(dialogContext);}
        catch(e){if(dialogContext.mounted){if(e is StateError&&e.message=='حاول بعد دقيقة'){Navigator.pop(dialogContext);}else{update((){loading=false;failure='تعذر فتح الطاولة. ارجع وحاول مجددًا.';});}}}
      },child:Text(join?'انضم':'مشاهدة'))],
    ))));}finally{navigating=false;}
  }
  Widget roomRow(Map<String,dynamic> room){
    final settings=room['settings'] is Map?room['settings'] as Map:<String,dynamic>{};
    final game=settings['gameId']?.toString()??'carrom';
    final cap=(room['capacity'] as num?)?.toInt()??2,occupied=(room['occupied'] as num?)?.toInt()??0;
    final open=room['started']!=true&&occupied<cap,watch=room['begun']==true&&room['finished']!=true;
    final roster=rows(room['roster']);
    return Padding(padding:const EdgeInsets.symmetric(horizontal:16,vertical:17),child:Row(crossAxisAlignment:CrossAxisAlignment.start,children:[
      mark(game),const SizedBox(width:12),Expanded(child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[
        Text(games[game]??game,style:const TextStyle(fontSize:17,fontWeight:FontWeight.w700)),const SizedBox(height:5),
        Text(details(settings,cap),maxLines:2,style:TextStyle(color:Theme.of(context).colorScheme.onSurfaceVariant,fontSize:12,height:1.5)),const SizedBox(height:9),
        Wrap(spacing:4,children:List.generate(cap,(seat){final p=roster.where((p)=>p['seat']==seat).firstOrNull;return Tooltip(message:p==null?'مقعد فارغ':name(p),child:avatar(p??{},radius:13));})),
      ])),const SizedBox(width:8),Column(crossAxisAlignment:CrossAxisAlignment.end,children:[
        Text(room['roomId']?.toString()??'',style:TextStyle(fontSize:12,color:Theme.of(context).colorScheme.onSurfaceVariant)),const SizedBox(height:24),
        SizedBox(height:30,child:FilledButton(style:FilledButton.styleFrom(backgroundColor:open?const Color(0xff83b932):null,foregroundColor:Colors.white,padding:const EdgeInsets.symmetric(horizontal:18)),
          onPressed:open||watch?()=>confirmTable(room,game,open):null,
          child:Text(open?'انضم':watch?'مشاهدة':'تجهيز',style:const TextStyle(fontSize:12)))),
      ]),
    ]));
  }
  Widget memberRow(Map<String,dynamic> user)=>InkWell(onTap:()=>widget.onProfile(user['id'].toString()),child:Padding(
    padding:const EdgeInsets.symmetric(horizontal:18,vertical:16),child:Row(children:[
      PlayerAvatar(api:widget.api,user:user,radius:31,framed:true),const SizedBox(width:13),
      Expanded(child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[
        Row(children:[StickerArtwork(asset:user['nameBadgeAsset']?.toString()??'',size:24),const SizedBox(width:3),Expanded(child:Text(name(user),style:const TextStyle(fontSize:18,fontWeight:FontWeight.w600)))]),
        const SizedBox(height:5),ProfileStars(size:18,count:(user['starsCount'] as num?)?.toInt()??0),
        const SizedBox(height:8),Wrap(spacing:16,runSpacing:6,children:[
          Row(mainAxisSize:MainAxisSize.min,children:[const ProfileDecoration('trophy',size:18),const SizedBox(width:5),Text('فوز ${user['wins']??0}',style:const TextStyle(fontSize:12))]),
          Row(mainAxisSize:MainAxisSize.min,children:[ReputationFlame(score:int.tryParse('${user['reputation']}')??0,size:20),const SizedBox(width:5),Text('سمعة ${user['reputation']??0}',style:const TextStyle(fontSize:12))]),
        ]),
      ])),
    ])));
  Widget messageRow(Map<String,dynamic> message){
    final ts=(message['createdAt'] as num?)?.toInt(),date=ts==null?null:DateTime.fromMillisecondsSinceEpoch(ts).toLocal();
    final mine=message['userId']!=null && message['userId'].toString()==widget.user?['id']?.toString();
    return Directionality(textDirection:mine?TextDirection.rtl:TextDirection.ltr,child:Padding(padding:const EdgeInsets.fromLTRB(14,8,18,8),child:Align(alignment:mine?Alignment.centerRight:Alignment.centerLeft,child:Row(mainAxisSize:MainAxisSize.min,crossAxisAlignment:CrossAxisAlignment.start,children:[
      InkWell(onTap:()=>widget.onProfile(message['userId'].toString()),child:avatar(message,radius:20)),const SizedBox(width:12),
      Flexible(child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[Row(textDirection:TextDirection.rtl,mainAxisSize:MainAxisSize.min,children:[
        StickerArtwork(asset:message['nameBadgeAsset']?.toString()??'',size:18),const SizedBox(width:3),
        Flexible(child:Text(name(message),overflow:TextOverflow.ellipsis,style:const TextStyle(fontSize:13,fontWeight:FontWeight.w600))),const SizedBox(width:5),
        if(date!=null)Text(TimeOfDay.fromDateTime(date).format(context),style:TextStyle(fontSize:10,color:Theme.of(context).colorScheme.onSurfaceVariant)),
      ]),if(message['pending']==true)TextButton(onPressed:message['failed']==true?(){setState(()=>message['failed']=false);unawaited(submitMessage(message));}:null,child:Text(message['failed']==true?'تعذر الإرسال · إعادة المحاولة':'جارٍ الإرسال',style:const TextStyle(fontSize:10))),const SizedBox(height:5),if(message['stickerId']!=null)StickerArtwork(asset:message['stickerAsset']?.toString()??'',size:100)else ChatCosmetic(id:message['chatBubble']?.toString()??'',
        child:Text(message['text']?.toString()??'',textDirection:TextDirection.rtl,style:const TextStyle(fontSize:15,height:1.4))),])),
    ]))));
  }
  Widget empty(String text)=>ListView(physics:const AlwaysScrollableScrollPhysics(),children:[Padding(padding:const EdgeInsets.symmetric(horizontal:30,vertical:50),child:Text(text,textAlign:TextAlign.center,style:TextStyle(color:Theme.of(context).colorScheme.onSurfaceVariant)))]);
  Future<void> create() async {
    if(community==null)return;
    final config=await showModalBottomSheet<Map<String,String>>(context:context,isScrollControlled:true,useSafeArea:true,builder:(_)=>const CreateMatchSheet());
    if(config==null||!mounted)return;try{await widget.onGame(config['game']!,{'online':'1','action':'create','community':community!['id'].toString(),...config});}on StateError{/* Entry failure is already shown by the host. */}
  }
  @override void dispose(){stopLive();timer?.cancel();input.dispose();scroll.dispose();super.dispose();}
  Widget communityFlag(Map<String,dynamic> value,{double size=40}){
    final code=value['countryCode']?.toString();
    if(const ['sa','kw','jo','iq'].contains(code)){
      return Image.asset('assets/runtime/platform/assets/flags/$code.png',width:size,height:size,fit:BoxFit.contain,semanticLabel:value['name']?.toString());
    }
    return Text(value['mark']?.toString()??'P');
  }
  @override Widget build(BuildContext context){
    final colors=Theme.of(context).colorScheme;
    return Column(children:[
      if(community!=null)SizedBox(height:58,child:Row(children:[
        if(community!=null)IconButton(onPressed:back,tooltip:'المساحات',icon:const Icon(Icons.chevron_right,size:30))else const SizedBox(width:16),
        if(community!=null)CircleAvatar(radius:17,backgroundColor:Colors.transparent,child:communityFlag(community!,size:34)),
        const SizedBox(width:10),Expanded(child:Text(community?['name']?.toString()??'المساحات',maxLines:1,overflow:TextOverflow.ellipsis,style:const TextStyle(fontWeight:FontWeight.w600,fontSize:17))),
        if(community!=null)IconButton(onPressed:create,tooltip:'إنشاء طاولة',icon:const Icon(Icons.add,size:24)),
        if(community==null)IconButton(onPressed:widget.onInvite,tooltip:'دخول بدعوة',icon:const Icon(Icons.link)),
      ])),
      if(community==null)Align(alignment:Alignment.centerRight,child:TextButton.icon(onPressed:widget.onInvite,icon:const Icon(Icons.link),label:const Text('دخول بدعوة'))),
      if(community!=null&&canModerate)const Padding(padding:EdgeInsets.symmetric(horizontal:16,vertical:6),child:Text('أنت مشرف هذه المساحة · افتح ملف عضو للكتم أو الحظر أو الإخراج.',style:TextStyle(fontSize:12))),
      if(community!=null)Row(children:List.generate(3,(i)=>Expanded(child:InkWell(onTap:()=>setState((){tab=i;if(i==1){scrollToEnd();}else{FocusScope.of(context).unfocus();}}),child:Container(height:49,alignment:Alignment.center,decoration:BoxDecoration(border:Border(bottom:BorderSide(color:tab==i?colors.primary:colors.outlineVariant,width:tab==i?3:.5))),child:Text(['الألعاب (${rooms.length})','الدردشة','متصل (${members.length})'][i],style:TextStyle(color:tab==i?colors.primary:colors.onSurfaceVariant,fontWeight:tab==i?FontWeight.w700:FontWeight.normal,fontSize:14))))))),
      if(error!=null)MaterialBanner(content:Text(error!,style:const TextStyle(fontSize:12)),actions:[TextButton(onPressed:refresh,child:const Text('إعادة المحاولة'))]),
      Expanded(child:RefreshIndicator(onRefresh:refresh,child:community==null?
        (spaces.isEmpty?empty(busy?'تحميل المساحات…':'لا توجد مساحات متاحة'):ListView.separated(physics:const AlwaysScrollableScrollPhysics(),padding:const EdgeInsets.all(8),itemCount:spaces.length,separatorBuilder:(_,_)=>const SizedBox(height:8),itemBuilder:(_,i){final c=spaces[i];return ListTile(shape:RoundedRectangleBorder(borderRadius:BorderRadius.circular(12)),tileColor:colors.surfaceContainerLow,contentPadding:const EdgeInsets.all(18),leading:CircleAvatar(backgroundColor:Colors.transparent,child:communityFlag(c)),title:Text(c['name'].toString(),style:const TextStyle(fontWeight:FontWeight.w700)),subtitle:Text('${c['onlineCount']??0} متصل · ${c['gameRoomCount']??0} مباراة\n${c['description']??''}'),trailing:const Icon(Icons.chevron_left),onTap:()=>enter(c));})):
        tab==0?(rooms.isEmpty?empty('لا توجد مباريات حاليًا. أنشئ أول مباراة.'):ListView.separated(physics:const AlwaysScrollableScrollPhysics(),itemCount:rooms.length,itemBuilder:(_,i)=>roomRow(rooms[i]),separatorBuilder:(_,_)=>const Divider(height:1,indent:16,endIndent:16))):
        tab==2?(members.isEmpty?empty('لا يوجد أعضاء متصلون الآن.'):ListView.separated(physics:const AlwaysScrollableScrollPhysics(),itemCount:members.length,itemBuilder:(_,i)=>memberRow(members[i]),separatorBuilder:(_,_)=>const Divider(height:1,indent:16,endIndent:16))):
        messages.isEmpty?empty('قل مرحبًا وابدأ المحادثة.'):ListView.builder(controller:scroll,physics:const AlwaysScrollableScrollPhysics(),padding:const EdgeInsets.symmetric(vertical:12),itemCount:messages.length,itemBuilder:(_,i)=>messageRow(messages[i])),
      )),
      if(community!=null&&tab==1)ChatComposer(controller:input,sending:sending,onSend:send,onStickers:sendSticker,maxLength:280),
    ]);
  }
}

class ChatComposer extends StatelessWidget {
  const ChatComposer({super.key,required this.controller,required this.sending,required this.onSend,this.onToggle,this.onStickers,this.expanded=false,this.focusNode,this.maxLength=160});
  final TextEditingController controller;
  final bool sending,expanded;
  final VoidCallback onSend;
  final VoidCallback? onToggle,onStickers;
  final FocusNode? focusNode;
  final int maxLength;
  @override Widget build(BuildContext context)=>Material(color:Theme.of(context).colorScheme.surface,child:Container(constraints:const BoxConstraints(minHeight:54),decoration:BoxDecoration(border:Border(top:BorderSide(color:Theme.of(context).dividerColor,width:.5))),child:Row(children:[
    Expanded(child:TextField(controller:controller,focusNode:focusNode,maxLength:maxLength,textInputAction:TextInputAction.send,onSubmitted:(_)=>onSend(),minLines:1,maxLines:3,style:const TextStyle(fontSize:16),decoration:const InputDecoration(counterText:'',hintText:'قل مرحبًا',border:InputBorder.none,contentPadding:EdgeInsets.symmetric(horizontal:16,vertical:12)))),
    if(onStickers!=null)IconButton(onPressed:onStickers,tooltip:'الملصقات',icon:const Icon(Icons.sticky_note_2_outlined,size:23)),
    if(onToggle!=null)IconButton(onPressed:onToggle,tooltip:expanded?'إخفاء المحادثة':'عرض المحادثة',icon:Icon(expanded?Icons.chat_bubble:Icons.chat_bubble_outline,size:23)),
    IconButton(onPressed:sending?null:onSend,tooltip:'إرسال',icon:const Icon(Icons.send_rounded,size:24)),
  ])));
}

class CreateMatchSheet extends StatefulWidget {
  const CreateMatchSheet({super.key,this.initialGame='pool'});
  final String initialGame;
  @override State<CreateMatchSheet> createState()=>_CreateMatchSheetState();
}
class _CreateMatchSheetState extends State<CreateMatchSheet> {
  late String game;final values=<String,String>{};
  @override void initState(){super.initState();game=CommunityHubState.games.containsKey(widget.initialGame)?widget.initialGame:'pool';}
  Widget select(String key,String label,List<String> labels,{String initial='0'})=>Padding(padding:const EdgeInsets.only(bottom:12),child:DropdownButtonFormField<String>(initialValue:values[key]??initial,decoration:InputDecoration(labelText:label,border:const OutlineInputBorder()),items:List.generate(labels.length,(i)=>DropdownMenuItem(value:'$i',child:Text(labels[i]))),onChanged:(v){if(v!=null)setState(()=>values[key]=v);}));
  @override Widget build(BuildContext context)=>Padding(padding:EdgeInsets.fromLTRB(20,20,20,20+MediaQuery.viewInsetsOf(context).bottom),child:SingleChildScrollView(child:Column(mainAxisSize:MainAxisSize.min,crossAxisAlignment:CrossAxisAlignment.stretch,children:[
    const Text('إنشاء مباراة',style:TextStyle(fontSize:22,fontWeight:FontWeight.w700)),const SizedBox(height:20),
    DropdownButtonFormField<String>(initialValue:game,decoration:const InputDecoration(labelText:'اللعبة',border:OutlineInputBorder()),items:CommunityHubState.games.entries.map((e)=>DropdownMenuItem(value:e.key,child:Text(e.value))).toList(),onChanged:(v){if(v!=null)setState((){game=v;values.clear();});}),const SizedBox(height:14),
    KeyedSubtree(key:ValueKey(game),child:Column(children:[
      if(game=='crazy8')...[
        select('seats','اللاعبون',['لاعبان','3 لاعبين','4 لاعبين','6 لاعبين','2 ضد 2']),
        select('special','البطاقات',['أساسية','جميع البطاقات الخاصة','درع','أشعة','الأحمر','الأزرق']),
        select('live','نوع المباراة',['تناوب الأدوار','مباشر'],initial:'1'),
      ]else if(game!='pool')...[
        select('players','اللاعبون',['لاعبان','2 ضد 2']),
        if(game=='carrom')...[
          select('gamemode','النمط',['كلاسيك','Pool','حر 120','حر 160','حر 210']),
          select('break','البداية',['اللاعب الأول','اللاعب الثاني']),
        ]else...[
          select('goalsToWin','الأهداف',['هدفان','3 أهداف','5 أهداف'],initial:'1'),
          select('passes','التمرير',['بدون حد','3 تمريرات','6 تمريرات']),
        ],
        select('live','نوع المباراة',game=='tablesoccer'?['تناوب الأدوار','متزامن']:['تناوب الأدوار','مباشر'],initial:game=='tablesoccer'?'0':'1'),
      ]else...[
        select('gameType','نوع البلياردو',['إيت بول · لاعبان','إيت بول · فريقان بالتناوب','إيت بول · فريقان','ناين بول · لاعبان','ناين بول · فريقان بالتناوب','ناين بول · فريقان','ثلاثي · ٣ لاعبين','قيم بول · أول من يسجل ٨ كرات']),
        select('largeTable','الطاولة',['الأصلية','الطاولة الكبيرة']),
        Padding(padding:const EdgeInsets.all(14),child:Text('قيم بول: أي ٨ كرات، والسوداء عادية. البيضاء لا تُحسب.')),
      ],
    ])),const SizedBox(height:12),
    FilledButton(onPressed:()=>Navigator.pop(context,{'game':game,'live':game=='tablesoccer'?'0':'1','players':'0','seats':'0','special':'0','gamemode':'0','break':'0','goalsToWin':'1','passes':'0',...values}),child:const Padding(padding:EdgeInsets.all(12),child:Text('إنشاء المباراة'))),
  ])));
}
