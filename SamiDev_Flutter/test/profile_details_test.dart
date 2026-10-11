import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:samidev/ui/profile_details.dart';

void main() {
  testWidgets('owned preview, browsing, filtering, item details and detailed ranks', (tester) async {
    tester.view.physicalSize = const Size(390, 1100);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final user = <String, dynamic>{
      'relation': 'self', 'legacyWins': 4,
      'showcaseItems': [
        for (var i = 0; i < 4; i++) {'id': 'item_$i', 'name': 'مقتنى $i', 'gameId': i == 3 ? 'pool' : '', 'asset': '/platform/assets/profile/raster/star.webp', 'quantity': i == 0 ? 2 : 1},
      ],
      'gameStatistics': [
        {'gameId': 'pool', 'level': 3, 'wins': 23, 'played': 30, 'losses': 7, 'draws': 0, 'rankName': 'بداية', 'progress': .53, 'winsToNextLevel': 7},
      ],
    };
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: SingleChildScrollView(child: ProfileDetails(user: user))))));
    await tester.pumpAndSettle();
    expect(find.text('مقتنى 0'), findsOneWidget);
    expect(find.text('مقتنى 3'), findsNothing);
    expect(find.text('23 فوز'), findsOneWidget);
    expect(find.text('خسر 7'), findsNothing);
    await tester.tap(find.text('تصفّح كل المقتنيات (5)'));
    await tester.pumpAndSettle();
    expect(find.text('مقتنى 3'), findsOneWidget);
    await tester.tap(find.byType(DropdownButton<String>));
    await tester.pumpAndSettle();
    await tester.tap(find.text('البلياردو').last);
    await tester.pumpAndSettle();
    expect(find.text('مقتنى 0'), findsNothing);
    expect(find.text('مقتنى 3'), findsOneWidget);
    await tester.tap(find.text('مقتنى 3'));
    await tester.pumpAndSettle();
    expect(find.byType(AlertDialog), findsOneWidget);
    await tester.tap(find.text('إغلاق'));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('عرض التفاصيل'));
    await tester.tap(find.text('عرض التفاصيل'));
    await tester.pumpAndSettle();
    expect(find.text('خسر 7'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
