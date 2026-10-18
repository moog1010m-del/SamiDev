import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// Public legal text is shared with the website and readable offline.
class PlazrLegalPage extends StatefulWidget {
  const PlazrLegalPage({super.key,this.pageId='privacy',this.onAccount});
  final String pageId;
  final VoidCallback? onAccount;
  @override State<PlazrLegalPage> createState()=>_PlazrLegalPageState();
}
class _PlazrLegalPageState extends State<PlazrLegalPage>{
  late Future<Map<String,dynamic>> content=load();
  Future<Map<String,dynamic>> load()async=>Map<String,dynamic>.from(jsonDecode(await rootBundle.loadString('assets/runtime/platform/legal-content.json')));
  @override Widget build(BuildContext context)=>Directionality(textDirection:TextDirection.rtl,child:Scaffold(
    appBar:AppBar(title:const Text('Plazr · المعلومات والوثائق')),
    body:FutureBuilder<Map<String,dynamic>>(future:content,builder:(context,snapshot){
      if(snapshot.hasError)return Center(child:TextButton(onPressed:()=>setState(()=>content=load()),child:const Text('تعذر تحميل الوثيقة · إعادة المحاولة')));
      if(!snapshot.hasData)return const Center(child:CircularProgressIndicator());
      final data=snapshot.data!,pages=(data['pages'] as List).cast<Map<String,dynamic>>();
      final page=pages.firstWhere((p)=>p['id']==widget.pageId,orElse:()=>pages.first);
      final colors=Theme.of(context).colorScheme;
      return Align(alignment:Alignment.topCenter,child:ConstrainedBox(constraints:const BoxConstraints(maxWidth:820),child:ListView(padding:const EdgeInsets.all(22),children:[
        Text(page['title'].toString(),style:Theme.of(context).textTheme.headlineSmall),const SizedBox(height:12),SelectableText(page['summary'].toString()),const SizedBox(height:10),Text('نسخة المراجعة: ${data['revision']}',style:TextStyle(color:colors.onSurfaceVariant,fontSize:12)),
        if(data['draft']==true)Container(margin:const EdgeInsets.symmetric(vertical:22),padding:const EdgeInsets.all(18),decoration:BoxDecoration(color:colors.tertiaryContainer,borderRadius:BorderRadius.circular(14)),child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[const Text('مسودة للمراجعة — ليست وثيقة إطلاق معتمدة',style:TextStyle(fontWeight:FontWeight.w700)),const SizedBox(height:10),for(final item in data['reviewItems'] as List)Padding(padding:const EdgeInsets.only(bottom:8),child:Text('• $item',style:const TextStyle(fontSize:13,height:1.7)))])),
        for(final section in (page['sections'] as List).cast<Map<String,dynamic>>())...[
          Padding(padding:const EdgeInsets.only(top:24,bottom:10),child:Text(section['title'].toString(),style:Theme.of(context).textTheme.titleLarge)),
          for(final text in section['paragraphs'] as List)Padding(padding:const EdgeInsets.only(bottom:12),child:SelectableText(text.toString(),style:const TextStyle(fontSize:15,height:1.9))),
        ],
        const Divider(height:36),Row(children:[Expanded(child:SelectableText(data['supportEmail'].toString(),textDirection:TextDirection.ltr)),IconButton(tooltip:'نسخ بريد الدعم',onPressed:()async{await Clipboard.setData(ClipboardData(text:data['supportEmail'].toString()));if(context.mounted)ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content:Text('تم نسخ بريد الدعم')));},icon:const Icon(Icons.copy_outlined))]),
        if(widget.onAccount!=null)TextButton(onPressed:widget.onAccount,child:const Text('فتح إعدادات الحساب والحذف')),
        Wrap(spacing:8,children:[for(final other in pages)if(other['id']!=page['id'])TextButton(onPressed:()=>Navigator.pushReplacement(context,MaterialPageRoute<void>(builder:(_)=>PlazrLegalPage(pageId:other['id'].toString(),onAccount:widget.onAccount))),child:Text(other['title'].toString()))]),
      ])));
    }),
  ));
}
