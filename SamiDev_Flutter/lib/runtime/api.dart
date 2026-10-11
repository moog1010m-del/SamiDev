import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'policy.dart';
import 'failures.dart';

abstract class SessionVault {
  Future<String?> read(String key);
  Future<void> write(String key, String? value);
}
class SecureSessionVault implements SessionVault {
  final FlutterSecureStorage storage = const FlutterSecureStorage(
    iOptions: IOSOptions(accessibility: KeychainAccessibility.first_unlock_this_device));
  @override Future<String?> read(String key) => storage.read(key: key);
  @override Future<void> write(String key, String? value) => value == null
    ? storage.delete(key: key) : storage.write(key: key, value: value);
}
class ApiResponse {
  ApiResponse(this.status, this.type, this.bytes);
  final int status;
  final String type;
  final Uint8List bytes;
  Map<String, dynamic> get json => jsonDecode(utf8.decode(bytes)) as Map<String, dynamic>;
}
class PlatformApi {
  PlatformApi(this.policy, this.vault,{HttpClient? httpClient}):client=httpClient??HttpClient(){client.connectionTimeout=const Duration(seconds:15);}
  final RuntimePolicy policy;
  final SessionVault vault;
  final HttpClient client;
  String? _session;
  int _generation = 0;
  bool _closed = false;
  String get _key => 'samidev.session.${policy.backend.origin}';
  bool get signedIn => _session != null;
  Future<void> restore() async {
    final saved = await vault.read(_key);
    if (saved != null && RegExp(r'^[A-Za-z0-9_-]{32,128}$').hasMatch(saved)) _session = saved;
  }
  Map<String, String> get headers => {'Origin':policy.backend.origin,
    if (_session != null) 'Cookie':'samidev_session=$_session'};
  Future<ApiResponse> request(String method, String path, {String? query, List<int>? body}) async {
    if (_closed || !RuntimePolicy.allowApi(method,path)) throw const HttpException('Route denied');
    final generation = _generation;
    final request = await client.openUrl(method, policy.upstream(path, query)).timeout(const Duration(seconds:20));
    request.followRedirects = false;
    headers.forEach((key,value) => request.headers.set(key,value));
    request.headers.set(HttpHeaders.acceptHeader,'application/json');
    if (body != null && body.isNotEmpty) {
      if (body.length > 512*1024) {request.abort(); throw const HttpException('Body too large');}
      request.headers.contentType = ContentType.json; request.add(body);
    }
    final response = await request.close().timeout(const Duration(seconds:20));
    if (response.statusCode >= 300 && response.statusCode < 400) {
      await response.drain<void>();throw const RuntimeFailure('UPSTREAM_REDIRECT','عنوان الخادم يعيد توجيه الطلب. يجب ضبط عنوان الخادم النهائي في التطبيق.');
    }
    final data=BytesBuilder(copy:false);var length=0;
    await for (final chunk in response.timeout(const Duration(seconds:20))) {
      length+=chunk.length;if(length>4*1024*1024) throw const HttpException('Response too large');
      data.add(chunk);
    }
    if (!_closed && generation == _generation) {
      if (response.statusCode == 401 || (path == '/api/auth/logout' && response.statusCode == 200)) {
        await clearSession();
      } else if ({'/api/auth/login','/api/auth/register'}.contains(path) && response.statusCode == 200) {
        final cookies=response.cookies.where((c)=>c.name=='samidev_session').toList();
        if(cookies.length!=1 || !cookies.single.httpOnly || !RegExp(r'^[A-Za-z0-9_-]{32,128}$').hasMatch(cookies.single.value)) {
          throw const RuntimeFailure('SESSION_COOKIE_INVALID','لم يرسل الخادم جلسة دخول صالحة. أبلغ الدعم.');
        }
        if(policy.backend.scheme=='https' && !cookies.single.secure) throw const RuntimeFailure('SESSION_COOKIE_INSECURE','الخادم غير مهيأ لتسجيل الدخول الآمن. أبلغ الدعم.');
        _session=cookies.single.value;_generation++;await vault.write(_key,_session);
      }
    }
    final bytes=data.takeBytes();
    if(response.statusCode>=500){
      var structured=false;
      try{structured=jsonDecode(utf8.decode(bytes)) is Map<String,dynamic>;}catch(_){}
      if(!structured){
        final failure=RuntimeFailure('UPSTREAM_HTTP_${response.statusCode}','الخادم أو بوابة الاتصال أعادا خطأ. تحقق من تشغيل الخادم والتانل.',status:response.statusCode);
        return ApiResponse(response.statusCode,'application/json',Uint8List.fromList(utf8.encode(jsonEncode(failure.json))));
      }
    }
    return ApiResponse(response.statusCode,response.headers.contentType?.mimeType??'application/json',bytes);
  }
  Future<void> clearSession() async {_generation++;_session=null;await vault.write(_key,null);}
  void close(){_closed=true;client.close(force:true);}
}
