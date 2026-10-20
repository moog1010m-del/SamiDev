import 'dart:math';
import 'package:flutter/material.dart';
import 'chat_cosmetic.dart';
import 'sticker_art.dart';

/// Transparent history floats over the unchanged game surface. Outside text
/// entry it passes touches through to the game, including between bubbles.
class FloatingGameChat extends StatelessWidget {
  const FloatingGameChat({super.key,required this.messages,required this.roster,required this.seat,required this.controller,required this.interactive});
  final List<Map<String,dynamic>> messages,roster;
  final int seat;
  final ScrollController controller;
  final bool interactive;
  @override Widget build(BuildContext context) {
    if(messages.isEmpty)return const SizedBox.shrink();
    final colors=Theme.of(context).colorScheme;
    return IgnorePointer(ignoring:!interactive,child:ConstrainedBox(constraints:BoxConstraints(maxHeight:min(230,MediaQuery.sizeOf(context).height*.28)),child:Material(type:MaterialType.transparency,child:ListView.builder(
      controller:controller,shrinkWrap:true,padding:const EdgeInsets.all(14),itemCount:messages.length,itemBuilder:(context,i){
        final m=messages[i],mine=m['seat']==seat;
        return Padding(padding:const EdgeInsets.only(bottom:10),child:Align(alignment:mine?Alignment.centerRight:Alignment.centerLeft,child:ConstrainedBox(constraints:BoxConstraints(maxWidth:MediaQuery.sizeOf(context).width*.78),child:Column(mainAxisSize:MainAxisSize.min,crossAxisAlignment:mine?CrossAxisAlignment.end:CrossAxisAlignment.start,children:[
          Text(roster.where((p)=>p['seat']==m['seat']).map((p)=>p['name']?.toString()??'لاعب').firstOrNull??'لاعب',style:TextStyle(fontSize:11,color:colors.primary,shadows:const [Shadow(color:Color(0x80000000),blurRadius:3)])),
          if(m['pending']==true)Text(m['failed']==true?'تعذر تأكيد الإرسال':'جارٍ الإرسال',style:const TextStyle(fontSize:10)),const SizedBox(height:4),
          if(m['stickerId']!=null)StickerArtwork(asset:m['stickerAsset']?.toString()??'',size:100)else ChatCosmetic(id:m['chatBubble']?.toString()??'',child:Text(m['text']?.toString()??'',style:const TextStyle(fontSize:15,height:1.4))),
        ]))));
      },
    ))));
  }
}
