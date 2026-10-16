import 'package:flutter/material.dart';
import '../runtime/api.dart';
import 'sticker_art.dart';

Future<Map<String,dynamic>?> pickChatSticker(BuildContext context,PlatformApi api) async {
  try {
    final response=await api.request('GET','/api/store');
    if(response.status!=200)throw StateError('تعذر تحميل الملصقات');
    final items=(response.json['catalog'] as List? ?? []).whereType<Map>().where((item)=>item['slot']=='name_badge'&&item['owned']==true).map((item)=>Map<String,dynamic>.from(item)).toList();
    if(!context.mounted)return null;
    return await showModalBottomSheet<Map<String,dynamic>>(context:context,showDragHandle:true,builder:(context)=>SafeArea(child:Padding(padding:const EdgeInsets.all(20),child:Column(mainAxisSize:MainAxisSize.min,children:[const Text('ملصقاتي',style:TextStyle(fontSize:18,fontWeight:FontWeight.w600)),const SizedBox(height:16),if(items.isEmpty)const Padding(padding:EdgeInsets.all(24),child:Text('الملصقات التي تملكها من المتجر تظهر هنا.')),Flexible(child:SingleChildScrollView(child:Wrap(spacing:12,runSpacing:12,children:items.map((item)=>IconButton(tooltip:item['name']?.toString(),onPressed:()=>Navigator.pop(context,item),icon:StickerArtwork(asset:item['asset'].toString(),size:64))).toList())))]))));
  }catch(_){if(context.mounted)ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content:Text('تعذر تحميل الملصقات. حاول مجددًا.')));return null;}
}
