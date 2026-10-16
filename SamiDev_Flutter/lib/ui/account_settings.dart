import 'dart:convert';
import 'package:flutter/material.dart';
import '../runtime/api.dart';
import '../runtime/native_auth.dart';
import 'auth_screen.dart';

class AccountSettings extends StatefulWidget {
  const AccountSettings({super.key,required this.api,required this.user,required this.onChanged,this.onTheme});
  final VoidCallback? onTheme;
  final PlatformApi api;
  final Map<String,dynamic> user;
  final Future<void> Function(Map<String,dynamic>) onChanged;
  @override State<AccountSettings> createState()=>_AccountSettingsState();
}
class _AccountSettingsState extends State<AccountSettings> {
  late Map<String,dynamic> user=widget.user;
  late final name=TextEditingController(text:user['username']?.toString()??'');
  bool busy=false;
  String? error;
  @override void dispose(){name.dispose();super.dispose();}
  Future<void> rename() async {
    if(busy)return;
    if(!RegExp(r'^[A-Za-z0-9_]{3,20}$').hasMatch(name.text.trim())){setState(()=>error='استخدم ٣–٢٠ حرفًا إنجليزيًا أو رقمًا أو _ بدون @');return;}
    final approved=await showDialog<bool>(context:context,builder:(c)=>AlertDialog(title:const Text('تغيير اسم المستخدم'),content:Text(user['freeRenameAvailable']==true?'هذا التغيير مجاني.':'ستُستهلك بطاقة تغيير اسم واحدة عند النجاح.'),actions:[TextButton(onPressed:()=>Navigator.pop(c,false),child:const Text('إلغاء')),FilledButton(onPressed:()=>Navigator.pop(c,true),child:const Text('تأكيد'))]));
    if(approved!=true||!mounted)return;
    setState((){busy=true;error=null;});
    try{
      final response=await widget.api.request('PATCH','/api/profile',body:utf8.encode(jsonEncode({'username':name.text.trim()})));
      final data=response.json;
      if(response.status!=200)throw StateError(data['message']?.toString()??'تعذر تغيير الاسم');
      final updated=Map<String,dynamic>.from(data['user']);
      await widget.onChanged(updated);
      if(mounted)setState((){user=updated;name.text=updated['username']?.toString()??'';});
    }catch(e){if(mounted)setState(()=>error=e is StateError?e.message.toString():'تعذر الاتصال');}
    finally{if(mounted)setState(()=>busy=false);}
  }
  Future<void> logout() async {
    final accepted=await showDialog<bool>(context:context,builder:(c)=>AlertDialog(title:const Text('تسجيل الخروج'),content:Text(user['isGuest']==true?'سيُنشأ ضيف جديد. اربط بريدك أولًا إذا أردت استرداد تقدمك.':'ستعود للعب كضيف، ويمكنك الدخول لحسابك لاحقًا من الإعدادات.'),actions:[TextButton(onPressed:()=>Navigator.pop(c,false),child:const Text('إلغاء')),FilledButton(onPressed:()=>Navigator.pop(c,true),child:const Text('خروج'))]));
    if(accepted!=true||!mounted)return;setState(()=>busy=true);
    try{
      final response=await widget.api.request('POST','/api/auth/logout',body:utf8.encode('{}'));
      if(response.status!=200)throw StateError('تعذر الخروج');
      final guest=await NativeAuth(widget.api).guest();await widget.onChanged(guest);
      if(mounted)setState((){user=guest;name.text=guest['username']?.toString()??'';});
    }catch(_){if(mounted)setState(()=>error='تعذر الخروج. حاول مجددًا');}finally{if(mounted)setState(()=>busy=false);}
  }
  Future<void> notifications() async {
    try{
      final response=await widget.api.request('GET','/api/communities');
      if(response.status!=200)throw StateError('تعذر تحميل الإشعارات');
      final rows=(response.json['notifications'] as List? ?? []).whereType<Map>().toList();
      if(!mounted)return;
      await showDialog<void>(context:context,builder:(c)=>AlertDialog(title:const Text('الإشعارات'),content:SizedBox(width:400,child:SingleChildScrollView(child:Column(mainAxisSize:MainAxisSize.min,children:[if(rows.isEmpty)const Text('لا توجد إشعارات حاليًا'),for(final n in rows)ListTile(title:Text(n['sender']?.toString()??'سيتم'),subtitle:Text(n['text']?.toString()??''))]))),actions:[TextButton(onPressed:()=>Navigator.pop(c),child:const Text('إغلاق'))]));
    }catch(_){if(mounted)setState(()=>error='تعذر تحميل الإشعارات');}
  }
  Future<void> account() async {
    if(widget.api.firebase==null){setState(()=>error='ربط البريد يتطلب تفعيل Firebase على الخادم أولًا. اللعب كضيف متاح.');return;}
    final auth=NativeAuth(widget.api,linkGuest:user['isGuest']==true);
    await Navigator.of(context).push(MaterialPageRoute<void>(builder:(c)=>Scaffold(appBar:AppBar(title:const Text('البريد وكلمة المرور')),body:AuthScreen(auth:auth,onAuthenticated:(updated)async{await widget.onChanged(updated);if(mounted){setState((){user=updated;name.text=updated['username']?.toString()??'';});if(c.mounted)Navigator.pop(c);}}))));
    auth.clearPending();
  }
  @override Widget build(BuildContext context)=>Scaffold(appBar:AppBar(title:const Text('إعدادات المنصة')),body:ListView(padding:const EdgeInsets.all(24),children:[
    const Text('المظهر',style:TextStyle(fontSize:18,fontWeight:FontWeight.bold)),
    if(widget.onTheme!=null)TextButton(onPressed:widget.onTheme,child:const Text('تبديل المظهر الفاتح والداكن')),
    TextButton(onPressed:notifications,child:const Text('الإشعارات')),
    const Divider(),const Text('الحساب',style:TextStyle(fontSize:18,fontWeight:FontWeight.bold)),
    Text(user['isGuest']==true?'تلعب كضيف. اربط بريدًا جديدًا لحفظ تقدمك والوصول إليه من جهاز آخر.':'حسابك مرتبط. يمكنك الدخول إلى حساب آخر من هنا.'),
    const SizedBox(height:16),FilledButton(onPressed:busy?null:account,child:const Text('ربط البريد أو تسجيل الدخول')),
    const SizedBox(height:28),TextField(controller:name,enabled:!busy,textDirection:TextDirection.ltr,decoration:const InputDecoration(labelText:'اسم المستخدم بدون @')),
    const SizedBox(height:12),Text(user['freeRenameAvailable']==true?'تغيير مجاني مرة واحدة.':'بطاقات تغيير الاسم: ${user['renameCredits']??0} · تتوفر في المتجر.'),
    TextButton(onPressed:busy?null:rename,child:const Text('حفظ اسم المستخدم')),
    TextButton(onPressed:busy?null:logout,child:const Text('تسجيل الخروج والعودة كضيف')),
    if(error!=null)Text(error!,style:TextStyle(color:Theme.of(context).colorScheme.error)),
  ]));
}
