import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:crypto/crypto.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:samidev/runtime/api.dart';
import 'package:samidev/runtime/assets.dart';
import 'package:samidev/runtime/game_runtime.dart';
import 'package:samidev/runtime/policy.dart';
import 'runtime_gateway_test.dart' show TestBundle;
import 'session_test.dart' show MemoryVault;

void main(){
 test('native gateway observes pending chat before authoritative confirmation',()async{
  final hashes={for(final id in ['carrom','crazy8','pool','tablesoccer'])id:'testhash-$id'};
  final web=utf8.encode('<html>SamiDev</html>');
  final assets=RuntimeAssets(bundle:TestBundle({'assets/runtime-manifest.json':utf8.encode(jsonEncode({'engines':hashes,'files':{'platform/index.html':{'size':web.length,'sha256':sha256.convert(web).toString()}}})),'assets/runtime/platform/index.html':web}));
  final backend=await HttpServer.bind(InternetAddress.loopbackIPv4,0),accepted=Completer<void>();
  backend.listen((request)async{
   if(request.uri.path=='/ws'){
    final socket=await WebSocketTransformer.upgrade(request);
    socket.listen((raw)async{final packet=jsonDecode(raw as String) as Map;expect(packet['clientMessageId'],'chat_test_nonce_123');await accepted.future;socket.add(jsonEncode({'type':'chat_message','id':'confirmed','seat':0,'text':packet['text'],'clientMessageId':packet['clientMessageId'],'chatBubble':'chat_ember'}));socket.add(jsonEncode({'type':'move','authority':{'turn':[1],'sequence':[2,3],'gameOver':false},'reveal':{'ignored':'physics'}}));});return;
   }
   request.response.headers.contentType=ContentType.json;
   if(request.uri.path=='/api/game-ticket'){request.response.write('{"ticket":"local-test-only"}');}
   else{request.response.write(jsonEncode({'games':[for(final e in hashes.entries){'id':e.key,'mainJsSha256':e.value}]}));}
   await request.response.close();
  });
  final runtime=GameRuntime(PlatformApi(RuntimePolicy('http://127.0.0.1:${backend.port}',allowLocalDevelopment:true),MemoryVault()),assets:assets);
  final client=HttpClient();WebSocket? socket;final events=<Map<String,dynamic>>[];
  final subscription=runtime.events.stream.listen(events.add);
  try{
   await runtime.start();final bootstrap=await client.getUrl(runtime.launch);bootstrap.followRedirects=false;final response=await bootstrap.close();final cookie=response.cookies.single;await response.drain<void>();
   socket=await WebSocket.connect(runtime.origin.replace(scheme:'ws',path:'/ws').toString(),headers:{'Origin':runtime.origin.origin,'Cookie':'${cookie.name}=${cookie.value}'});
   final confirmed=socket.first;
   socket.add(jsonEncode({'type':'chat_send','text':'سلام','clientMessageId':'chat_test_nonce_123'}));
   for(var i=0;i<100&&events.isEmpty;i++){await Future<void>.delayed(const Duration(milliseconds:5));}
   expect(events.single['type'],'chat_pending');expect(events.single['clientMessageId'],'chat_test_nonce_123');
   accepted.complete();final echo=jsonDecode(await confirmed as String) as Map;expect(echo['chatBubble'],'chat_ember');
   for(var i=0;i<100&&events.length<3;i++){await Future<void>.delayed(const Duration(milliseconds:5));}
   expect(events[1]['type'],'chat_message');expect(events[1]['clientMessageId'],events.first['clientMessageId']);expect(events.last['type'],'game_turn');expect(events.last['turn'],[1]);
  }finally{if(!accepted.isCompleted)accepted.complete();await socket?.close();await subscription.cancel();client.close(force:true);await runtime.close();await backend.close(force:true);}
 });
}
