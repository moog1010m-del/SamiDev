import 'dart:convert';
import 'package:flutter/material.dart';
import '../runtime/api.dart';

const reportReasons={
 'harassment':'هذا الشخص يضايقني أو يتنمر.',
 'cheating':'هذا الشخص يغش في اللعب.',
 'abuse':'إساءة أو خطاب كراهية.',
 'profile':'اسم المستخدم أو الصورة غير لائقين.',
 'threat':'تهديد بالعنف في الحياة الواقعية.',
 'exploitation':'استغلال أو تحرش جنسي.',
 'spam':'رسائل مزعجة أو احتيال.',
 'other':'سبب آخر.',
};
class SafetySheet extends StatefulWidget {
 const SafetySheet({super.key,required this.api,required this.userId,required this.username,required this.onUnauthorized,this.roomId=''});
 final PlatformApi api;
 final String userId,username,roomId;
 final VoidCallback onUnauthorized;
 @override State<SafetySheet> createState()=>_SafetySheetState();
}
class _SafetySheetState extends State<SafetySheet>{
 final detail=TextEditingController();String? reason,error;bool block=true,busy=false;
 @override void dispose(){detail.dispose();super.dispose();}
 Future<void> submit(bool report)async{
  if(busy||report&&reason==null)return;
  setState((){busy=true;error=null;});
  try{
   final response=await widget.api.request('POST','/api/users/${widget.userId}/${report?'report':'block'}',body:utf8.encode(jsonEncode(report?{'reason':reason,'message':detail.text.trim(),'roomId':widget.roomId,'block':block}:{'blocked':true})));
   if(!mounted)return;
   if(response.status==401){widget.onUnauthorized();throw StateError('انتهت الجلسة');}
   if(response.status!=200)throw StateError(response.json['message']?.toString()??'تعذر تنفيذ الطلب');
   ScaffoldMessenger.of(context).showSnackBar(SnackBar(content:Text(report?(response.json['blocked']==true?'تم الحظر وإرسال البلاغ للإدارة':'تم إرسال البلاغ للإدارة'):'تم حظر المستخدم')));
   Navigator.pop(context,true);
  }catch(e){if(mounted)setState(()=>error=e is StateError?e.message.toString():'تعذر تنفيذ الطلب؛ أعد المحاولة');}
  finally{if(mounted)setState(()=>busy=false);}
 }
 @override Widget build(BuildContext context)=>PopScope(canPop:!busy,child:SafeArea(child:Padding(padding:EdgeInsets.only(bottom:MediaQuery.viewInsetsOf(context).bottom),child:SizedBox(height:MediaQuery.sizeOf(context).height*.88,child:Column(children:[
  ListTile(title:const Text('الحظر والإبلاغ',style:TextStyle(fontSize:20,fontWeight:FontWeight.w600)),trailing:IconButton(tooltip:'إغلاق',onPressed:busy?null:()=>Navigator.pop(context),icon:const Icon(Icons.close))),
  Expanded(child:ListView(padding:const EdgeInsets.symmetric(horizontal:20),children:[
   Text(widget.username,style:const TextStyle(fontWeight:FontWeight.bold)),const SizedBox(height:10),
   const Text('الحظر يخفي رسائله ويمنع طلبات الصداقة. لا يغيّر مباراة قائمة.',style:TextStyle(height:1.6)),const SizedBox(height:14),const Text('اختر سببًا'),
   for(final entry in reportReasons.entries)ListTile(contentPadding:EdgeInsets.zero,enabled:!busy,title:Text(entry.value,style:const TextStyle(fontSize:14)),trailing:reason==entry.key?const Icon(Icons.check_circle_outline):null,onTap:()=>setState(()=>reason=entry.key)),
   TextField(controller:detail,enabled:!busy,maxLength:500,maxLines:3,decoration:const InputDecoration(labelText:'تفاصيل إضافية (اختياري)',border:OutlineInputBorder())),
   CheckboxListTile(contentPadding:EdgeInsets.zero,value:block,onChanged:busy?null:(value)=>setState(()=>block=value==true),title:const Text('حظر المستخدم أيضًا')),
   if(error!=null)Text(error!,style:TextStyle(color:Theme.of(context).colorScheme.error)),
  ])),
  Padding(padding:const EdgeInsets.all(16),child:Row(children:[Expanded(child:FilledButton(onPressed:busy||reason==null?null:()=>submit(true),child:Text(busy?'جارٍ الإرسال…':'إرسال البلاغ'))),const SizedBox(width:10),OutlinedButton(onPressed:busy?null:()=>submit(false),child:const Text('حظر فقط'))])),
 ])))));
}
