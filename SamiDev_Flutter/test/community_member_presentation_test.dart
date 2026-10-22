import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:samidev/runtime/api.dart';
import 'package:samidev/ui/community_hub.dart';
import 'package:samidev/ui/reputation_flame.dart';
import 'community_live_test.dart' show LiveApi;
class MemberApi extends LiveApi{
 @override Future<ApiResponse> request(String method,String path,{String? query,List<int>? body})async=>ApiResponse(200,'application/json',Uint8List.fromList(utf8.encode(jsonEncode({'ok':true,'community':{'id':'majlis','name':'Saudi Arabia','countryCode':'sa'},'capabilities':{},'rooms':[],'messages':[],'members':[
  {'id':'a','username':'Dev','displayName':'Dev','bio':'BIO MUST STAY HIDDEN','hasAvatar':false,'starsCount':5,'reputation':50004,'wins':102},
  {'id':'b','username':'Guest_123','displayName':'Guest_123','hasAvatar':false,'starsCount':0,'reputation':3,'wins':2},
 ]}))));
}
void main(){testWidgets('members show one username, no bio and earned reputation',(tester)async{
 final api=MemberApi();addTearDown(api.close);addTearDown(api.stream.close);
 await tester.pumpWidget(MaterialApp(home:MediaQuery(data:const MediaQueryData(disableAnimations:true),child:Scaffold(body:CommunityHub(api:api,active:true,initialCommunity:'majlis',onGame:(_,_)async{},onProfile:(_){},onTheme:(){},onInvite:(){},onNavigationChanged:(){},onUnauthorized:(){})))));
 await tester.pumpAndSettle();await tester.tap(find.text('متصل (2)'));await tester.pumpAndSettle();
 expect(find.text('Dev'),findsOneWidget);expect(find.text('Guest_123'),findsOneWidget);expect(find.text('BIO MUST STAY HIDDEN'),findsNothing);
 final flames=tester.widgetList<ReputationFlame>(find.byType(ReputationFlame)).map((w)=>w.score).toList();expect(flames,[50004,3]);
 expect(tester.takeException(),isNull);
 await tester.pumpWidget(const SizedBox());await tester.pumpAndSettle();
});}
