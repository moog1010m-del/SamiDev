import 'package:flutter/material.dart';
import 'games_hub.dart';

/// Bundled navigation is usable before the server responds. No cached account
/// is treated as authenticated, and offline taps never create a room.
class OfflineShell extends StatelessWidget {
  const OfflineShell({super.key, required this.connecting, required this.onRetry, required this.onUnavailable, this.error});
  final bool connecting;
  final VoidCallback onRetry, onUnavailable;
  final String? error;
  @override Widget build(BuildContext context) => Column(children:[
    MaterialBanner(
      leading:Icon(connecting?Icons.sync:Icons.wifi_off_rounded),
      content:Text(connecting?'جارٍ الاتصال… يمكنك تصفح الألعاب':'الاتصال بالخدمة غير متاح. يمكنك تصفح الألعاب، وتحتاج اتصالًا لبدء مباراة.'),
      actions:[if(connecting)const Padding(padding:EdgeInsets.all(12),child:SizedBox(width:18,height:18,child:CircularProgressIndicator(strokeWidth:2)))else TextButton(onPressed:onRetry,child:const Text('إعادة الاتصال'))],
    ),
    if(error!=null)ExpansionTile(title:const Text('تفاصيل الاتصال',style:TextStyle(fontSize:12)),children:[Padding(padding:const EdgeInsets.all(12),child:Text(error!,style:const TextStyle(fontSize:12)))]),
    Expanded(child:GamesHub(onGame:(_,query)async{onUnavailable();})),
  ]);
}
