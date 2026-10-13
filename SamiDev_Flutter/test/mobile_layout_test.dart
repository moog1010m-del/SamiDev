import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:samidev/ui/community_hub.dart';
import 'package:samidev/ui/game_viewport.dart';

void main(){
  testWidgets('chat composer does not reserve an empty history panel',(tester)async{
    final input=TextEditingController();var sends=0;
    await tester.pumpWidget(MaterialApp(home:Scaffold(body:Column(children:[const Expanded(child:SizedBox()),ChatComposer(controller:input,sending:false,onSend:()=>sends++)]))));
    expect(tester.getSize(find.byType(ChatComposer)).height,lessThan(75));
    await tester.enterText(find.byType(TextField),'مرحبا');await tester.tap(find.byTooltip('إرسال'));expect(sends,1);
    await tester.pumpWidget(const SizedBox());input.dispose();
  });
  testWidgets('keyboard clips the board without shrinking engine coordinates',(tester)async{
    tester.view.physicalSize=const Size(390,844);tester.view.devicePixelRatio=1;
    addTearDown(tester.view.resetPhysicalSize);addTearDown(tester.view.resetDevicePixelRatio);
    final surface=GlobalKey();final viewport=GlobalKey();
    Widget page(double keyboard,double available,{bool active=true})=>MaterialApp(home:MediaQuery(data:MediaQueryData(size:const Size(390,844),viewInsets:EdgeInsets.only(bottom:keyboard)),child:Align(alignment:Alignment.topCenter,child:SizedBox(width:390,height:available,child:GameViewport(key:viewport,active:active,dim:keyboard>0,child:SizedBox.expand(key:surface))))));
    await tester.pumpWidget(page(0,740));expect(tester.getSize(find.byKey(surface)),const Size(390,740));
    await tester.pumpWidget(page(0,560,active:false));expect(tester.getSize(find.byKey(surface)),const Size(390,740));
    await tester.pumpWidget(page(300,440));expect(tester.getSize(find.byKey(surface)),const Size(390,740));
    await tester.pumpWidget(page(0,740));expect(tester.getSize(find.byKey(surface)),const Size(390,740));
  });
  testWidgets('create sheet offers only supported games and real card settings',(tester)async{
    await tester.pumpWidget(const MaterialApp(home:Scaffold(body:CreateMatchSheet())));
    expect(find.text('نوع البلياردو'),findsOneWidget);
    await tester.tap(find.byType(DropdownButtonFormField<String>).at(1));await tester.pumpAndSettle();
    await tester.ensureVisible(find.text('قيم بول · أول من يسجل ٨ كرات').last);
    await tester.tap(find.text('قيم بول · أول من يسجل ٨ كرات').last);await tester.pumpAndSettle();
    expect(find.text('قيم بول · أول من يسجل ٨ كرات'),findsOneWidget);
    await tester.tap(find.byType(DropdownButtonFormField<String>).first);await tester.pumpAndSettle();
    await tester.tap(find.text('أونو').last);await tester.pumpAndSettle();
    expect(find.text('البطاقات'),findsOneWidget);expect(find.text('اللاعبون'),findsOneWidget);
    expect(find.text('غولف'),findsNothing);expect(find.text('إنشاء المباراة'),findsOneWidget);
  });
}
