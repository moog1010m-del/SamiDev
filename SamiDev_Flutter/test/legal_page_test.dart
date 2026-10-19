import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:samidev/ui/legal_page.dart';
void main(){testWidgets('privacy loads offline and shows policy without internal review notes',(tester)async{
 await tester.pumpWidget(const MaterialApp(home:PlazrLegalPage()));await tester.pumpAndSettle();
 expect(find.text('سياسة الخصوصية'),findsOneWidget);
 expect(find.textContaining('مسودة للمراجعة'),findsNothing);
 expect(find.textContaining('آخر تحديث:'),findsOneWidget);
 expect(tester.takeException(),isNull);
});}
