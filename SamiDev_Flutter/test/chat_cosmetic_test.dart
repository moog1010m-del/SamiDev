import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:samidev/ui/chat_cosmetic.dart';

void main() {
  for (final id in ChatCosmetic.sizes.keys) {
    testWidgets('$id fits short and long text without shrinking the avatar', (
      tester,
    ) async {
      tester.view.physicalSize = const Size(360, 780);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final widths = <double>[];
      for (final text in ['ألو', 'رسالة طويلة ${'كلمة ' * 40}']) {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: Padding(
                padding: const EdgeInsets.all(16),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const SizedBox(
                      key: ValueKey('avatar'),
                      width: 40,
                      height: 40,
                      child: CircleAvatar(child: Icon(Icons.person)),
                    ),
                    const SizedBox(width: 10),
                    Flexible(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text('اسم اللاعب · الآن'),
                          ChatCosmetic(
                            id: id,
                            child: Text(text, textDirection: TextDirection.rtl),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        );
        await tester.pumpAndSettle();
        expect(
          tester.getSize(find.byKey(const ValueKey('avatar'))),
          const Size(40, 40),
        );
        final size = tester.getSize(find.byType(ChatCosmetic));
        expect(size.width, lessThanOrEqualTo(278));
        widths.add(size.width);
        expect(tester.takeException(), isNull);
      }
      expect(widths.first, lessThan(widths.last));
    });
  }
}
