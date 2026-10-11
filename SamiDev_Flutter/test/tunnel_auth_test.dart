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

// Test transport only: model TLS termination while keeping the real API and
// loopback gateway code. Production still uses HttpClient certificate validation.
class TunnelTransport implements HttpClient {
  TunnelTransport(this.port);
  final int port;
  final delegate=HttpClient();
  @override set connectionTimeout(Duration? value){delegate.connectionTimeout=value;}
  @override Future<HttpClientRequest> openUrl(String method,Uri url)=>delegate.openUrl(method,url.replace(scheme:'http',host:'127.0.0.1',port:port));
  @override void close({bool force=false})=>delegate.close(force:force);
  @override dynamic noSuchMethod(Invocation invocation)=>super.noSuchMethod(invocation);
}
void main(){
  test('gateway explains insecure tunnel cookie, accepts secure login and keeps session native',()async{
    final web=utf8.encode('<html><body>Login</body></html>');
    final hashes={for(final id in ['carrom','crazy8','pool','tablesoccer'])id:'test-$id'};
    final manifest={'engines':hashes,'files':{'platform/index.html':{'size':web.length,'sha256':sha256.convert(web).toString()}}};
    final assets=RuntimeAssets(bundle:TestBundle({'assets/runtime-manifest.json':utf8.encode(jsonEncode(manifest)),'assets/runtime/platform/index.html':web}));
    final backend=await HttpServer.bind(InternetAddress.loopbackIPv4,0);var secure=false;
    backend.listen((request)async{
      await request.drain<void>();request.response.headers.contentType=ContentType.json;
      if(request.uri.path=='/api/games'){
        request.response.write(jsonEncode({'games':[for(final e in hashes.entries){'id':e.key,'mainJsSha256':e.value}]}));
      }else if(request.uri.path.startsWith('/api/auth/')){
        request.response.cookies.add(Cookie('samidev_session','T'*43)..httpOnly=true..secure=secure);
        request.response.write('{"ok":true,"user":{"id":"test-user"}}');
      }else{
        expect(request.headers.value('Cookie'),'samidev_session=${'T'*43}');
        request.response.write('{"ok":true}');
      }
      await request.response.close();
    });
    final vault=MemoryVault();
    final api=PlatformApi(RuntimePolicy('https://mobile.example.test'),vault,httpClient:TunnelTransport(backend.port));
    final runtime=GameRuntime(api,assets:assets);final client=HttpClient();
    try{
      await runtime.start();final launch=await client.getUrl(runtime.launch);launch.followRedirects=false;
      final bootstrap=await launch.close();final cookie=bootstrap.cookies.single;await bootstrap.drain<void>();
      Future<HttpClientResponse> post(String path)async{
        final request=await client.postUrl(runtime.origin.replace(path:path));request.cookies.add(cookie);
        request.headers.set('Origin',runtime.origin.origin);request.headers.contentType=ContentType.json;
        request.write('{"username":"test","password":"password-not-for-output"}');return request.close();
      }
      final rejected=await post('/api/auth/register');expect(rejected.statusCode,502);
      final error=jsonDecode(await rejected.transform(utf8.decoder).join()) as Map;
      expect(error['error'],'SESSION_COOKIE_INSECURE');expect(error['message'],contains('الخادم'));expect(api.signedIn,isFalse);expect(vault.data,isEmpty);
      secure=true;
      final accepted=await post('/api/auth/login');expect(accepted.statusCode,200);expect(accepted.cookies,isEmpty);
      final body=await accepted.transform(utf8.decoder).join();expect(body, isNot(contains('T'*43)));expect(body,isNot(contains('password-not-for-output')));
      expect(api.signedIn,isTrue);expect(vault.data.values.single,'T'*43);expect((await api.request('GET','/api/me')).status,200);
    }finally{client.close(force:true);await runtime.close();await backend.close(force:true);}
  });
}
