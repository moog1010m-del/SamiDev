import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:samidev/ui/account_settings.dart';

import 'account_settings_test.dart' show SecurityAccountApi;

void main() {
  setUpAll(() async {
    final icons = FontLoader('MaterialIcons');
    icons.addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'));
    await icons.load();
    final font = Platform.environment['SAMIDEV_TEST_FONT'];
    if (font != null) {
      final loader = FontLoader('SettingsReview');
      loader.addFont(
        File(font).readAsBytes().then((bytes) => ByteData.sublistView(bytes)),
      );
      await loader.load();
    }
  });
  for (final brightness in Brightness.values) {
    testWidgets(
      'settings navigation and device sheet fit a small phone with large text in $brightness',
      (tester) async {
        tester.view.physicalSize = const Size(320, 690);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        final api = SecurityAccountApi();
        addTearDown(api.close);
        final capture = GlobalKey();
        await tester.pumpWidget(
          RepaintBoundary(
            key: capture,
            child: MaterialApp(
              debugShowCheckedModeBanner: false,
              theme: ThemeData(
                brightness: brightness,
                fontFamily: Platform.environment['SAMIDEV_TEST_FONT'] == null
                    ? null
                    : 'SettingsReview',
              ),
              builder: (context, child) => MediaQuery(
                data: MediaQuery.of(context)
                    .copyWith(textScaler: TextScaler.linear(1.25)),
                child: child!,
              ),
              home: AccountSettings(
                api: api,
                user: {
                  'id': 'saved',
                  'username': 'Saved_player',
                  'isGuest': false,
                  'freeRenameAvailable': true,
                },
                onChanged: (_) async {},
                onTheme: () {},
              ),
            ),
          ),
        );
        await tester.pumpAndSettle();
        Future<void> screenshot(String name) async {
          final folder = Platform.environment['SAMIDEV_TEST_ARTIFACTS'];
          if (folder == null) return;
          await tester.runAsync(() async {
            final boundary =
                capture.currentContext!.findRenderObject()!
                    as RenderRepaintBoundary;
            final picture = await boundary.toImage();
            final bytes = await picture.toByteData(
              format: ui.ImageByteFormat.png,
            );
            await Directory(folder).create(recursive: true);
            await File('$folder/native-settings-$name-${brightness.name}.png')
                .writeAsBytes(bytes!.buffer.asUint8List());
            picture.dispose();
          });
        }

        await screenshot('menu');
        await tester.tap(find.text('الحساب'));
        await tester.pumpAndSettle();
        expect(find.text('saved@example.test'), findsOneWidget);
        expect(find.byType(TextField), findsNothing);
        expect(tester.takeException(), isNull);
        await screenshot('account');
        await tester.tap(find.byTooltip('رجوع'));
        await tester.pumpAndSettle();
        await tester.tap(find.text('الأجهزة'));
        await tester.pumpAndSettle();
        await screenshot('devices');
        await tester.ensureVisible(find.text('Windows'));
        await tester.pumpAndSettle();
        await tester.tap(find.text('Windows'));
        await tester.pumpAndSettle();
        await screenshot('detail');
        expect(tester.takeException(), isNull);
        expect(api.writes, isEmpty);
        await tester.tap(find.byTooltip('إغلاق التفاصيل'));
        await tester.pumpAndSettle();
        expect(api.writes, isEmpty);
        await tester.tap(find.byTooltip('رجوع'));
        await tester.pumpAndSettle();
        expect(find.text('الإعدادات'), findsOneWidget);
        expect(tester.takeException(), isNull);
      },
    );
  }
}
