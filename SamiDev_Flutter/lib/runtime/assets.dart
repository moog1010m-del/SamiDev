import 'dart:collection';
import 'dart:convert';
import 'package:crypto/crypto.dart';
import 'package:flutter/services.dart';

class RuntimeAssets {
  RuntimeAssets({AssetBundle? bundle}) : bundle=bundle??rootBundle;
  final AssetBundle bundle;
  late final Map<String,dynamic> manifest;
  final LinkedHashMap<String,Uint8List> _cache=LinkedHashMap();
  final Map<String,Future<Uint8List>> _loading={};
  int _bytes=0;
  Future<void> load() async {
    manifest=jsonDecode(await bundle.loadString('assets/runtime-manifest.json')) as Map<String,dynamic>;
  }
  bool contains(String key) => (manifest['files'] as Map).containsKey(key);
  Future<Uint8List> read(String key) async {
    if(!contains(key)) throw const FormatException('Asset not bundled');
    final cached=_cache.remove(key);if(cached!=null){_cache[key]=cached;return cached;}
    return _loading.putIfAbsent(key,()=>_read(key)).whenComplete(()=>_loading.remove(key));
  }
  Future<Uint8List> _read(String key) async {
    final meta=manifest['files'][key] as Map;
    final data=await bundle.load('assets/runtime/$key');
    final bytes=data.buffer.asUint8List(data.offsetInBytes,data.lengthInBytes);
    if(bytes.length!=meta['size'] || sha256.convert(bytes).toString()!=meta['sha256']) {
      throw StateError('تعذر التحقق من سلامة ملفات التطبيق');
    }
    if(bytes.length<=12*1024*1024){
      while(_cache.isNotEmpty && _bytes+bytes.length>12*1024*1024){_bytes-=_cache.remove(_cache.keys.first)!.length;}
      _cache[key]=bytes;_bytes+=bytes.length;
    }
    return bytes;
  }
}
