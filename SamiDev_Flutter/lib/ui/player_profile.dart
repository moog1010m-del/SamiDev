import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import '../runtime/api.dart';

class ProfileDecoration extends StatelessWidget {
  const ProfileDecoration(this.name,{super.key,this.size=22});
  final String name;
  final double size;
  @override Widget build(BuildContext context)=>ExcludeSemantics(child:Image.asset(
    'assets/runtime/platform/assets/profile/raster/$name.webp',width:size,height:size,fit:BoxFit.contain));
}
class ProfileStars extends StatelessWidget {
  const ProfileStars({super.key,this.size=17,this.count=5});
  final double size;
  final int count;
  // The web profile's decorative motif, not an invented rating or achievement.
  @override Widget build(BuildContext context)=>ExcludeSemantics(child:Row(mainAxisSize:MainAxisSize.min,
    children:List.generate(5,(i)=>Opacity(opacity:i<count?1.0:0.22,child:ProfileDecoration('star',size:size)))));
}
class PlayerAvatar extends StatelessWidget {
  const PlayerAvatar({super.key,required this.api,required this.user,this.radius=27,this.framed=false});
  final PlatformApi api;
  final Map user;
  final double radius;
  final bool framed;
  @override Widget build(BuildContext context){
    final id=user['userId']??user['accountId']??user['id'];
    Widget fallback()=>Image.asset('assets/runtime/images/default-avatar.png',width:radius*2,height:radius*2,fit:BoxFit.cover);
    return Container(width:radius*2+4,height:radius*2+4,padding:const EdgeInsets.all(2),
      decoration:BoxDecoration(shape:BoxShape.circle,border:framed?Border.all(color:const Color(0xffb89137),width:1.5):null),
      child:ClipOval(child:id is String&&RegExp(r'^[A-Za-z0-9_-]{1,64}$').hasMatch(id)&&user['hasAvatar']!=false
        ? Image.network(api.policy.upstream('/api/avatar/$id').toString(),width:radius*2,height:radius*2,fit:BoxFit.cover,
          loadingBuilder:(_,child,progress)=>progress==null?child:fallback(),errorBuilder:(_,__,___)=>fallback()) : fallback()));
  }
}

Future<void> showPlayerProfile(BuildContext context,{required PlatformApi api,required String id,required VoidCallback onUnauthorized,String roomId=''}) async {
  if(!RegExp(r'^[A-Za-z0-9_-]{1,64}$').hasMatch(id))return;
  await showModalBottomSheet<void>(context:context,isScrollControlled:true,useSafeArea:true,showDragHandle:true,
    constraints:const BoxConstraints(maxWidth:460),builder:(_)=>PlayerProfileSheet(api:api,id:id,roomId:roomId,onUnauthorized:onUnauthorized));
}
class PlayerProfileSheet extends StatefulWidget {
  const PlayerProfileSheet({super.key,required this.api,required this.id,required this.onUnauthorized,this.roomId=''});
  final PlatformApi api;
  final String id,roomId;
  final VoidCallback onUnauthorized;
  @override State<PlayerProfileSheet> createState()=>_PlayerProfileSheetState();
}
class _PlayerProfileSheetState extends State<PlayerProfileSheet> {
  Map<String,dynamic>? user;
  String? error;
  bool loading=true,busy=false,reporting=false;
  final report=TextEditingController();
  Future<Map<String,dynamic>> request(String path,{Map<String,dynamic>? body}) async {
    final response=await widget.api.request(body==null?'GET':'POST',path,body:body==null?null:utf8.encode(jsonEncode(body)));
    if(response.status==401){widget.onUnauthorized();throw StateError('انتهت الجلسة، سجّل الدخول مجددًا');}
    final data=response.json;
    if(response.status!=200||data['ok']==false)throw StateError(data['message']?.toString()??'تعذر إكمال الطلب');
    return data;
  }
  @override void initState(){super.initState();unawaited(load());}
  @override void dispose(){report.dispose();super.dispose();}
  Future<void> load() async {
    setState((){loading=true;error=null;});
    try{final data=await request('/api/public-profile/${widget.id}');if(mounted)setState(()=>user=Map<String,dynamic>.from(data['user']));}
    catch(e){if(mounted)setState(()=>error=e is StateError?e.message.toString():'تعذر تحميل بطاقة اللاعب. حاول مجددًا.');}
    finally{if(mounted)setState(()=>loading=false);}
  }
  Future<void> action(String kind) async {
    if(busy||user==null)return;setState((){busy=true;error=null;});
    try{
      final u=user!;
      if(kind=='friend'){
        await request(u['relation']=='incoming'?'/api/friends/respond':'/api/friends/request',
          body:u['relation']=='incoming'?{'userId':widget.id,'accept':true}:{'username':u['username']});
      }else if(kind=='reputation'){
        await request('/api/users/${widget.id}/reputation',body:{'source':'profile'});
      }else if(kind=='report'){
        final text=report.text.trim();if(text.isEmpty)throw StateError('اكتب وصف المشكلة أولًا');
        await request('/api/users/${widget.id}/report',body:{'message':text,if(widget.roomId.isNotEmpty)'roomId':widget.roomId});
        if(mounted){setState(()=>reporting=false);report.clear();ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content:Text('تم إرسال البلاغ للإدارة')));}
      }
      final data=await request('/api/public-profile/${widget.id}');if(mounted)setState(()=>user=Map<String,dynamic>.from(data['user']));
    }catch(e){if(mounted)setState(()=>error=e is StateError?e.message.toString():'تعذر إكمال العملية. حاول مجددًا.');}
    finally{if(mounted)setState(()=>busy=false);}
  }
  Widget stat(String label,String value,Widget icon)=>Expanded(child:Column(children:[Text(label,style:TextStyle(fontSize:12,color:Theme.of(context).colorScheme.onSurfaceVariant)),const SizedBox(height:7),Row(mainAxisAlignment:MainAxisAlignment.center,children:[icon,const SizedBox(width:5),Flexible(child:Text(value,style:const TextStyle(fontWeight:FontWeight.w700,fontSize:16)))] )]));
  @override Widget build(BuildContext context){
    final u=user,colors=Theme.of(context).colorScheme;
    final self=u?['relation']=='self',relation=u?['relation'];
    final remaining=(u?['reputationDailyRemaining'] as num?)?.toInt()??0;
    return ConstrainedBox(constraints:BoxConstraints(maxHeight:MediaQuery.sizeOf(context).height*.85),child:SingleChildScrollView(
      padding:EdgeInsets.fromLTRB(20,0,20,24+MediaQuery.viewInsetsOf(context).bottom),child:Column(mainAxisSize:MainAxisSize.min,children:[
        Row(children:[const Expanded(child:Text('بطاقة اللاعب',style:TextStyle(fontWeight:FontWeight.w700,fontSize:18))),IconButton(tooltip:'إغلاق',onPressed:()=>Navigator.pop(context),icon:const Icon(Icons.close))]),
        if(loading)const Padding(padding:EdgeInsets.all(32),child:CircularProgressIndicator()),
        if(u!=null)...[
          Container(width:double.infinity,padding:const EdgeInsets.symmetric(vertical:20),decoration:BoxDecoration(
            borderRadius:BorderRadius.circular(20),gradient:LinearGradient(colors:[colors.primaryContainer,colors.surfaceContainerLow])),
            child:Column(children:[PlayerAvatar(api:widget.api,user:u,radius:48,framed:true),const SizedBox(height:12),
              Row(mainAxisAlignment:MainAxisAlignment.center,children:[ProfileDecoration(u['nameBadge']=='badge_crown'?'trophy':(u['nameBadge']=='badge_fire'?'reputation-flame':'palm-swords'),size:30),const SizedBox(width:8),Flexible(child:Text(u['displayName']?.toString()??u['username']?.toString()??'لاعب',textAlign:TextAlign.center,style:const TextStyle(fontSize:23,fontWeight:FontWeight.w700)))]),
              const SizedBox(height:7),ProfileStars(size:23,count:(u['starsCount'] as num?)?.toInt()??5),if(u['username']!=null)Padding(padding:const EdgeInsets.only(top:7),child:Text('@${u['username']}',textDirection:TextDirection.ltr,style:TextStyle(color:colors.onSurfaceVariant))),
            ])),
          Padding(padding:const EdgeInsets.symmetric(vertical:23),child:Row(children:[
            stat('لاعب منذ','${u['accountAgeDays']??0} يوم',const Icon(Icons.calendar_today_outlined,size:18)),
            stat('الفوز','${u['wins']??0}',const ProfileDecoration('trophy')),
            stat('السمعة','${u['reputation']??0}',const ProfileDecoration('reputation-flame')),
          ])),
          if(!self)Wrap(alignment:WrapAlignment.center,spacing:8,runSpacing:8,children:[
            FilledButton.icon(onPressed:busy||relation=='friend'||relation=='outgoing'?null:()=>action('friend'),icon:const Icon(Icons.person_add_outlined,size:19),label:Text(switch(relation){'friend'=>'صديق','outgoing'=>'تم إرسال الطلب','incoming'=>'قبول الصداقة',_=>'إضافة صديق'})),
            OutlinedButton.icon(onPressed:busy||remaining<=0||u['reputationGrantedToday']==true?null:()=>action('reputation'),icon:const ProfileDecoration('reputation-flame',size:19),label:Text(u['reputationGrantedToday']==true?'مُنحت اليوم':'منح سمعة ($remaining/5)')),
            TextButton.icon(onPressed:busy?null:()=>setState(()=>reporting=!reporting),icon:const Icon(Icons.flag_outlined,size:19),label:const Text('إبلاغ')),
          ]),
          if(reporting)...[TextField(controller:report,maxLength:500,maxLines:3,decoration:const InputDecoration(labelText:'وصف المشكلة',border:OutlineInputBorder())),FilledButton(onPressed:busy?null:()=>action('report'),child:const Text('إرسال للإدارة'))],
          if(busy)const Padding(padding:EdgeInsets.all(12),child:LinearProgressIndicator()),
        ],
        if(error!=null)...[Padding(padding:const EdgeInsets.all(12),child:Text(error!,style:TextStyle(color:colors.error))),if(u==null&&!loading)TextButton(onPressed:load,child:const Text('إعادة المحاولة'))],
      ])));
  }
}
