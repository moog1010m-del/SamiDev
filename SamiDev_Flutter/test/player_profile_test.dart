import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:samidev/runtime/api.dart';
import 'package:samidev/runtime/policy.dart';
import 'package:samidev/ui/player_profile.dart';
import 'package:samidev/ui/profile_details.dart';
import 'session_test.dart' show MemoryVault;

class ProfileApi extends PlatformApi {
  ProfileApi():super(RuntimePolicy('https://profile.example.test'),MemoryVault());
  final calls=<String>[];
  final user=<String,dynamic>{'id':'profile_test_123','username':'test','displayName':'لاعب الاختبار','hasAvatar':false,
    'starsCount':1,'wins':17,'reputation':6,'accountAgeDays':23,'relation':'none','reputationDailyRemaining':4,'reputationGrantedToday':false};
  @override Future<ApiResponse> request(String method,String path,{String? query,List<int>? body}) async {
    calls.add('$method $path');
    if(path=='/api/friends/request'){expect(jsonDecode(utf8.decode(body!))['username'],'test');user['relation']='outgoing';}
    return ApiResponse(200,'application/json',Uint8List.fromList(utf8.encode(jsonEncode({'ok':true,'user':user}))));
  }
}
void main(){
  for(final brightness in Brightness.values){
    testWidgets('public card on a small phone in $brightness uses real data and API actions',(tester)async{
      tester.view.physicalSize=const Size(360,640);tester.view.devicePixelRatio=1;
      addTearDown(tester.view.resetPhysicalSize);addTearDown(tester.view.resetDevicePixelRatio);
      final api=ProfileApi();addTearDown(api.close);
      await tester.pumpWidget(MaterialApp(theme:ThemeData(brightness:brightness),home:Builder(builder:(context)=>Scaffold(body:TextButton(
        onPressed:()=>showPlayerProfile(context,api:api,id:'profile_test_123',onUnauthorized:(){}),child:const Text('افتح البطاقة'))))));
      await tester.tap(find.text('افتح البطاقة'));await tester.pumpAndSettle();
      expect(find.text('لاعب الاختبار'),findsOneWidget);expect(find.text('17'),findsOneWidget);expect(find.text('6'),findsOneWidget);
      expect(find.byType(ProfileStars),findsOneWidget);expect(find.byWidgetPredicate((widget)=>widget is ProfileDecoration&&widget.name=='star'),findsOneWidget);expect(find.byType(PlayerAvatar),findsOneWidget);
      await tester.ensureVisible(find.text('إضافة صديق'));await tester.tap(find.text('إضافة صديق'));await tester.pumpAndSettle();
      expect(api.calls,contains('POST /api/friends/request'));expect(find.text('تم إرسال الطلب'),findsOneWidget);
      expect(find.byType(ProfileDetails),findsNothing);
      await tester.ensureVisible(find.text('الملف الكامل والمقتنيات والإحصاءات'));
      await tester.tap(find.text('الملف الكامل والمقتنيات والإحصاءات'));await tester.pumpAndSettle();
      expect(find.byType(ProfileDetails),findsOneWidget);
      await tester.ensureVisible(find.byTooltip('العودة إلى البطاقة المختصرة'));
      await tester.tap(find.byTooltip('العودة إلى البطاقة المختصرة'));await tester.pumpAndSettle();
      expect(find.byType(ProfileDetails),findsNothing);
      expect(tester.takeException(),isNull);
      await tester.ensureVisible(find.byTooltip('إغلاق'));await tester.tap(find.byTooltip('إغلاق'));await tester.pumpAndSettle();
      expect(find.byType(PlayerProfileSheet),findsNothing);
    });
  }
}
