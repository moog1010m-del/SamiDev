import 'package:flutter/services.dart';
import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/rendering.dart';
import 'package:samidev/main.dart' show SamiDevApp;
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:samidev/ui/games_hub.dart';

void main(){
  testWidgets('mobile discovery launches existing quick room bridge with exact Pyramid rules',(tester)async{
    tester.view.physicalSize=const Size(390,844);tester.view.devicePixelRatio=1;
    addTearDown(tester.view.resetPhysicalSize);addTearDown(tester.view.resetDevicePixelRatio);
    const visualOut=String.fromEnvironment('SAMIDEV_VISUAL_OUTPUT');
    if(visualOut.isNotEmpty){await tester.runAsync(()async{
      final loader=FontLoader('PreviewArabic')..addFont(Future.value(ByteData.sublistView(await File('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf').readAsBytes())));await loader.load();
      final icons=FontLoader('MaterialIcons')..addFont(Future.value(ByteData.sublistView(await File('/workspace/.flutter-sdk/bin/cache/artifacts/material_fonts/MaterialIcons-Regular.otf').readAsBytes())));await icons.load();
    });}
    String? game;Map<String,String>? query;
    final key=GlobalKey<GamesHubState>(),captureKey=GlobalKey();
    Future<void> capture(String name)async{
      const out=String.fromEnvironment('SAMIDEV_VISUAL_OUTPUT');if(out.isEmpty)return;
      await tester.pumpAndSettle();
      await tester.runAsync(()async{
      final image=await (captureKey.currentContext!.findRenderObject() as RenderRepaintBoundary).toImage(pixelRatio:2);
      final data=await image.toByteData(format:ui.ImageByteFormat.png);
      await Directory(out).create(recursive:true);await File('$out/$name.png').writeAsBytes(data!.buffer.asUint8List());image.dispose();
      });
    }
    await tester.pumpWidget(MaterialApp(theme:const SamiDevApp().theme(Brightness.dark).copyWith(textTheme:visualOut.isEmpty?null:const SamiDevApp().theme(Brightness.dark).textTheme.apply(fontFamily:'PreviewArabic')),home:Scaffold(body:RepaintBoundary(key:captureKey,child:Directionality(textDirection:TextDirection.rtl,child:GamesHub(key:key,user:const {'gameStatistics':[{'gameId':'pool','level':3,'wins':23,'progress':.53,'rankName':'بداية'}]},onGame:(g,q)async{game=g;query=q;}))))));
    if(visualOut.isNotEmpty){await tester.runAsync(()async{for(final item in supportedGames){await precacheImage(AssetImage('assets/runtime/room-sprites/${item.asset}.png'),key.currentContext!);}
      await precacheImage(const AssetImage('assets/runtime/platform/assets/ranks/level-003.png'),key.currentContext!);});}
    await capture('games-grid');
    expect(find.text('البلياردو'),findsOneWidget);expect(find.text('الكيرم'),findsOneWidget);
    expect(find.text('بوكر'),findsNothing);expect(find.text('Ranked'),findsNothing);
    await tester.tap(find.text('البلياردو'));await tester.pumpAndSettle();
    expect(find.text('اللعب السريع'),findsOneWidget);expect(find.text('23 فوز'),findsOneWidget);await capture('pool-matching');
    final row=find.ancestor(of:find.text('الهرم الحر'),matching:find.byType(Row)).first;
    final join=find.descendant(of:row,matching:find.text('انضم'));
    await tester.ensureVisible(join);await tester.pumpAndSettle();await tester.tap(join);await tester.pumpAndSettle();
    expect(game,'pool');expect(query?['action'],'quick');expect(query?['preset'],'pool-pyramid');expect(query?['gameType'],'8');expect(query?['community'],'square');
    expect(tester.takeException(),isNull);expect(key.currentState!.back(),isTrue);await tester.pumpAndSettle();expect(find.text('الكل'),findsOneWidget);
  });
}
