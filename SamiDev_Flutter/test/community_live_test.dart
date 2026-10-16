import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:samidev/runtime/api.dart';
import 'package:samidev/runtime/policy.dart';
import 'package:samidev/ui/community_hub.dart';
import 'session_test.dart' show MemoryVault;

class LiveApi extends PlatformApi {
 LiveApi():super(RuntimePolicy('https://live.example.test'),MemoryVault());
 final stream=StreamController<Map<String,dynamic>>.broadcast();
 final reply=Completer<ApiResponse>();
 Map<String,dynamic>? sent;
 @override Stream<Map<String,dynamic>> events(String path)=>stream.stream;
 @override Future<ApiResponse> request(String method,String path,{String? query,List<int>? body})async{
  if(path.endsWith('/chat')){sent=Map<String,dynamic>.from(jsonDecode(utf8.decode(body!)));return reply.future;}
  return ApiResponse(200,'application/json',Uint8List.fromList(utf8.encode(jsonEncode({'ok':true,'community':{'id':'majlis','name':'المجلس','mark':'م'},'capabilities':{},'rooms':[],'members':[],'messages':[]}))));
 }
}
void main(){
 testWidgets('native chat renders pending immediately and merges stream with acknowledgement once',(tester)async{
  final api=LiveApi();addTearDown(api.close);addTearDown(api.stream.close);
  await tester.pumpWidget(MaterialApp(home:Scaffold(body:CommunityHub(api:api,active:true,initialCommunity:'majlis',user:{'id':'self-player','username':'Player','nameBadgeAsset':'/platform/assets/profile/raster/palm-swords.webp'},onGame:(game,query)async{},onProfile:(_){},onTheme:(){},onInvite:(){},onNavigationChanged:(){},onUnauthorized:(){}))));
  await tester.pumpAndSettle();await tester.tap(find.text('الدردشة'));await tester.pumpAndSettle();
  await tester.enterText(find.byType(TextField),'فوري');await tester.tap(find.byTooltip('إرسال'));await tester.pump();
  expect(find.text('فوري'),findsOneWidget);expect(find.text('جارٍ الإرسال'),findsOneWidget);
  final message={'id':'stored-message','clientMessageId':api.sent!['clientMessageId'],'userId':'self-player','displayName':'Player','username':'Player','text':'فوري','createdAt':DateTime.now().millisecondsSinceEpoch};
  api.stream.add({'type':'message','message':message});await tester.pumpAndSettle();
  expect(find.text('فوري'),findsOneWidget);expect(find.text('جارٍ الإرسال'),findsNothing);
  api.reply.complete(ApiResponse(200,'application/json',Uint8List.fromList(utf8.encode(jsonEncode({'ok':true,'message':message})))));
  await tester.pumpAndSettle();expect(find.text('فوري'),findsOneWidget);
  api.stream.add({'type':'message','message':{'id':'other-message','userId':'other-player','username':'Other','text':'رسالة الآخر','createdAt':DateTime.now().millisecondsSinceEpoch}});
  await tester.pumpAndSettle();
  expect(tester.getCenter(find.text('فوري')).dx,greaterThan(tester.view.physicalSize.width/tester.view.devicePixelRatio/2));
  expect(tester.getCenter(find.text('رسالة الآخر')).dx,lessThan(tester.view.physicalSize.width/tester.view.devicePixelRatio/2));
  expect(find.byTooltip('إعدادات المنصة'),findsNothing);
  expect(tester.takeException(),isNull);
  await tester.pumpWidget(const SizedBox());await tester.pumpAndSettle();
 });
}
