import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:samidev/ui/chat_cosmetic.dart';

void main(){
  for(final id in ['chat_ember','chat_mist','chat_turquoise']){
    testWidgets('$id paints a short and multiline native message without nine-patch overflow',(tester) async {
      for(final text in ['سلام','رسالة طويلة لاختبار تمدد إطار المحادثة\nبسطر ثانٍ دون قص الزوايا']){
        await tester.pumpWidget(MaterialApp(home:Scaffold(body:Center(child:ConstrainedBox(constraints:const BoxConstraints(maxWidth:260),child:ChatCosmetic(id:id,child:Text(text)))))));
        final context=tester.element(find.byType(ChatCosmetic));
        await tester.runAsync(()=>precacheImage(ExactAssetImage('assets/runtime/platform/assets/cosmetics/$id.webp',scale:4),context));
        await tester.pumpAndSettle();
        expect(tester.takeException(),isNull);
        final image=tester.widget<Image>(find.byType(Image));
        expect(image.centerSlice,isNotNull);
        expect((image.image as ExactAssetImage).scale,4);
        final size=tester.getSize(find.byType(ChatCosmetic));
        expect(size.width,greaterThanOrEqualTo(84));expect(size.height,greaterThanOrEqualTo(58));expect(size.width,lessThanOrEqualTo(260));
      }
    });
  }
}
