import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:samidev/ui/floating_game_chat.dart';
import 'package:samidev/ui/offline_shell.dart';
import 'package:samidev/ui/game_viewport.dart';
void main(){
  testWidgets('offline shell keeps bundled discovery visible and blocks network matches',(tester)async{
    var retries=0,unavailable=0;
    await tester.pumpWidget(MaterialApp(home:Scaffold(body:OfflineShell(connecting:false,onRetry:()=>retries++,onUnavailable:()=>unavailable++))));
    expect(find.text('البلياردو'),findsWidgets);
    await tester.tap(find.text('البلياردو').first);await tester.pumpAndSettle();
    expect(unavailable,0); // Browsing a bundled game does not require network.
    await tester.tap(find.text('انضم').first);await tester.pumpAndSettle();expect(unavailable,1);
    await tester.tap(find.text('إعادة الاتصال'));expect(retries,1);
    expect(find.byType(CircularProgressIndicator),findsNothing);
  });
  testWidgets('chat floats transparently and touches reach the board without a toggle',(tester)async{
    final scroll=ScrollController();var taps=0;
    await tester.pumpWidget(MaterialApp(home:Scaffold(body:GameViewport(child:GestureDetector(behavior:HitTestBehavior.opaque,onTap:()=>taps++,child:const ColoredBox(color:Colors.blue)),overlay:FloatingGameChat(messages:const [{'seat':0,'text':'hello'}],roster:const [{'seat':0,'name':'player'}],seat:0,controller:scroll,interactive:false)))));
    expect(find.text('hello'),findsOneWidget);
    final materials=tester.widgetList<Material>(find.descendant(of:find.byType(FloatingGameChat),matching:find.byType(Material)));
    expect(materials.every((m)=>m.type==MaterialType.transparency),isTrue);
    await tester.tapAt(tester.getCenter(find.text('hello')));expect(taps,1);
    expect(find.byTooltip('عرض المحادثة'),findsNothing);
    await tester.pumpWidget(const SizedBox());scroll.dispose();
  });
  testWidgets('keyboard does not add a black scrim over the board',(tester)async{
    await tester.pumpWidget(const MaterialApp(home:Scaffold(body:GameViewport(dim:true,child:ColoredBox(color:Colors.blue)))));
    expect(tester.widgetList<ColoredBox>(find.byType(ColoredBox)).where((box)=>box.color==const Color(0x55000000)),isEmpty);
  });
}
