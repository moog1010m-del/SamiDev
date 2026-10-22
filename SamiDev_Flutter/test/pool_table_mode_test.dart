import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:samidev/ui/community_hub.dart';

void main() {
  testWidgets('large table remains an explicit match choice on mobile', (tester) async {
    Map<String, String>? result;
    await tester.pumpWidget(MaterialApp(home: Builder(builder: (context) => Scaffold(body: TextButton(
      child: const Text('افتح'),
      onPressed: () async {
        result = await showModalBottomSheet<Map<String, String>>(
          context: context, isScrollControlled: true,
          builder: (_) => const CreateMatchSheet(initialGame: 'pool'),
        );
      },
    )))));
    await tester.tap(find.text('افتح'));
    await tester.pumpAndSettle();
    expect(find.text('الأصلية'), findsOneWidget);
    await tester.tap(find.text('الأصلية'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('الطاولة الكبيرة').last);
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('إنشاء المباراة'));
    await tester.tap(find.text('إنشاء المباراة'));
    await tester.pumpAndSettle();
    expect(result?['game'], 'pool');
    expect(result?['largeTable'], '1');
    expect(tester.takeException(), isNull);
  });
}
