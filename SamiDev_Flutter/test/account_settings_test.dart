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
void main(){
 testWidgets('single username rename requires confirmation and shows consumed free change',(tester)async{
  final api=AccountApi();addTearDown(api.close);Map<String,dynamic>? changed;
  await tester.pumpWidget(MaterialApp(home:AccountSettings(api:api,user:{'id':'guest-id','username':'Guest_123','isGuest':true,'freeRenameAvailable':true},onChanged:(u)async{changed=u;})));
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
  await tester.enterText(find.byType(TextField),'@bad');await tester.tap(find.text('حفظ اسم المستخدم'));await tester.pumpAndSettle();
  expect(api.writes,isEmpty);expect(find.byType(AlertDialog),findsNothing);
 });
}
