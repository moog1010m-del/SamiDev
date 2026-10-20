import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:samidev/runtime/game_haptics.dart';

void main() {
  testWidgets('native pattern preserves silence and cancels pending impacts', (
    tester,
  ) async {
    final impacts = <double>[];
    final h = GameHaptics(
      impact: (a) async {
        impacts.add(a);
      },
    );
    h.play({
      'amplitudes': [1, 0, .5],
      'durations': [20, 30, 10],
    });
    expect(impacts, [1]);
    await tester.pump(const Duration(milliseconds: 49));
    expect(impacts, [1]);
    await tester.pump(const Duration(milliseconds: 1));
    expect(impacts, [1, .5]);
    h.dispose();
    final cancelled = GameHaptics(
      impact: (a) async {
        impacts.add(a);
      },
    );
    cancelled.play({
      'amplitudes': [0, 1],
      'durations': [50, 10],
    });
    cancelled.cancel();
    await tester.pump(const Duration(milliseconds: 100));
    expect(impacts, [1, .5]);
    cancelled.dispose();
    cancelled.play({
      'amplitudes': [1],
      'durations': [20],
    });
    expect(impacts, [1, .5]);
  });
  testWidgets('invalid and excessive channel payloads never reach the device', (
    tester,
  ) async {
    final impacts = <double>[];
    final h = GameHaptics(
      impact: (a) async {
        impacts.add(a);
      },
    );
    for (final message in <Map>[
      {},
      {
        'amplitudes': [1],
        'durations': [],
      },
      {
        'amplitudes': [-1],
        'durations': [20],
      },
      {
        'amplitudes': [double.nan],
        'durations': [20],
      },
      {
        'amplitudes': [1],
        'durations': [501],
      },
      {'amplitudes': List.filled(17, 1), 'durations': List.filled(17, 10)},
      {'amplitudes': List.filled(5, 1), 'durations': List.filled(5, 500)},
      {
        'amplitudes': [0],
        'durations': [20],
      },
    ]) {
      h.play(message);
    }
    await tester.pump(const Duration(seconds: 3));
    expect(impacts, isEmpty);
    h.dispose();
  });
  testWidgets('burst limit and cancel channel do not queue a vibration storm', (
    tester,
  ) async {
    final impacts = <double>[];
    final h = GameHaptics(
      impact: (a) async {
        impacts.add(a);
      },
    );
    final request = {
      'amplitudes': [1, 0, .5],
      'durations': [10, 50, 10],
    };
    h.play(request);
    h.play(request);
    h.play({'action': 'cancel'});
    await tester.pump(const Duration(milliseconds: 100));
    expect(impacts, [1]);
    h.dispose();
  });
  testWidgets('uses native Flutter feedback levels without extra permissions', (
    tester,
  ) async {
    final calls = <String>[];
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(SystemChannels.platform, (call) async {
          if (call.method == 'HapticFeedback.vibrate')
            calls.add(call.arguments as String);
          return null;
        });
    addTearDown(
      () => TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(SystemChannels.platform, null),
    );
    for (final amplitude in [.1, .5, .8, 1.0]) {
      final h = GameHaptics();
      h.play({
        'amplitudes': [amplitude],
        'durations': [20],
      });
      await tester.pump();
      h.dispose();
    }
    expect(calls, [
      'HapticFeedbackType.selectionClick',
      'HapticFeedbackType.lightImpact',
      'HapticFeedbackType.mediumImpact',
      'HapticFeedbackType.heavyImpact',
    ]);
  });
}
