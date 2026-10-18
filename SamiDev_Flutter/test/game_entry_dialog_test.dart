import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:samidev/runtime/api.dart';
import 'package:samidev/runtime/policy.dart';
import 'package:samidev/ui/community_hub.dart';
import 'session_test.dart' show MemoryVault;
class EntryApi extends PlatformApi {
 EntryApi():super(RuntimePolicy('https://entry.example.test'),MemoryVault());
 @override Stream<Map<String,dynamic>> events(String path)=>const Stream.empty();
 @override Future<ApiResponse> request(String method,String path,{String? query,List<int>? body})async=>ApiResponse(200,'application/json',Uint8List.fromList(utf8.encode(jsonEncode({'ok':true,'community':{'id':'majlis','name':'Saudi Arabia','mark':'🇸🇦','countryCode':'sa'},'capabilities':{},'rooms':[{'roomId':'ENTRY1','settings':{'gameId':'pool','live':1},'capacity':2,'occupied':1,'roster':[]}],'members':[],'messages':[]}))));
}
void main(){testWidgets('cancel makes no request; same dialog stays busy until game readiness',(tester)async{
 final api=EntryApi();addTearDown(api.close);final ready=Completer<void>();var calls=0;
 await tester.pumpWidget(MaterialApp(home:Scaffold(body:CommunityHub(api:api,active:true,initialCommunity:'majlis',onGame:(game,query){calls++;expect(query['action'],'join');return ready.future;},onProfile:(_){},onTheme:(){},onInvite:(){},onNavigationChanged:(){},onUnauthorized:(){}))));
 await tester.pumpAndSettle();await tester.tap(find.text('انضم'));await tester.pumpAndSettle();
 await tester.tap(find.text('إلغاء'));await tester.pumpAndSettle();expect(calls,0);
 await tester.tap(find.text('انضم'));await tester.pumpAndSettle();final dialog=tester.element(find.byType(AlertDialog));
 await tester.tap(find.descendant(of:find.byType(AlertDialog),matching:find.text('انضم')));await tester.pump();expect(calls,1);expect(find.text('نجهّز طاولتك…'),findsOneWidget);expect(tester.element(find.byType(AlertDialog)),same(dialog));
 ready.complete();await tester.pumpAndSettle();expect(find.byType(AlertDialog),findsNothing);expect(tester.takeException(),isNull);
 await tester.pumpWidget(const SizedBox());await tester.pumpAndSettle();
});}
