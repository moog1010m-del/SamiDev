import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';
import 'dart:typed_data';
import 'api.dart';
import 'assets.dart';
import 'policy.dart';
import 'failures.dart';

class GameRuntime {
  GameRuntime(this.api, {RuntimeAssets? assets}) : assets=assets??RuntimeAssets();
  final PlatformApi api;
  final RuntimeAssets assets;
  final events=StreamController<Map<String,dynamic>>.broadcast();
  final Set<WebSocket> _sockets={};
  HttpServer? _server;
  late final Uri origin;
  final String _secret=base64Url.encode(List<int>.generate(32,(_)=>Random.secure().nextInt(256))).replaceAll('=','');
  bool _bootstrapUsed=false, _closed=false, paused=false;
  int _connecting=0;
  String community='majlis';
  Map<String,dynamic> _catalog={};
  Uri get launch => origin.replace(path:'/_launch/$_secret');
  bool owns(Uri uri) => _server!=null && uri.scheme=='http' && uri.host=='127.0.0.1' && uri.port==origin.port && uri.userInfo.isEmpty;
  bool allowsNavigation(Uri uri) => owns(uri) && (RuntimePolicy.entries.contains(uri.path) || (!_bootstrapUsed&&uri.path==launch.path));
  Future<void> start() async {
    try{await assets.load();await assets.read('platform/index.html');}
    catch(error){throw RuntimeFailure.from(error,asset:true);}
    await api.restore();
    final reply=await api.request('GET','/api/games');
    if(reply.status!=200) throw const RuntimeFailure('UPSTREAM_UNAVAILABLE','الخادم غير متاح حاليًا. تحقق من تشغيله وعنوانه.');
    final games=reply.json['games'] as List;
    for(final game in games){_catalog[game['id'] as String]=game;}
    final hashes=assets.manifest['engines'] as Map;
    if(hashes.length!=4 || hashes.entries.any((e)=>_catalog[e.key]?['mainJsSha256']!=e.value)) {
      throw StateError('نسخة الألعاب في التطبيق تختلف عن الخادم. حدّث التطبيق والخادم معًا.');
    }
    if(_closed)return;
    _server=await HttpServer.bind(InternetAddress.loopbackIPv4,0);
    if(_closed){await _server!.close(force:true);return;}
    origin=Uri.parse('http://127.0.0.1:${_server!.port}');
    _server!.listen((request){unawaited(_handle(request));});
  }
  bool _authenticated(HttpRequest request) => request.cookies.any((c)=>c.name=='sd_runtime'&&c.value==_secret);
  bool _validSource(HttpRequest request) {
    final source=request.headers.value('Origin');
    return request.headers.value('Host')==origin.authority &&
      (source==null||source==origin.origin) && request.headers.value('Sec-Fetch-Site')!='cross-site';
  }
  void _headers(HttpResponse response, String path) {
    response.headers.set('X-Content-Type-Options','nosniff');
    response.headers.set('X-Frame-Options','DENY');
    response.headers.set('Cache-Control','no-store');
    response.headers.set('Referrer-Policy','no-referrer');
    response.headers.set('Permissions-Policy','camera=(), microphone=(), geolocation=(), payment=()');
    final scripts=path.startsWith('/platform')?"'self'":"'self' 'unsafe-inline'";
    response.headers.set('Content-Security-Policy',"default-src 'self'; script-src $scripts; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'");
  }
  Future<void> _handle(HttpRequest request) async {
    var upgraded=false;
    try {
      final path=request.uri.path;
      _headers(request.response,path);
      if(_closed||!_validSource(request)){request.response.statusCode=403;return;}
      if(path==launch.path && request.method=='GET' && !_bootstrapUsed){
        _bootstrapUsed=true;
        request.response.headers.add('Set-Cookie','sd_runtime=$_secret; Path=/; HttpOnly; SameSite=Strict');
        request.response.statusCode=303;request.response.headers.set('Location','/platform/');return;
      }
      if(!_authenticated(request)){request.response.statusCode=403;return;}
      if(path=='/ws'){
        if(request.headers.value('Origin')!=origin.origin || !WebSocketTransformer.isUpgradeRequest(request) || paused || _connecting+_sockets.length~/2>=2){request.response.statusCode=403;return;}
        upgraded=await _socket(request);return;
      }
      if(path.startsWith('/api/')){
        if(!RuntimePolicy.allowApi(request.method,path)){request.response.statusCode=403;return;}
        if(!{'GET','HEAD'}.contains(request.method) && request.headers.value('Origin')!=origin.origin){request.response.statusCode=403;return;}
        final body=BytesBuilder(copy:false);var length=0;
        await for(final bytes in request.timeout(const Duration(seconds:15))){length+=bytes.length;if(length>512*1024){request.response.statusCode=413;return;}body.add(bytes);}
        final reply=await api.request(request.method,path,query:request.uri.query,body:body.takeBytes());
        request.response.statusCode=reply.status;
        request.response.headers.set('Content-Type',reply.type);
        request.response.add(reply.bytes);
        if((path=='/api/auth/logout'&&reply.status==200 || reply.status==401)&&!api.signedIn){
          await _disconnect(4003);_emit({'type':'auth_expired'});
        }
        return;
      }
      if(!{'GET','HEAD'}.contains(request.method)){request.response.statusCode=405;return;}
      if(path=='/client-config.js'){
        request.response.headers.set('Content-Type','application/javascript; charset=utf-8');
        request.response.write('window.__SAMIDEV_CLIENT_CONFIG=${jsonEncode({'platformEnabled':true,'requireGameAuth':true,'production':true,'chatMaxChars':160,'games':_catalog,'mainJsSha256':assets.manifest['engines']['carrom']})};');return;
      }
      final key=path=='/platform/'?'platform/index.html':path.substring(1);
      if(path.contains('..')||path.contains('\\')||!assets.contains(key)){request.response.statusCode=404;return;}
      var bytes=await assets.read(key);
      if(path.startsWith('/platform')&&key.endsWith('.html')){bytes=Uint8List.fromList(utf8.encode(utf8.decode(bytes).replaceFirst('<html','<html data-sd-native')));}

      if(RuntimePolicy.isGame(path)){
        // Native portrait chat uses the same authoritative WS stream.
        bytes=Uint8List.fromList(utf8.encode(utf8.decode(bytes).replaceAll('<script src="/chat-ui.js"></script>','')));
      }
      request.response.headers.set('Content-Type',_mime(key));
      request.response.headers.set('Accept-Ranges','bytes');
      final range=request.headers.value('Range');var start=0,end=bytes.length-1;
      if(range!=null){
        final match=RegExp(r'^bytes=(\d*)-(\d*)$').firstMatch(range);
        if(match==null||match[1]!.isEmpty&&match[2]!.isEmpty){request.response.statusCode=416;return;}
        if(match[1]!.isEmpty){final count=int.tryParse(match[2]!)??0;start=max(0,bytes.length-count);}
        else {start=int.tryParse(match[1]!)??bytes.length;if(match[2]!.isNotEmpty)end=min(end,int.tryParse(match[2]!)??-1);}
        if(start<0||start>end||start>=bytes.length){request.response.statusCode=416;request.response.headers.set('Content-Range','bytes */${bytes.length}');return;}
        request.response.statusCode=206;request.response.headers.set('Content-Range','bytes $start-$end/${bytes.length}');
      }
      request.response.contentLength=end-start+1;
      if(request.method!='HEAD')request.response.add(bytes.sublist(start,end+1));
    } catch(error){
      final failure=RuntimeFailure.from(error,asset:!request.uri.path.startsWith('/api/')&&request.uri.path!='/ws');
      try{request.response.statusCode=failure.status;request.response.headers.contentType=ContentType.json;request.response.write(jsonEncode(failure.json));}catch(_){}
    } finally {if(!upgraded){try{await request.response.close();}catch(_){}}}
  }
  Future<bool> _socket(HttpRequest request) async {
    _connecting++;WebSocket? remote;WebSocket? local;
    try {
      final ticket=await api.request('POST','/api/game-ticket',body:utf8.encode(jsonEncode({'communityId':community})));
      if(ticket.status!=200){request.response.statusCode=ticket.status;return false;}
      final uri=api.policy.upstream('/ws').replace(scheme:api.policy.backend.scheme=='https'?'wss':'ws',queryParameters:{'ticket':ticket.json['ticket'] as String});
      remote=await WebSocket.connect(uri.toString(),headers:api.headers,compression:CompressionOptions.compressionOff,customClient:api.client).timeout(const Duration(seconds:15));
      if(_closed||paused){await remote.close();request.response.statusCode=503;return false;}
      local=await WebSocketTransformer.upgrade(request,compression:CompressionOptions.compressionOff);
      final upstream=remote,downstream=local;
      _sockets.addAll([upstream,downstream]);
      void closePair([int? code]){final safeCode={1000,1001,1008,1009,1011,4001,4003}.contains(code)?code!:1001;_sockets.remove(upstream);_sockets.remove(downstream);unawaited(upstream.close(safeCode).catchError((_){ }));unawaited(downstream.close(safeCode).catchError((_){ }));}
      downstream.listen((message){
        if(message is! String || utf8.encode(message).length>65536){closePair(1009);return;}
        upstream.add(message);
      },onDone:()=>closePair(downstream.closeCode),onError:(_)=>closePair(1011));
      upstream.listen((message){
        if(message is! String || message.length>4*1024*1024){closePair(1009);return;}
        downstream.add(message);
        // Physics updates bypass JSON parsing in Dart; UI only observes selected event types.
        if(RegExp(r'"type"\s*:\s*"(chat_message|chat_history|created|joined|watching|room_state|begin_match|left_room|invite_created|error)"').hasMatch(message.substring(0,min(120,message.length)))){
          try{_emit(jsonDecode(message) as Map<String,dynamic>);}catch(_){}
        }
      },onDone:(){if(upstream.closeCode==4003)_emit({'type':'auth_expired'});closePair(upstream.closeCode);},onError:(_)=>closePair(1011));
      return true;
    } catch(_){await remote?.close();await local?.close();rethrow;}
    finally{_connecting--;}
  }
  void _emit(Map<String,dynamic> data){if(!events.isClosed)events.add(data);}
  Future<void> _disconnect(int code) async {
    final sockets=List<WebSocket>.of(_sockets);_sockets.clear();
    await Future.wait(sockets.map((s)=>s.close(code)));
  }
  Future<void> suspend() async {paused=true;await _disconnect(1001);}
  void resume(){paused=false;}
  Future<void> close() async {_closed=true;await _disconnect(1001);await _server?.close(force:true);await events.close();api.close();}
  static String _mime(String path) {
    const types={'html':'text/html; charset=utf-8','js':'application/javascript; charset=utf-8','css':'text/css; charset=utf-8','json':'application/json','atlas':'text/plain','glsl':'text/plain','txt':'text/plain','svg':'image/svg+xml','webp':'image/webp','png':'image/png','jpg':'image/jpeg','jpeg':'image/jpeg','m4a':'audio/mp4','mp3':'audio/mpeg','ogg':'audio/ogg','wav':'audio/wav','woff2':'font/woff2','ttf':'font/ttf'};
    return types[path.split('.').last]??'application/octet-stream';
  }
}
