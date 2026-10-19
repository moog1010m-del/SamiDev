import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:samidev/ui/friend_banner.dart';

void main() {
  testWidgets('friend banner opens, swipes up and expires without overflow', (
    tester,
  ) async {
    var opened = 0, dismissed = 0;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: FriendBanner(
            username: 'Friend_123',
            text: 'رسالة جديدة',
            onOpen: () => opened++,
            onDismiss: () => dismissed++,
          ),
        ),
      ),
    );
    await tester.tap(find.text('رسالة جديدة'));
    expect(opened, 1);
    await tester.drag(find.byType(Dismissible), const Offset(0, -400));
    await tester.pumpAndSettle();
    expect(dismissed, 1);
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: FriendBanner(
            username: 'Friend_456',
            text: 'رسالة أخرى',
            onOpen: () {},
            onDismiss: () => dismissed++,
          ),
        ),
      ),
    );
    await tester.pump(const Duration(seconds: 6));
    expect(dismissed, 2);
    expect(tester.takeException(), isNull);
  });
}
