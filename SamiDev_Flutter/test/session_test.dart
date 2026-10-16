import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:samidev/runtime/api.dart';
import 'package:samidev/runtime/policy.dart';
import 'package:samidev/runtime/failures.dart';
class MemoryVault implements SessionVault {
 final data=<String,String>{};
 @override Future<String?> read(String key)async=>data[key];
 @override Future<void> write(String key,String? value)async{if(value==null){data.remove(key);}else{data[key]=value;}}
}
void main(){
 test('device self-revoke, global logout and accepted deletion remove secure session',()async{
  final server=await HttpServer.bind(InternetAddress.loopbackIPv4,0);
  final vault=MemoryVault();
  final api=PlatformApi(RuntimePolicy('http://127.0.0.1:${server.port}',allowLocalDevelopment:true),vault);
  server.listen((request)async{
   expect(request.headers.value('User-Agent'),contains('SamiDev/'));
   request.response.headers.contentType=ContentType.json;
   if(request.uri.path=='/api/auth/login'){
    request.response.cookies.add(Cookie('samidev_session','S'*43)..httpOnly=true);
    request.response.write('{"ok":true}');
   }else{
    expect(request.headers.value('Cookie'),'samidev_session=${'S'*43}');
    request.response.statusCode=request.uri.path=='/api/account/delete'?202:200;
    request.response.write('{"ok":true,"signedOut":true}');
   }
   await request.response.close();
  });
  try{
   for(final entry in [('DELETE','/api/account/devices/current'),('POST','/api/account/logout-all'),('POST','/api/account/delete')]){
    await api.request('POST','/api/auth/login',body:utf8.encode('{}'));expect(api.signedIn,isTrue);
    await api.request(entry.$1,entry.$2,body:entry.$1=='POST'?utf8.encode('{}'):null);
    expect(api.signedIn,isFalse);expect(vault.data,isEmpty);
   }
  }finally{api.close();await server.close(force:true);}
 });
 test('cookie stays native, accompanies API, clears on 401, redirects blocked',()async{
  final server=await HttpServer.bind(InternetAddress.loopbackIPv4,0);
  final policy=RuntimePolicy('http://127.0.0.1:${server.port}',allowLocalDevelopment:true);
  final vault=MemoryVault();
  final api=PlatformApi(policy,vault);
  var expired=false;
  server.listen((req)async{
   expect(req.headers.value('Origin'),policy.backend.origin);
   if(req.uri.path=='/api/auth/login'){
    req.response.cookies.add(Cookie('samidev_session','A'*43)..httpOnly=true);
    req.response.write('{"ok":true}');
   }else if(req.uri.path=='/api/me'){
    expect(req.headers.value('Cookie'),'samidev_session=${'A'*43}');
    req.response.statusCode=expired?401:200;req.response.write('{"ok":true}');
   }else{req.response.statusCode=302;req.response.headers.set('Location','https://attacker.invalid');}
   await req.response.close();
  });
  try{
   await api.request('POST','/api/auth/login',body:utf8.encode('{}'));
   expect(api.signedIn,isTrue);await api.request('GET','/api/me');expired=true;
   await api.request('GET','/api/me');expect(api.signedIn,isFalse);
   await expectLater(api.request('GET','/api/build'),throwsA(isA<RuntimeFailure>().having((e)=>e.code,'code','UPSTREAM_REDIRECT')));
   expect(vault.data,isEmpty);
  }finally{api.close();await server.close(force:true);}
 });
}
