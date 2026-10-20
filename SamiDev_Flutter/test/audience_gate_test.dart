import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:samidev/runtime/api.dart';
import 'package:samidev/ui/audience_gate.dart';
import 'session_test.dart' show MemoryVault;
class UnreadableVault implements SessionVault {
  @override Future<String?> read(String key) async => throw StateError('unavailable');
  @override Future<void> write(String key, String? value) async => throw StateError('unavailable');
}
void main() {
  test('birthday boundary, Arabic digits and impossible/future dates', () {
    final now = DateTime(2026, 10, 19);
    expect(AudienceGate.classify('19', '10', '2013', now), 'general');
    expect(AudienceGate.classify('20', '10', '2013', now), 'restricted');
    expect(AudienceGate.classify('١٩', '١٠', '٢٠١٤', now), 'restricted');
    expect(AudienceGate.classify('31', '2', '2014', now), isNull);
    expect(AudienceGate.classify('20', '10', '2026', now), isNull);
    expect(AudienceGate.classify('', '', '', now), isNull);
  });
  testWidgets('old acceptance cannot bypass age; child never constructs network widget', (tester) async {
    final vault = MemoryVault();
    vault.data['plazr.community-rules.2026-10-19.1'] = 'accepted';
    var onlineBuilds = 0;
    await tester.pumpWidget(MaterialApp(home: AudienceGate(vault: vault, clock: () => DateTime(2026, 10, 19), restrictedChild: const Text('local-only'), child: Builder(builder: (_) { onlineBuilds++; return const Text('online'); }))));
    await tester.pumpAndSettle(); expect(onlineBuilds, 0);
    await tester.enterText(find.byType(TextField).at(0), '19');
    await tester.enterText(find.byType(TextField).at(1), '10');
    await tester.enterText(find.byType(TextField).at(2), '2014');
    await tester.tap(find.text('متابعة')); await tester.pumpAndSettle();
    expect(find.text('local-only'), findsOneWidget); expect(onlineBuilds, 0);
    expect(vault.data[AudienceGate.storageKey], 'restricted');
    expect(vault.data.values.any((v) => v.contains('2014')), false);
    await tester.pumpWidget(const SizedBox());
    await tester.pumpWidget(MaterialApp(home: AudienceGate(vault: vault, restrictedChild: const Text('restored-local'), child: Builder(builder: (_) { onlineBuilds++; return const Text('online'); }))));
    await tester.pumpAndSettle(); expect(find.text('restored-local'), findsOneWidget); expect(onlineBuilds, 0);
    expect(find.byType(TextField), findsNothing);
  });
  testWidgets('unreadable age storage cannot open online route', (tester) async {
    var onlineBuilds = 0;
    await tester.pumpWidget(MaterialApp(home: AudienceGate(vault: UnreadableVault(), child: Builder(builder: (_) { onlineBuilds++; return const Text('online'); }))));
    await tester.pumpAndSettle(); expect(onlineBuilds, 0);
    expect(tester.widget<FilledButton>(find.widgetWithText(FilledButton, 'متابعة')).onPressed, isNull);
  });
}
