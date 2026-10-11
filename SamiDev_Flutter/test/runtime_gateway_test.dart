import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
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
 test('modified asset bytes fail closed',()async{
  final assets=RuntimeAssets(bundle:TestBundle({'assets/runtime-manifest.json':utf8.encode(jsonEncode({'files':{'main.js':{'size':3,'sha256':'wrong'}}})),'assets/runtime/main.js':[1,2,3]}));
  await assets.load();await expectLater(assets.read('main.js'),throwsStateError);
 });
}
