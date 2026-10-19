import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:samidev/runtime/assets.dart';
import 'package:samidev/runtime/child_runtime.dart';
import 'child_runtime_test.dart' show FileBundle;
void main() {
  test('original local engines render and accept moves without external requests', () async {
    for (final game in ChildRuntime.entries.keys) {
      final runtime = ChildRuntime(game, assets: RuntimeAssets(bundle: FileBundle()));
      try {
        await runtime.start();
        final process = await Process.start('node', ['../SamiDev_Platform/tests/children_offline_browser.mjs', runtime.launch.toString(), game], environment: Platform.environment);
        process.stdout.transform(SystemEncoding().decoder).listen(stdout.write);
        process.stderr.transform(SystemEncoding().decoder).listen(stderr.write);
        expect(await process.exitCode, 0, reason: game);
      } finally { await runtime.close(); }
    }
  }, skip: Platform.environment['PLAZR_CHILD_BROWSER'] != '1', timeout: const Timeout(Duration(minutes: 5)));
}
