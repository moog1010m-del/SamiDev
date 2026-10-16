import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:samidev/runtime/api.dart';
import 'package:samidev/runtime/policy.dart';
import 'package:samidev/ui/account_settings.dart';
import 'session_test.dart' show MemoryVault;
class AccountApi extends PlatformApi {
 AccountApi():super(RuntimePolicy('https://accounts.example.test'),MemoryVault());
 final writes=<Map<String,dynamic>>[];
 @override Future<ApiResponse> request(String method,String path,{String? query,List<int>? body})async{
  expect(method,'PATCH');expect(path,'/api/profile');
  final data=jsonDecode(utf8.decode(body!)) as Map<String,dynamic>;writes.add(data);
  return ApiResponse(200,'application/json',Uint8List.fromList(utf8.encode(jsonEncode({'ok':true,'user':{'id':'guest-id','username':data['username'],'displayName':data['username'],'isGuest':true,'freeRenameAvailable':false,'renameCredits':0}}))));
 }
}
class SecurityAccountApi extends PlatformApi {
 SecurityAccountApi({this.googleOnly=false}):super(RuntimePolicy('https://accounts.example.test'),MemoryVault());
 final bool googleOnly;
 final writes=<String>[];
 ApiResponse result(Map<String,dynamic> data)=>ApiResponse(200,'application/json',Uint8List.fromList(utf8.encode(jsonEncode({'ok':true,...data}))));
 @override Future<ApiResponse> request(String method,String path,{String? query,List<int>? body})async{
  if(path=='/api/account'){return result({'email':'saved@example.test','providers':googleOnly?['google.com']:['password'],'isGuest':false});}
  if(path=='/api/account/devices'){return result({'devices':[
   {'id':'current','device':'iPhone','client':'تطبيق SamiDev','country':'SA','lastSeenAt':1700000000000,'current':true},
   if(!writes.contains('/api/account/devices/other')){'id':'other','device':'Windows','client':'Chrome','country':'','lastSeenAt':1700000000000,'current':false},
  ]});}
  if(method=='DELETE'){writes.add(path);return result({'signedOut':false});}
  throw StateError('Unexpected route: $method $path');
 }
}
void main(){
 testWidgets('single username rename requires confirmation and shows consumed free change',(tester)async{
  final api=AccountApi();addTearDown(api.close);Map<String,dynamic>? changed;
  await tester.pumpWidget(MaterialApp(home:AccountSettings(api:api,user:{'id':'guest-id','username':'Guest_123','isGuest':true,'freeRenameAvailable':true},onChanged:(u)async{changed=u;})));
  await tester.tap(find.text('الحساب'));await tester.pumpAndSettle();
  expect(find.textContaining('@Guest_'),findsNothing);
  await tester.enterText(find.byType(TextField),'New_name');
  await tester.tap(find.text('حفظ اسم المستخدم'));await tester.pumpAndSettle();
  expect(api.writes,isEmpty);
  await tester.tap(find.text('إلغاء'));await tester.pumpAndSettle();expect(api.writes,isEmpty);
  await tester.tap(find.text('حفظ اسم المستخدم'));await tester.pumpAndSettle();
  await tester.tap(find.text('تأكيد'));await tester.pumpAndSettle();
  expect(api.writes,[{'username':'New_name'}]);expect(changed?['id'],'guest-id');
  expect(find.textContaining('بطاقات تغيير الاسم: 0'),findsOneWidget);
 });
 testWidgets('invalid username cannot consume a rename',(tester)async{
  final api=AccountApi();addTearDown(api.close);
  await tester.pumpWidget(MaterialApp(home:AccountSettings(api:api,user:{'username':'Guest_123','isGuest':true,'freeRenameAvailable':true},onChanged:(u)async{})));
  await tester.tap(find.text('الحساب'));await tester.pumpAndSettle();
  await tester.enterText(find.byType(TextField),'@bad');await tester.tap(find.text('حفظ اسم المستخدم'));await tester.pumpAndSettle();
  expect(api.writes,isEmpty);expect(find.byType(AlertDialog),findsNothing);
 });
 testWidgets('saved account has security settings without sign-in form',(tester)async{
  final api=SecurityAccountApi();addTearDown(api.close);
  await tester.pumpWidget(MaterialApp(home:AccountSettings(api:api,user:{'id':'saved','username':'Saved_player','isGuest':false},onChanged:(u)async{})));
  expect(find.text('الأجهزة'),findsOneWidget);expect(find.text('الخصوصية'),findsOneWidget);
  await tester.tap(find.text('الحساب'));await tester.pumpAndSettle();
  expect(find.text('ربط الحساب أو تسجيل الدخول'),findsNothing);
  expect(find.text('saved@example.test'),findsOneWidget);
  expect(find.text('تغيير كلمة المرور عبر البريد'),findsOneWidget);
  expect(find.text('حذف الحساب نهائيًا'),findsOneWidget);
 });
 testWidgets('Google account explains external password management',(tester)async{
  final api=SecurityAccountApi(googleOnly:true);addTearDown(api.close);
  await tester.pumpWidget(MaterialApp(home:AccountSettings(api:api,user:{'id':'saved','username':'Saved_player','isGuest':false},onChanged:(u)async{})));
  await tester.tap(find.text('الحساب'));await tester.pumpAndSettle();
  expect(find.text('تغيير كلمة المرور عبر البريد'),findsNothing);
  expect(find.text('تُدار كلمة مرور Google من حسابك لدى Google.'),findsOneWidget);
 });
 testWidgets('cancelling account deletion keeps account and performs no mutation',(tester)async{
  final api=SecurityAccountApi();addTearDown(api.close);
  await tester.pumpWidget(MaterialApp(home:AccountSettings(api:api,user:{'id':'saved','username':'Saved_player','isGuest':false},onChanged:(u)async{fail('cancel must not switch accounts');})));
  await tester.tap(find.text('الحساب'));await tester.pumpAndSettle();
  await tester.ensureVisible(find.text('حذف الحساب نهائيًا'));await tester.tap(find.text('حذف الحساب نهائيًا'));await tester.pumpAndSettle();
  await tester.enterText(find.widgetWithText(TextField,'كلمة المرور الحالية'),'Never-sent-password');
  await tester.tap(find.text('إلغاء'));await tester.pumpAndSettle();
  expect(find.byType(AlertDialog),findsNothing);expect(api.writes,isEmpty);expect(find.text('saved@example.test'),findsOneWidget);
  expect(tester.takeException(),isNull);
 });
 testWidgets('device revocation requires confirmation and refreshes real list',(tester)async{
  final api=SecurityAccountApi();addTearDown(api.close);
  await tester.pumpWidget(MaterialApp(home:AccountDevices(api:api,onSignedOut:()async{fail('other device must not sign out current device');})));
  await tester.pumpAndSettle();
  expect(find.text('iPhone · هذا الجهاز'),findsOneWidget);expect(find.text('Windows'),findsOneWidget);
  await tester.tap(find.byTooltip('تسجيل الخروج').last);await tester.pumpAndSettle();
  expect(api.writes,isEmpty);await tester.tap(find.text('إلغاء'));await tester.pumpAndSettle();expect(api.writes,isEmpty);
  await tester.tap(find.byTooltip('تسجيل الخروج').last);await tester.pumpAndSettle();await tester.tap(find.text('تأكيد'));await tester.pumpAndSettle();
  expect(api.writes,['/api/account/devices/other']);expect(find.text('Windows'),findsNothing);expect(find.text('iPhone · هذا الجهاز'),findsOneWidget);
 });
}
