import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:samidev/runtime/api.dart';
import 'package:samidev/runtime/native_auth.dart';
import 'package:samidev/runtime/policy.dart';
import 'session_test.dart' show MemoryVault;
void main(){
 test('native SSE uses platform cookie and parses fragmented UTF-8 data',()async{
  final server=await HttpServer.bind(InternetAddress.loopbackIPv4,0);
  final api=PlatformApi(RuntimePolicy('http://127.0.0.1:${server.port}',allowLocalDevelopment:true),MemoryVault());
  server.listen((request)async{
   if(request.uri.path=='/api/auth/guest'){
    request.response.headers.contentType=ContentType.json;request.response.cookies.add(Cookie('samidev_session','G'*43)..httpOnly=true);
    request.response.write('{"ok":true,"user":{"id":"guest-player","isGuest":true}}');await request.response.close();return;
   }
   expect(request.headers.value('Cookie'),'samidev_session=${'G'*43}');expect(request.headers.value('Accept'),'text/event-stream');
   request.response.headers.contentType=ContentType('text','event-stream',charset:'utf-8');
   request.response.write('data: {"type":"snapshot","messages":[]}\n\n');await request.response.flush();
   request.response.write('data: {"type":"message","message":{"text":"');await request.response.flush();
   request.response.write('مرحبًا"}}\n\n');await request.response.close();
  });
  try{await NativeAuth(api).guest();final rows=await api.events('/api/communities/majlis/events').take(2).toList();expect(rows[0]['type'],'snapshot');expect((rows[1]['message'] as Map)['text'],'مرحبًا');}
  finally{api.close();await server.close(force:true);}
 });
}
