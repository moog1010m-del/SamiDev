import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';
import 'dart:typed_data';
import 'assets.dart';

/// Bundled game engine only. This class has no API, auth, remote socket or URL.
class ChildRuntime {
  ChildRuntime(this.game, {RuntimeAssets? assets}) : assets = assets ?? RuntimeAssets() {
    if (!entries.containsKey(game)) throw ArgumentError.value(game, 'game');
  }
  static const entries = {'pool': '/games/pool/index.html', 'carrom': '/index.html', 'tablesoccer': '/games/tablesoccer/index.html'};
  static const scripts = {'samidev-games.js', 'game-touch.js', 'browser-runtime.js', 'launcher.js'};
  final String game;
  final RuntimeAssets assets;
  HttpServer? _server;
  bool _used = false, _closed = false;
  final _secret = base64Url.encode(List<int>.generate(32, (_) => Random.secure().nextInt(256))).replaceAll('=', '');
  late final Uri origin;
  Uri get launch => origin.replace(path: '/_child/$_secret');
  Uri get entry => origin.replace(path: entries[game], queryParameters: const {'play': '1', 'gameType': '0', 'players': '0', 'live': '1'});
  bool owns(Uri uri) => !_closed && _server != null && uri.scheme == 'http' && uri.host == '127.0.0.1' && uri.port == origin.port && uri.userInfo.isEmpty;
  bool allowsNavigation(Uri uri) => owns(uri) && ((!_used && uri.path == launch.path) || uri == entry);
  Future<void> start() async {
    await assets.load();
    await assets.read(entries[game]!.substring(1));
    if (_closed) return;
    _server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    origin = Uri.parse('http://127.0.0.1:${_server!.port}');
    if (_closed) { await _server!.close(force: true); return; }
    _server!.listen((request) => unawaited(_handle(request)));
  }
  bool _allowed(String key) {
    if (key.isEmpty || key.contains('..') || key.contains('\\') || key.contains('%') || key.startsWith('platform/') || key == 'game-host.html') return false;
    if (key.endsWith('.html')) return '/$key' == entries[game];
    if (key.endsWith('.js')) {
      final main = game == 'carrom' ? 'main.js' : 'games/$game/main.js';
      return scripts.contains(key) || key == main;
    }
    return assets.contains(key);
  }
  String _document(String html) {
    // Drop all online/social/shop scripts, including their inline event handlers.
    html = html.replaceAllMapped(RegExp(r'<script\b([^>]*)>([\s\S]*?)</script>', caseSensitive: false), (match) {
      final src = RegExp(r'''\bsrc\s*=\s*["']([^"']+)["']''', caseSensitive: false).firstMatch(match[1]!);
      if (src == null) return match[0]!; // Shipped dictionaries and asset lists.
      final name = Uri.parse(src[1]!).path.split('/').last;
      if (name == 'client-config.js') return '<script src="/client-config.js"></script>';
      return scripts.contains(name) ? '<script src="/$name"></script>' : '';
    });
    if (game == 'carrom') {
      const labels = {'شريط تحريك القرص':'Striker position','دورك':'Your turn','اللاعب {0}':'Player {0}','دورك للعب':'Your turn','انتهى وقت دورك':'Turn timed out', 'دور {0} للعب':'Player {0} turn', 'خطأ: دخل القرص الضارب في الجيب':'Striker pocketed', 'المساعدة':'Help', 'حرّك القرص الضارب':'Move the striker'};
      for (final label in labels.entries) { html = html.replaceAll(jsonEncode(label.key), jsonEncode(label.value)); }
    }
    return html.replaceFirst('<head>', '<head><script>window.__SAMIDEV_QUERY=${jsonEncode(entry.query)};window.__PLAZR_CHILD_OFFLINE=true;</script><style>#mode-menu-button{display:none!important}</style>');
  }
  Future<void> _handle(HttpRequest request) async {
    try {
      final path = request.uri.path;
      final headers = request.response.headers;
      headers.set('Cache-Control', 'no-store');
      headers.set('X-Content-Type-Options', 'nosniff');
      headers.set('Referrer-Policy', 'no-referrer');
      headers.set('X-Frame-Options', 'DENY');
      headers.set('Permissions-Policy', 'camera=(), microphone=(), geolocation=(), payment=(), usb=()');
      headers.set('Content-Security-Policy', "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self'; frame-src 'none'; worker-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'");
      if (_closed || request.headers.value('Host') != origin.authority || request.headers.value('Sec-Fetch-Site') == 'cross-site' || (request.headers.value('Origin') != null && request.headers.value('Origin') != origin.origin)) { request.response.statusCode = 403; return; }
      if (!{'GET', 'HEAD'}.contains(request.method)) { request.response.statusCode = 405; return; }
      if (path == launch.path && !_used && request.method == 'GET') {
        _used = true;
        headers.add('Set-Cookie', 'plazr_child=$_secret; Path=/; HttpOnly; SameSite=Strict');
        request.response.statusCode = 303;
        headers.set('Location', entry.toString());
        return;
      }
      if (!request.cookies.any((c) => c.name == 'plazr_child' && c.value == _secret)) { request.response.statusCode = 403; return; }
      if (path.startsWith('/api/') || path.startsWith('/ws') || path.startsWith('/_child/')) { request.response.statusCode = 403; return; }
      if (path == '/client-config.js') {
        headers.contentType = ContentType('application', 'javascript', charset: 'utf-8');
        request.response.write('window.__SAMIDEV_CLIENT_CONFIG=${jsonEncode({'platformEnabled': false, 'requireGameAuth': false, 'production': true, 'games': {for (final g in entries.keys) g: {'mainJsSha256': assets.manifest['engines'][g]}}})};');
        return;
      }
      final key = path.substring(1);
      if (!_allowed(key) || !assets.contains(key)) { request.response.statusCode = 403; return; }
      if (key.endsWith('.html') && request.uri != Uri(path: entry.path, query: entry.query)) { request.response.statusCode = 403; return; }
      var bytes = await assets.read(key);
      if (key.endsWith('.html')) bytes = Uint8List.fromList(utf8.encode(_document(utf8.decode(bytes))));
      headers.set('Content-Type', _mime(key));
      headers.set('Accept-Ranges', 'bytes');
      var start = 0, end = bytes.length - 1;
      final range = request.headers.value('Range');
      if (range != null) {
        final parts = RegExp(r'^bytes=(\d+)-(\d*)$').firstMatch(range);
        if (parts == null) { request.response.statusCode = 416; return; }
        start = int.tryParse(parts[1]!) ?? bytes.length;
        if (parts[2]!.isNotEmpty) end = min(end, int.tryParse(parts[2]!) ?? -1);
        if (start > end || start >= bytes.length) { request.response.statusCode = 416; return; }
        request.response.statusCode = 206;
        headers.set('Content-Range', 'bytes $start-$end/${bytes.length}');
      }
      request.response.contentLength = end - start + 1;
      if (request.method != 'HEAD') request.response.add(bytes.sublist(start, end + 1));
    } catch (_) { try { request.response.statusCode = 500; } catch (_) {} }
    finally { try { await request.response.close(); } catch (_) {} }
  }
  static String _mime(String key) => switch (key.split('.').last) {
    'html' => 'text/html; charset=utf-8', 'js' => 'application/javascript; charset=utf-8', 'css' => 'text/css; charset=utf-8', 'json' => 'application/json; charset=utf-8',
    'png' => 'image/png', 'webp' => 'image/webp', 'jpg' || 'jpeg' => 'image/jpeg', 'svg' => 'image/svg+xml', 'ogg' => 'audio/ogg', 'mp3' => 'audio/mpeg', 'm4a' => 'audio/mp4', 'wav' => 'audio/wav', 'woff2' => 'font/woff2', 'ttf' => 'font/ttf', _ => 'application/octet-stream',
  };
  Future<void> close() async { _closed = true; await _server?.close(force: true); }
}
