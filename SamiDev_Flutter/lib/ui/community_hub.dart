import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import '../runtime/api.dart';
import 'player_profile.dart';

class CommunityHub extends StatefulWidget {
  const CommunityHub({super.key,required this.api,required this.active,required this.onGame,required this.onProfile,required this.onTheme,required this.onInvite,required this.onNavigationChanged,required this.onUnauthorized,this.initialCommunity});
  final PlatformApi api;
  final bool active;
  final String? initialCommunity;
  final Future<void> Function(String game,Map<String,String> query) onGame;
  final void Function(String userId) onProfile;
  final VoidCallback onTheme,onInvite,onNavigationChanged,onUnauthorized;
  @override State<CommunityHub> createState()=>CommunityHubState();
}
class CommunityHubState extends State<CommunityHub> {
  Timer? timer;
  Map<String,dynamic>? community;
  List<Map<String,dynamic>> spaces=[],rooms=[],members=[],messages=[];
  final input=TextEditingController(),scroll=ScrollController();
  bool busy=false,sending=false,navigating=false;
  String? error;
  int tab=0,generation=0;
  static const games={'pool':'البلياردو','carrom':'الكيرم','crazy8':'أونو','tablesoccer':'كرة الطاولة'};
  List<Map<String,dynamic>> rows(dynamic data)=>(data as List? ?? []).whereType<Map>().map((e)=>Map<String,dynamic>.from(e)).toList();
  Future<Map<String,dynamic>> request(String path,{String method='GET',Map<String,dynamic>? body}) async {
    final r=await widget.api.request(method,path,body:body==null?null:utf8.encode(jsonEncode(body)));
    final data=r.json;if(r.status==401)widget.onUnauthorized();if(r.status!=200||data['ok']==false)throw StateError(data['message']?.toString()??'تعذر إكمال الطلب');return data;
  }
  @override void initState(){super.initState();final cid=widget.initialCommunity;if({'majlis','square','diwan','elite'}.contains(cid))community={'id':cid};WidgetsBinding.instance.addPostFrameCallback((_){if(mounted)widget.onNavigationChanged();});restart();}
  @override void didUpdateWidget(covariant CommunityHub old){super.didUpdateWidget(old);if(old.active!=widget.active)restart();}
  void restart(){timer?.cancel();if(widget.active){unawaited(refresh());timer=Timer.periodic(const Duration(seconds:3),(_)=>refresh());}}
  void report(Object e){if(mounted)setState(()=>error=e is StateError?e.message.toString():'تعذر الاتصال. اسحب للتحديث.');}
  Future<void> refresh() async {
    if(busy||!widget.active)return;busy=true;final version=generation,cid=community?['id'];
    try{
      final d=await request(cid==null?'/api/communities':'/api/communities/$cid');
      if(!mounted||version!=generation)return;
      final nearEnd=!scroll.hasClients||scroll.position.maxScrollExtent-scroll.offset<80;
      final previous=messages.isEmpty?null:messages.last['id'];
      setState((){error=null;if(cid==null){spaces=rows(d['communities']);}else{community=Map<String,dynamic>.from(d['community']);rooms=rows(d['rooms']);members=rows(d['members']);messages=rows(d['messages']);}});
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
    if(!{'majlis','square','diwan','elite'}.contains(cid)||community?['id']==cid)return;
    generation++;setState((){community={'id':cid};rooms=[];members=[];messages=[];tab=0;});
    WidgetsBinding.instance.addPostFrameCallback((_){if(mounted)widget.onNavigationChanged();});
    if(widget.active)unawaited(refresh());
  }
  Future<bool> back() async {
    if(community==null)return false;
    final cid=community!['id'];
    try{await request('/api/communities/$cid/leave',method:'POST',body:{});}catch(e){report(e);}
    if(!mounted)return true;generation++;setState((){community=null;rooms=[];members=[];messages=[];error=null;});widget.onNavigationChanged();await refresh();return true;
  }
  Future<void> send() async {
    final text=input.text.trim();if(text.isEmpty||sending||community==null)return;
    final cid=community!['id'];setState(()=>sending=true);
    try{await request('/api/communities/$cid/chat',method:'POST',body:{'text':text});if(!mounted)return;input.clear();await refresh();scrollToEnd();}
    catch(e){report(e);}finally{if(mounted)setState(()=>sending=false);}
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
          onPressed:open||watch?()=>widget.onGame(game,{'online':'1','action':open?'join':'watch','room':room['roomId'].toString(),'community':community!['id'].toString()}):null,
          child:Text(open?'انضم':watch?'مشاهدة':'تجهيز',style:const TextStyle(fontSize:12)))),
      ]),
    ]));
  }
  Widget memberRow(Map<String,dynamic> user)=>InkWell(onTap:()=>widget.onProfile(user['id'].toString()),child:Padding(
    padding:const EdgeInsets.symmetric(horizontal:18,vertical:16),child:Row(children:[
      PlayerAvatar(api:widget.api,user:user,radius:31,framed:true),const SizedBox(width:13),
      Expanded(child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[
        Row(children:[const ProfileDecoration('palm-swords',size:24),const SizedBox(width:6),Expanded(child:Text(name(user),style:const TextStyle(fontSize:18,fontWeight:FontWeight.w600)))]),
        const SizedBox(height:5),const ProfileStars(size:18),
        if(user['username']!=null)Padding(padding:const EdgeInsets.only(top:4),child:Text('@${user['username']}',textDirection:TextDirection.ltr,style:TextStyle(fontSize:12,color:Theme.of(context).colorScheme.onSurfaceVariant))),
        const SizedBox(height:8),Wrap(spacing:16,runSpacing:6,children:[
          Row(mainAxisSize:MainAxisSize.min,children:[const ProfileDecoration('trophy',size:18),const SizedBox(width:5),Text('فوز ${user['wins']??0}',style:const TextStyle(fontSize:12))]),
          Row(mainAxisSize:MainAxisSize.min,children:[const ProfileDecoration('reputation-flame',size:18),const SizedBox(width:5),Text('سمعة ${user['reputation']??0}',style:const TextStyle(fontSize:12))]),
        ]),
      ])),
    ])));
  Widget messageRow(Map<String,dynamic> message){
    final ts=(message['createdAt'] as num?)?.toInt(),date=ts==null?null:DateTime.fromMillisecondsSinceEpoch(ts).toLocal();
    return Directionality(textDirection:TextDirection.ltr,child:Padding(padding:const EdgeInsets.fromLTRB(14,8,18,8),child:Row(crossAxisAlignment:CrossAxisAlignment.start,children:[
      InkWell(onTap:()=>widget.onProfile(message['userId'].toString()),child:avatar(message,radius:20)),const SizedBox(width:12),
      Flexible(child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[Row(mainAxisSize:MainAxisSize.min,children:[
        Flexible(child:Text(name(message),overflow:TextOverflow.ellipsis,style:const TextStyle(fontSize:13,fontWeight:FontWeight.w600))),const SizedBox(width:8),
        if(date!=null)Text(TimeOfDay.fromDateTime(date).format(context),style:TextStyle(fontSize:10,color:Theme.of(context).colorScheme.onSurfaceVariant)),
      ]),const SizedBox(height:5),Container(padding:const EdgeInsets.symmetric(horizontal:16,vertical:11),decoration:BoxDecoration(color:Theme.of(context).colorScheme.surfaceContainerHighest,borderRadius:BorderRadius.circular(18)),
        child:Text(message['text']?.toString()??'',textDirection:TextDirection.rtl,style:const TextStyle(fontSize:15,height:1.4))),])),
    ])));
  }
  Widget empty(String text)=>ListView(physics:const AlwaysScrollableScrollPhysics(),children:[Padding(padding:const EdgeInsets.symmetric(horizontal:30,vertical:50),child:Text(text,textAlign:TextAlign.center,style:TextStyle(color:Theme.of(context).colorScheme.onSurfaceVariant)))]);
  Future<void> create() async {
    if(community==null)return;
    final config=await showModalBottomSheet<Map<String,String>>(context:context,isScrollControlled:true,useSafeArea:true,builder:(_)=>const CreateMatchSheet());
    if(config==null||!mounted)return;await widget.onGame(config['game']!,{'online':'1','action':'create','community':community!['id'].toString(),...config});
  }
  @override void dispose(){timer?.cancel();input.dispose();scroll.dispose();super.dispose();}
  @override Widget build(BuildContext context){
    final colors=Theme.of(context).colorScheme;
    return Column(children:[
      SizedBox(height:58,child:Row(children:[
        if(community!=null)IconButton(onPressed:back,tooltip:'المساحات',icon:const Icon(Icons.chevron_right,size:30))else const SizedBox(width:16),
        if(community!=null)CircleAvatar(radius:17,backgroundColor:colors.primary,child:Text(community!['mark']?.toString()??'S',style:const TextStyle(color:Colors.white,fontSize:14))),
        const SizedBox(width:10),Expanded(child:Text(community?['name']?.toString()??'المساحات',maxLines:1,overflow:TextOverflow.ellipsis,style:const TextStyle(fontWeight:FontWeight.w600,fontSize:17))),
        IconButton(tooltip:'المظهر',onPressed:widget.onTheme,icon:Icon(Theme.of(context).brightness==Brightness.dark?Icons.light_mode_outlined:Icons.dark_mode_outlined)),
        if(community==null)IconButton(onPressed:widget.onInvite,tooltip:'دخول بدعوة',icon:const Icon(Icons.link)),
      ])),
      if(community!=null)Row(children:List.generate(3,(i)=>Expanded(child:InkWell(onTap:()=>setState((){tab=i;if(i==1){scrollToEnd();}else{FocusScope.of(context).unfocus();}}),child:Container(height:49,alignment:Alignment.center,decoration:BoxDecoration(border:Border(bottom:BorderSide(color:tab==i?colors.primary:colors.outlineVariant,width:tab==i?3:.5))),child:Text(['الألعاب (${rooms.length})','الدردشة','متصل (${members.length})'][i],style:TextStyle(color:tab==i?colors.primary:colors.onSurfaceVariant,fontWeight:tab==i?FontWeight.w700:FontWeight.normal,fontSize:14))))))),
      if(error!=null)MaterialBanner(content:Text(error!,style:const TextStyle(fontSize:12)),actions:[TextButton(onPressed:refresh,child:const Text('إعادة المحاولة'))]),
      Expanded(child:RefreshIndicator(onRefresh:refresh,child:community==null?
        (spaces.isEmpty?empty(busy?'تحميل المساحات…':'لا توجد مساحات متاحة'):ListView.separated(physics:const AlwaysScrollableScrollPhysics(),padding:const EdgeInsets.all(8),itemCount:spaces.length,separatorBuilder:(_,__)=>const SizedBox(height:8),itemBuilder:(_,i){final c=spaces[i];return ListTile(shape:RoundedRectangleBorder(borderRadius:BorderRadius.circular(12)),tileColor:colors.surfaceContainerLow,contentPadding:const EdgeInsets.all(18),leading:CircleAvatar(backgroundColor:colors.primaryContainer,child:Text(c['mark']?.toString()??'S')),title:Text(c['name'].toString(),style:const TextStyle(fontWeight:FontWeight.w700)),subtitle:Text('${c['onlineCount']??0} متصل · ${c['gameRoomCount']??0} مباراة\n${c['description']??''}'),trailing:const Icon(Icons.chevron_left),onTap:()=>enter(c));})):
        tab==0?(rooms.isEmpty?empty('لا توجد مباريات حاليًا. أنشئ أول مباراة.'):ListView.separated(physics:const AlwaysScrollableScrollPhysics(),itemCount:rooms.length,itemBuilder:(_,i)=>roomRow(rooms[i]),separatorBuilder:(_,__)=>const Divider(height:1,indent:16,endIndent:16))):
        tab==2?(members.isEmpty?empty('لا يوجد أعضاء متصلون الآن.'):ListView.separated(physics:const AlwaysScrollableScrollPhysics(),itemCount:members.length,itemBuilder:(_,i)=>memberRow(members[i]),separatorBuilder:(_,__)=>const Divider(height:1,indent:16,endIndent:16))):
        messages.isEmpty?empty('قل مرحبًا وابدأ المحادثة.'):ListView.builder(controller:scroll,physics:const AlwaysScrollableScrollPhysics(),padding:const EdgeInsets.symmetric(vertical:12),itemCount:messages.length,itemBuilder:(_,i)=>messageRow(messages[i])),
      )),
      if(community!=null&&tab==0)Padding(padding:const EdgeInsets.fromLTRB(8,8,8,10),child:SizedBox(width:double.infinity,height:46,child:FilledButton(style:FilledButton.styleFrom(shape:RoundedRectangleBorder(borderRadius:BorderRadius.circular(10))),onPressed:create,child:const Text('إنشاء مباراة جديدة',style:TextStyle(fontWeight:FontWeight.w700))))),
      if(community!=null&&tab==1)ChatComposer(controller:input,sending:sending,onSend:send,maxLength:280),
    ]);
  }
}

class ChatComposer extends StatelessWidget {
  const ChatComposer({super.key,required this.controller,required this.sending,required this.onSend,this.onToggle,this.expanded=false,this.focusNode,this.maxLength=160});
  final TextEditingController controller;
  final bool sending,expanded;
  final VoidCallback onSend;
  final VoidCallback? onToggle;
  final FocusNode? focusNode;
  final int maxLength;
  @override Widget build(BuildContext context)=>Material(color:Theme.of(context).colorScheme.surface,child:Container(constraints:const BoxConstraints(minHeight:54),decoration:BoxDecoration(border:Border(top:BorderSide(color:Theme.of(context).dividerColor,width:.5))),child:Row(children:[
    Expanded(child:TextField(controller:controller,focusNode:focusNode,maxLength:maxLength,textInputAction:TextInputAction.send,onSubmitted:(_)=>onSend(),minLines:1,maxLines:3,style:const TextStyle(fontSize:16),decoration:const InputDecoration(counterText:'',hintText:'قل مرحبًا',border:InputBorder.none,contentPadding:EdgeInsets.symmetric(horizontal:16,vertical:12)))),
    if(onToggle!=null)IconButton(onPressed:onToggle,tooltip:expanded?'إخفاء المحادثة':'عرض المحادثة',icon:Icon(expanded?Icons.chat_bubble:Icons.chat_bubble_outline,size:23)),
    IconButton(onPressed:sending?null:onSend,tooltip:'إرسال',icon:const Icon(Icons.send_rounded,size:24)),
  ])));
}

class CreateMatchSheet extends StatefulWidget {
  const CreateMatchSheet({super.key});
  @override State<CreateMatchSheet> createState()=>_CreateMatchSheetState();
}
class _CreateMatchSheetState extends State<CreateMatchSheet> {
  String game='pool';final values=<String,String>{};
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
      ]else const Padding(padding:EdgeInsets.all(14),child:Text('8 كرات · لاعبان · مباشر')),
    ])),const SizedBox(height:12),
    FilledButton(onPressed:()=>Navigator.pop(context,{'game':game,'live':game=='tablesoccer'?'0':'1','players':'0','seats':'0','special':'0','gamemode':'0','break':'0','goalsToWin':'1','passes':'0',...values}),child:const Padding(padding:EdgeInsets.all(12),child:Text('إنشاء المباراة'))),
  ])));
}
