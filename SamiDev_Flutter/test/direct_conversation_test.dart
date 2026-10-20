import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:samidev/runtime/api.dart';
import 'package:samidev/runtime/policy.dart';
import 'package:samidev/ui/direct_conversation.dart';
import 'friend_notifications_test.dart' show MemoryVault;
class ConversationApi extends PlatformApi {
  ConversationApi():super(RuntimePolicy('https://example.test'),MemoryVault());
  final updates=StreamController<Map<String,dynamic>>.broadcast();
  final messages=<Map<String,dynamic>>[];
  final nonces=<String>[];
  bool muted=false, fail=false;
  @override Stream<Map<String,dynamic>> events(String path)=>updates.stream;
  @override Future<ApiResponse> request(String method,String path,{String? query,List<int>? body})async{
    final data=body==null?<String,dynamic>{}:jsonDecode(utf8.decode(body)) as Map<String,dynamic>;
    if(method=='POST'&&path.endsWith('/messages')){nonces.add(data['clientMessageId'] as String);if(fail)return ApiResponse(503,'application/json',Uint8List.fromList(utf8.encode('{}')));messages.add({'id':'m1','senderId':'owner','text':data['text']});}
    if(path.endsWith('/mute'))muted=data['muted'] as bool;
    return ApiResponse(200,'application/json',Uint8List.fromList(utf8.encode(jsonEncode({'user':{'username':'my_friend'},'messages':messages,'muted':muted,'seq':messages.length}))));
  }
}
void main(){
  testWidgets('native conversation confirms sends, retries same nonce and mutes',(tester)async{
    final api=ConversationApi();
    await tester.pumpWidget(MaterialApp(home:DirectConversation(api:api,accountId:'owner',peerId:'peer_12345678')));
    await tester.pumpAndSettle();expect(find.text('my_friend'),findsOneWidget);
    await tester.enterText(find.byType(TextField),'hello friend');api.fail=true;
    await tester.tap(find.byTooltip('إرسال'));await tester.pumpAndSettle();
    expect(find.text('hello friend'),findsOneWidget);expect(api.messages,isEmpty);
    await tester.pump(const Duration(seconds:5));await tester.pumpAndSettle();
    api.fail=false;await tester.tap(find.byTooltip('إرسال'));await tester.pumpAndSettle();
    expect(api.nonces.length,2);expect(api.nonces.first,api.nonces.last);expect(api.messages.length,1);
    await tester.tap(find.byTooltip('كتم الصديق'));await tester.pumpAndSettle();expect(api.muted,isTrue);expect(find.byTooltip('إلغاء كتم الصديق'),findsOneWidget);
    await tester.pumpWidget(const SizedBox());await api.updates.close();api.close();
  });
}
