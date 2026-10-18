import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import '../runtime/api.dart';
import 'profile_details.dart';
import 'sticker_art.dart';

class ProfileDecoration extends StatelessWidget {
  const ProfileDecoration(this.name,{super.key,this.size=22});
  final String name;
  final double size;
  @override Widget build(BuildContext context){
    const cells={'star':Offset(0,0),'reputation-flame':Offset(1,0),'trophy':Offset(2,0),'calendar':Offset(3,0),'friend':Offset(0,1),'collection':Offset(1,1),'report':Offset(2,1)};
    final cell=cells[name];
    if(cell==null)return ExcludeSemantics(child:Image.asset('assets/runtime/platform/assets/profile/raster/$name.webp',width:size,height:size,fit:BoxFit.contain));
    return ExcludeSemantics(child:SizedBox(width:size,height:size,child:ClipRect(child:OverflowBox(
      alignment:Alignment.topLeft,minWidth:size*4,maxWidth:size*4,minHeight:size*2,maxHeight:size*2,
      child:Transform.translate(offset:Offset(-cell.dx*size,-cell.dy*size),child:Image.asset(
        'assets/runtime/platform/assets/profile/identity/profile-atlas.png',width:size*4,height:size*2,fit:BoxFit.fill))))));
  }
}
class ProfileStars extends StatelessWidget {
  const ProfileStars({super.key,this.size=17,this.count=0});
  final double size;
  final int count;
  // The server's purchased star count is shared by own and public profiles.
  @override Widget build(BuildContext context)=>ExcludeSemantics(child:Row(mainAxisSize:MainAxisSize.min,
    children:List.generate(count.clamp(0,5),(i)=>ProfileDecoration('star',size:size))));
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

Future<void> showPlayerProfile(BuildContext context,{required PlatformApi api,required String id,required VoidCallback onUnauthorized,String roomId='',String communityId=''}) async {
  if(!RegExp(r'^[A-Za-z0-9_-]{1,64}$').hasMatch(id))return;
  await showModalBottomSheet<void>(context:context,isScrollControlled:true,useSafeArea:true,showDragHandle:true,
    constraints:const BoxConstraints(maxWidth:460),builder:(_)=>PlayerProfileSheet(api:api,id:id,roomId:roomId,communityId:communityId,onUnauthorized:onUnauthorized));
}
class PlayerProfileSheet extends StatefulWidget {
  const PlayerProfileSheet({super.key,required this.api,required this.id,required this.onUnauthorized,this.roomId='',this.communityId=''});
  final PlatformApi api;
  final String id,roomId,communityId;
  final VoidCallback onUnauthorized;
  @override State<PlayerProfileSheet> createState()=>_PlayerProfileSheetState();
}
class _PlayerProfileSheetState extends State<PlayerProfileSheet> {
  Map<String,dynamic>? user;
  bool canModerate=false,canAssignModerators=false;
  String? error;
  bool loading=true,busy=false,reporting=false,full=false;
  final report=TextEditingController();
  Future<Map<String,dynamic>> request(String path,{Map<String,dynamic>? body}) async {
    final response=await widget.api.request(body==null?'GET':'POST',path,body:body==null?null:utf8.encode(jsonEncode(body)));
    if(response.status==401){widget.onUnauthorized();throw StateError('انتهت الجلسة، سجّل الدخول مجددًا');}
    final data=response.json;
    if(response.status!=200||data['ok']==false)throw StateError(data['message']?.toString()??'تعذر إكمال الطلب');
    return data;
  }
  @override void initState(){super.initState();unawaited(load());if(widget.communityId.isNotEmpty)unawaited(loadModeration());}
  @override void dispose(){report.dispose();super.dispose();}
  Future<void> load() async {
    setState((){loading=true;error=null;});
    try{final data=await request('/api/public-profile/${widget.id}');if(mounted)setState(()=>user=Map<String,dynamic>.from(data['user']));}
    catch(e){if(mounted)setState(()=>error=e is StateError?e.message.toString():'تعذر تحميل بطاقة اللاعب. حاول مجددًا.');}
    finally{if(mounted)setState(()=>loading=false);}
  }
  Future<void> loadModeration() async {
    try{
      final result=await request('/api/communities/${widget.communityId}');
      final capabilities=result['capabilities'] as Map? ?? {};
      if(mounted)setState((){canModerate=capabilities['canModerate']==true;canAssignModerators=capabilities['canAssignModerators']==true;});
    }catch(_){ }
  }
  Future<void> moderate(String operation,String title) async {
    if(busy)return;
    final confirmed=await showDialog<bool>(context:context,builder:(context)=>AlertDialog(
      title:Text(title),content:Text('تنفيذ الإجراء على هذا الحساب في المساحة الحالية؟'),actions:[
        TextButton(onPressed:()=>Navigator.pop(context,false),child:const Text('إلغاء')),
        FilledButton(onPressed:()=>Navigator.pop(context,true),child:const Text('تأكيد'))]));
    if(confirmed!=true||!mounted)return;
    setState((){busy=true;error=null;});
    try{await request('/api/communities/${widget.communityId}/moderation',body:{'targetUserId':widget.id,'action':operation});
      if(mounted)ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content:Text('تم تنفيذ الإجراء في هذه المساحة')));
    }catch(e){if(mounted)setState(()=>error=e is StateError?e.message.toString():'تعذر تنفيذ الإجراء');}
    finally{if(mounted)setState(()=>busy=false);}
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
        Row(children:[Expanded(child:Text(full?'الملف الشخصي':'بطاقة اللاعب',style:const TextStyle(fontWeight:FontWeight.w700,fontSize:18))),IconButton(tooltip:full?'العودة إلى البطاقة المختصرة':'إغلاق',onPressed:()=>full?setState(()=>full=false):Navigator.pop(context),icon:Icon(full?Icons.arrow_back:Icons.close))]),
        if(loading)const Padding(padding:EdgeInsets.all(32),child:CircularProgressIndicator()),
        if(u!=null)...[
          ClipRRect(borderRadius:BorderRadius.circular(16),child:Image.asset(
            {'banner_dunes','banner_garden','banner_canyon'}.contains(u['profileBanner'])
              ? 'assets/runtime/platform/assets/cosmetics/${u['profileBanner']}.webp'
              : 'assets/runtime/platform/assets/profile/identity/samidev-night-cover.png',
            width:double.infinity,height:145,fit:BoxFit.cover)),
          Transform.translate(offset:const Offset(0,-52),child:PlayerAvatar(api:widget.api,user:u,radius:58,framed:true)),
          Transform.translate(offset:const Offset(0,-32),child:Row(mainAxisAlignment:MainAxisAlignment.center,children:[
            StickerArtwork(asset:u['nameBadgeAsset']?.toString()??'',size:22),const SizedBox(width:3),
            Flexible(child:Text(u['displayName']?.toString()??u['username']?.toString()??'لاعب',maxLines:1,overflow:TextOverflow.ellipsis,style:const TextStyle(fontSize:21,fontWeight:FontWeight.w700))),
            const SizedBox(width:6),ProfileStars(size:18,count:(u['starsCount'] as num?)?.toInt()??0),
          ])),
          if((u['bio']?.toString()??'').isNotEmpty)Padding(padding:const EdgeInsets.symmetric(horizontal:18),child:Text(u['bio'].toString(),textAlign:TextAlign.center,style:TextStyle(fontSize:13,height:1.7,color:colors.onSurfaceVariant))),
          Padding(padding:const EdgeInsets.symmetric(vertical:23),child:Row(children:[
            stat('لاعب منذ','${u['accountAgeDays']??0} يوم',const ProfileDecoration('calendar',size:18)),
            stat('الفوز','${u['wins']??0}',const ProfileDecoration('trophy')),
            stat('السمعة','${u['reputation']??0}',const ProfileDecoration('reputation-flame')),
          ])),
          if(!self)Wrap(alignment:WrapAlignment.center,spacing:8,runSpacing:8,children:[
            FilledButton.icon(onPressed:busy||relation=='friend'||relation=='outgoing'?null:()=>action('friend'),icon:const Icon(Icons.person_add_outlined,size:19),label:Text(switch(relation){'friend'=>'صديق','outgoing'=>'تم إرسال الطلب','incoming'=>'قبول الصداقة',_=>'إضافة صديق'})),
            OutlinedButton.icon(onPressed:busy||remaining<=0||u['reputationGrantedToday']==true?null:()=>action('reputation'),icon:const ProfileDecoration('reputation-flame',size:19),label:Text(u['reputationGrantedToday']==true?'مُنحت اليوم':'منح سمعة ($remaining/5)')),
            TextButton.icon(onPressed:busy?null:()=>setState(()=>reporting=!reporting),icon:const Icon(Icons.flag_outlined,size:19),label:const Text('إبلاغ')),
          ]),
          if(canModerate&&u['isSelf']!=true)PopupMenuButton<String>(
            enabled:!busy,tooltip:'إدارة العضو في المساحة',
            onSelected:(value){const names={'kick':'إخراج لمدة دقيقة','mute':'كتم ١٠ دقائق','unmute':'إلغاء الكتم','ban':'حظر من المساحة','unban':'فك حظر المساحة','grant_moderator':'تعيين مشرف للمساحة','revoke_moderator':'سحب إشراف المساحة'};unawaited(moderate(value,names[value]!));},
            itemBuilder:(_)=>[const PopupMenuItem(value:'kick',child:Text('إخراج لمدة دقيقة')),const PopupMenuItem(value:'mute',child:Text('كتم ١٠ دقائق')),const PopupMenuItem(value:'unmute',child:Text('إلغاء الكتم')),const PopupMenuItem(value:'ban',child:Text('حظر من المساحة')),const PopupMenuItem(value:'unban',child:Text('فك حظر المساحة')),
              if(canAssignModerators)...[const PopupMenuItem(value:'grant_moderator',child:Text('تعيين مشرف للمساحة')),const PopupMenuItem(value:'revoke_moderator',child:Text('سحب إشراف المساحة'))]],
            child:const Padding(padding:EdgeInsets.all(12),child:Text('إدارة العضو في المساحة'))),
          if(reporting)...[TextField(controller:report,maxLength:500,maxLines:3,decoration:const InputDecoration(labelText:'وصف المشكلة',border:OutlineInputBorder())),FilledButton(onPressed:busy?null:()=>action('report'),child:const Text('إرسال للإدارة'))],
          if(busy)const Padding(padding:EdgeInsets.all(12),child:LinearProgressIndicator()),
          const SizedBox(height:12),
          if(!full)SizedBox(width:double.infinity,child:OutlinedButton(
            onPressed:()=>setState(()=>full=true),child:const Text('الملف الكامل والمقتنيات والإحصاءات'))),
          if(full)ProfileDetails(user:u),
        ],
        if(error!=null)...[Padding(padding:const EdgeInsets.all(12),child:Text(error!,style:TextStyle(color:colors.error))),if(u==null&&!loading)TextButton(onPressed:load,child:const Text('إعادة المحاولة'))],
      ])));
  }
}
