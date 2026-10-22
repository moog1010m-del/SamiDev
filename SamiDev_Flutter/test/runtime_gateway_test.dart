import 'dart:convert';
import 'dart:io';
import 'package:crypto/crypto.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:samidev/runtime/api.dart';
import 'package:samidev/runtime/assets.dart';
import 'package:samidev/runtime/game_runtime.dart';
import 'package:samidev/runtime/policy.dart';
import 'session_test.dart' show MemoryVault;
class TestBundle extends CachingAssetBundle {
 TestBundle(this.values);
 final Map<String,List<int>> values;
 @override Future<ByteData> load(String key)async=>ByteData.sublistView(Uint8List.fromList(values[key]!));
}
void main(){
 test('loopback secret, origin guard, bundled asset range and integrity',()async{
  final web=utf8.encode('<html><body>SamiDev</body></html>');
  final hashes={for(final id in ['carrom','crazy8','pool','tablesoccer'])id:'testhash-$id'};
  final manifest={'engines':hashes,'files':{'platform/index.html':{'size':web.length,'sha256':sha256.convert(web).toString()}}};
  final assets=RuntimeAssets(bundle:TestBundle({'assets/runtime-manifest.json':utf8.encode(jsonEncode(manifest)),'assets/runtime/platform/index.html':web}));
  final backend=await HttpServer.bind(InternetAddress.loopbackIPv4,0);
  backend.listen((request)async{request.response.write(jsonEncode({'games':[for(final e in hashes.entries){'id':e.key,'mainJsSha256':e.value}]}));await request.response.close();});
  final runtime=GameRuntime(PlatformApi(RuntimePolicy('http://127.0.0.1:${backend.port}',allowLocalDevelopment:true),MemoryVault()),assets:assets);
  final client=HttpClient();
  try{
   await runtime.start();
   final unauth=await(await client.getUrl(runtime.origin.replace(path:'/platform/'))).close();expect(unauth.statusCode,403);await unauth.drain<void>();
   final bootstrap=await client.getUrl(runtime.launch);bootstrap.followRedirects=false;
   final response=await bootstrap.close();expect(response.statusCode,303);
   final cookie=response.cookies.single;expect(cookie.httpOnly,isTrue);await response.drain<void>();
   final range=await client.getUrl(runtime.origin.replace(path:'/platform/'));range.cookies.add(cookie);range.headers.set('Range','bytes=0-5');
   final ranged=await range.close();expect(ranged.statusCode,206);expect(await ranged.transform(utf8.decoder).join(),'<html ');
   final hostile=await client.getUrl(runtime.origin.replace(path:'/platform/'));hostile.cookies.add(cookie);hostile.headers.set('Origin','https://attacker.invalid');final denied=await hostile.close();expect(denied.statusCode,403);await denied.drain<void>();
   final repeat=await client.getUrl(runtime.launch);repeat.followRedirects=false;expect((await repeat.close()).statusCode,403);
   expect(runtime.allowsNavigation(Uri.parse('https://attacker.invalid')),isFalse);
  }finally{client.close(force:true);await runtime.close();await backend.close(force:true);}
 });
 test('all games share one verified host asset',()async{
  final hashes={for(final id in ['carrom','crazy8','pool','tablesoccer'])id:'testhash-$id'};
  final host=utf8.encode('<!doctype html><html><body><script src="/game-bootstrap.js"></script></body></html>');
  final web=utf8.encode('<html><body>Platform</body></html>');
  final assets=RuntimeAssets(bundle:TestBundle({'assets/runtime-manifest.json':utf8.encode(jsonEncode({'engines':hashes,'files':{'game-host.html':{'size':host.length,'sha256':sha256.convert(host).toString()},'platform/index.html':{'size':web.length,'sha256':sha256.convert(web).toString()}}})),'assets/runtime/game-host.html':host,'assets/runtime/platform/index.html':web}));
  final backend=await HttpServer.bind(InternetAddress.loopbackIPv4,0);
  backend.listen((request)async{request.response.write(jsonEncode({'games':[for(final e in hashes.entries){'id':e.key,'mainJsSha256':e.value}]}));await request.response.close();});
  final runtime=GameRuntime(PlatformApi(RuntimePolicy('http://127.0.0.1:${backend.port}',allowLocalDevelopment:true),MemoryVault()),assets:assets);
  final client=HttpClient();
  try{
   await runtime.start();final boot=await client.getUrl(runtime.launch);boot.followRedirects=false;final response=await boot.close();final cookie=response.cookies.single;await response.drain<void>();
   for(final path in ['/index.html','/games/carrom/index.html','/games/pool/index.html','/games/crazy8/index.html','/games/tablesoccer/index.html']){
    final request=await client.getUrl(runtime.origin.replace(path:path));request.cookies.add(cookie);final page=await request.close();expect(page.statusCode,200);final text=await page.transform(utf8.decoder).join();expect(text,contains('/game-bootstrap.js'));expect(text,isNot(contains('__dictEn')));
   }
  }finally{client.close(force:true);await runtime.close();await backend.close(force:true);}
 });
 test('table connection reports disconnect and reconnect without destroying bundled host',()async{
  final hashes={for(final id in ['carrom','crazy8','pool','tablesoccer'])id:'testhash-$id'};
  final web=utf8.encode('<html>Platform</html>');
  final assets=RuntimeAssets(bundle:TestBundle({'assets/runtime-manifest.json':utf8.encode(jsonEncode({'engines':hashes,'files':{'platform/index.html':{'size':web.length,'sha256':sha256.convert(web).toString()}}})),'assets/runtime/platform/index.html':web}));
  final backend=await HttpServer.bind(InternetAddress.loopbackIPv4,0);
  WebSocket? serverSocket;
  backend.listen((request)async{
   if(request.uri.path=='/ws'){serverSocket=await WebSocketTransformer.upgrade(request);serverSocket!.listen((_){ });return;}
   request.response.headers.contentType=ContentType.json;
   request.response.write(jsonEncode(request.uri.path=='/api/game-ticket'?{'ticket':'test-ticket'}:{'games':[for(final e in hashes.entries){'id':e.key,'mainJsSha256':e.value}]}));await request.response.close();
  });
  final runtime=GameRuntime(PlatformApi(RuntimePolicy('http://127.0.0.1:${backend.port}',allowLocalDevelopment:true),MemoryVault()),assets:assets);
  final client=HttpClient();final changes=<bool>[];
  final sub=runtime.events.stream.listen((event){if(event['type']=='game_connection')changes.add(event['connected']==true);});
  WebSocket? local;
  try{
   await runtime.start();
   final bootstrap=await client.getUrl(runtime.launch);bootstrap.followRedirects=false;final response=await bootstrap.close();final cookie=response.cookies.single;await response.drain<void>();
   Future<WebSocket> connect()=>WebSocket.connect(runtime.origin.replace(scheme:'ws',path:'/ws').toString(),headers:{'Cookie':'${cookie.name}=${cookie.value}','Origin':runtime.origin.origin});
   local=await connect();await Future<void>.delayed(const Duration(milliseconds:30));expect(changes.last,isTrue);
   await serverSocket!.close(1001);await local.drain<void>();await Future<void>.delayed(const Duration(milliseconds:30));expect(changes.last,isFalse);
   local=await connect();await Future<void>.delayed(const Duration(milliseconds:30));expect(changes,[true,false,true]);
   final asset=await client.getUrl(runtime.origin.replace(path:'/platform/'));asset.cookies.add(cookie);expect((await asset.close()).statusCode,200);
  }finally{await local?.close();await sub.cancel();await runtime.close();client.close(force:true);await backend.close(force:true);}
 });
 test('modified asset bytes fail closed',()async{
  for(final key in ['main.js','game-host.html']){
   final assets=RuntimeAssets(bundle:TestBundle({'assets/runtime-manifest.json':utf8.encode(jsonEncode({'files':{key:{'size':3,'sha256':'wrong'}}})),'assets/runtime/$key':[1,2,3]}));
   await assets.load();await expectLater(assets.read(key),throwsStateError);
  }
 });
}
