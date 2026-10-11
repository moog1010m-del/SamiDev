import 'dart:async';
import 'dart:io';
import 'package:flutter/services.dart';

/// Safe diagnostics: never include response bodies, credentials, cookies or URLs.
class RuntimeFailure implements Exception {
  const RuntimeFailure(this.code,this.message,{this.status=502});
  final String code,message;
  final int status;
  Map<String,dynamic> get json=>{'ok':false,'error':code,'message':'$message ($code)'};
  static RuntimeFailure from(Object error,{bool asset=false}) {
    if(error is RuntimeFailure)return error;
    if(asset)return const RuntimeFailure('APP_ASSETS_INVALID','ملفات التطبيق ناقصة أو غير متطابقة. أعد بناء التطبيق بعد مزامنة الأصول.',status:500);
    if(error is TimeoutException)return const RuntimeFailure('UPSTREAM_TIMEOUT','انتهت مهلة اتصال الخادم. حاول مجددًا.',status:504);
    if(error is HandshakeException)return const RuntimeFailure('UPSTREAM_TLS_FAILED','تعذر التحقق من اتصال الخادم الآمن. أبلغ الدعم.');
    if(error is SocketException)return const RuntimeFailure('UPSTREAM_UNREACHABLE','تعذر الوصول إلى الخادم. تحقق من الاتصال وتوفر الخادم.',status:503);
    if(error is PlatformException)return const RuntimeFailure('SESSION_STORAGE_UNAVAILABLE','تعذر استخدام التخزين الآمن للجلسة على الجهاز. أعد تشغيل التطبيق.',status:500);
    return const RuntimeFailure('LOCAL_GATEWAY_FAILED','تعذر إكمال الاتصال بالخادم. أبلغ الدعم بالرمز الظاهر.');
  }
  @override String toString()=>'$message ($code)';
}
