import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:samidev/ui/legal_page.dart';
void main(){testWidgets('privacy loads offline and discloses draft and children limitations',(tester)async{
 await tester.pumpWidget(const MaterialApp(home:PlazrLegalPage()));await tester.pumpAndSettle();
 expect(find.text('سياسة الخصوصية'),findsOneWidget);
 expect(find.text('مسودة للمراجعة — ليست وثيقة إطلاق معتمدة'),findsOneWidget);
 expect(find.textContaining('الجمهور يشمل دون 13'),findsOneWidget);
 expect(tester.takeException(),isNull);
});}
