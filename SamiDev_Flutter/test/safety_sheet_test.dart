import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:samidev/runtime/api.dart';
import 'package:samidev/runtime/policy.dart';
import 'package:samidev/ui/safety_sheet.dart';
import 'session_test.dart' show MemoryVault;
class SafetyApi extends PlatformApi{
 SafetyApi():super(RuntimePolicy('https://example.test'),MemoryVault());
 Map<String,dynamic>? body;
 @override Future<ApiResponse> request(String method,String path,{String? query,List<int>? body})async{
  this.body=jsonDecode(utf8.decode(body!)) as Map<String,dynamic>;
  return ApiResponse(200,'application/json',Uint8List.fromList(utf8.encode(jsonEncode({'ok':true,'blocked':this.body!['block']==true}))));
 }
}
void main(){
 testWidgets('a reason is required and block accompanies a report by default',(tester)async{
  final api=SafetyApi();
  await tester.pumpWidget(MaterialApp(home:Scaffold(body:SafetySheet(api:api,userId:'profile_test_123',username:'user',roomId:'ROOM12',onUnauthorized:(){}))));
  expect(tester.widget<FilledButton>(find.widgetWithText(FilledButton,'إرسال البلاغ')).onPressed,isNull);
  await tester.tap(find.text('هذا الشخص يغش في اللعب.'));await tester.pumpAndSettle();
  await tester.tap(find.text('إرسال البلاغ'));await tester.pumpAndSettle();
  expect(api.body,{'reason':'cheating','message':'','roomId':'ROOM12','block':true});
  expect(RuntimePolicy.allowApi('POST','/api/admin/reports/report_12345678/review'),isTrue);
  expect(RuntimePolicy.allowApi('GET','/api/admin/reports/report_12345678/review'),isFalse);
  api.close();
 });
}
