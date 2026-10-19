import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:samidev/ui/participation_gate.dart';
import 'session_test.dart' show MemoryVault;

void main() {
  testWidgets('participation starts only after explicit agreement and persists', (tester) async {
    final vault = MemoryVault();
    await tester.pumpWidget(MaterialApp(home: ParticipationGate(vault: vault, child: const Text('inside'))));
    await tester.pumpAndSettle();
    expect(find.text('inside'), findsNothing);
    expect(tester.widget<FilledButton>(find.widgetWithText(FilledButton, 'متابعة')).onPressed, isNull);
    await tester.tap(find.byType(CheckboxListTile));
    await tester.pump();
    await tester.ensureVisible(find.text('متابعة'));
    await tester.tap(find.text('متابعة'));
    await tester.pumpAndSettle();
    expect(find.text('inside'), findsOneWidget);
    expect(await vault.read(ParticipationGate.storageKey), 'accepted');
    await tester.pumpWidget(const SizedBox());
    await tester.pumpWidget(MaterialApp(home: ParticipationGate(vault: vault, child: const Text('restored'))));
    await tester.pumpAndSettle();
    expect(find.text('restored'), findsOneWidget);
  });
}
