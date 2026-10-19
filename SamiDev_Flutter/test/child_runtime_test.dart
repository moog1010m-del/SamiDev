import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter/services.dart';
import 'package:samidev/runtime/assets.dart';
import 'package:samidev/runtime/child_runtime.dart';
class FileBundle extends CachingAssetBundle {
  @override Future<ByteData> load(String key) async => ByteData.sublistView(Uint8List.fromList(await File(key).readAsBytes()));
}
void main() {
  test('child host denies API, sockets, online entry, other documents and untrusted origins', () async {
    final runtime = ChildRuntime('pool', assets: RuntimeAssets(bundle: FileBundle())); final client = HttpClient();
    try {
      await runtime.start(); String? cookie;
      Future<({int status, String text, HttpHeaders headers})> get(Uri uri, {String? origin}) async {
        final request = await client.getUrl(uri); request.followRedirects = false;
        if (cookie != null) request.headers.set('Cookie', cookie!);
        if (origin != null) request.headers.set('Origin', origin);
        final response = await request.close();
        if (response.cookies.isNotEmpty) cookie = '${response.cookies.first.name}=${response.cookies.first.value}';
        return (status: response.statusCode, text: await utf8.decodeStream(response), headers: response.headers);
      }
      expect((await get(runtime.entry)).status, 403);
      expect((await get(runtime.launch, origin: 'https://untrusted.example')).status, 403);
      final launched = await get(runtime.launch); expect(launched.status, 303);
      expect(launched.headers.value('set-cookie'), contains('HttpOnly'));
      final html = await get(runtime.entry); expect(html.status, 200);
      expect(html.text, contains('__PLAZR_CHILD_OFFLINE=true'));
      expect(html.text, isNot(contains('src="/samidev-network.js')));
      expect(html.text, isNot(contains('src="/inventory-ui.js')));
      expect(html.headers.value('content-security-policy'), contains("connect-src 'self'"));
      for (final path in ['/api/me', '/api/auth/guest', '/api/game-ticket', '/ws', '/platform/', '/platform/platform.js', '/samidev-network.js', '/games/crazy8/index.html']) {
        expect((await get(runtime.origin.replace(path: path))).status, 403, reason: path);
      }
      expect((await get(runtime.entry.replace(query: 'online=1'))).status, 403);
      expect(runtime.allowsNavigation(runtime.entry.replace(query: 'online=1')), false);
      expect(runtime.allowsNavigation(Uri.parse('https://plazr.cc')), false);
      expect((await get(runtime.origin.replace(path: '/browser-runtime.js'))).status, 200);
      expect((await get(runtime.origin.replace(path: '/games/pool/main.js'))).status, 200);
    } finally { client.close(force: true); await runtime.close(); }
  });
}
