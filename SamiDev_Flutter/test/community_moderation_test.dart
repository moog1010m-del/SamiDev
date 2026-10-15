import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:samidev/runtime/api.dart';
import 'package:samidev/ui/player_profile.dart';
import 'player_profile_test.dart' show ProfileApi;

class ModerationApi extends ProfileApi {
  ModerationApi(this.allowed);
  final bool allowed;
  Map<String,dynamic>? command;
  @override Future<ApiResponse> request(String method,String path,{String? query,List<int>? body}) async {
    if(path=='/api/communities/majlis')return ApiResponse(200,'application/json',Uint8List.fromList(utf8.encode(jsonEncode({'ok':true,'capabilities':{'canModerate':allowed,'canAssignModerators':false}}))));
    if(path=='/api/communities/majlis/moderation'){
      command=jsonDecode(utf8.decode(body!));
      return ApiResponse(200,'application/json',Uint8List.fromList(utf8.encode('{"ok":true}')));
    }
    return super.request(method,path,query:query,body:body);
  }
}
void main(){
  for(final allowed in [false,true]){testWidgets('native scoped moderation, permission=$allowed, requires confirmation',(tester)async{
    tester.view.physicalSize=const Size(390,844);tester.view.devicePixelRatio=1;
    addTearDown(tester.view.resetPhysicalSize);addTearDown(tester.view.resetDevicePixelRatio);
    final api=ModerationApi(allowed);addTearDown(api.close);
    await tester.pumpWidget(MaterialApp(home:Builder(builder:(context)=>Scaffold(body:TextButton(
      onPressed:()=>showPlayerProfile(context,api:api,id:'profile_test_123',communityId:'majlis',onUnauthorized:(){}),child:const Text('افتح'))))));
    await tester.tap(find.text('افتح'));await tester.pumpAndSettle();
    final control=find.text('إدارة العضو في المساحة');
    if(!allowed){expect(control,findsNothing);return;}
    await tester.ensureVisible(control);await tester.tap(control);await tester.pumpAndSettle();
    expect(find.text('تعيين مشرف للمساحة'),findsNothing);
    await tester.tap(find.text('كتم ١٠ دقائق'));await tester.pumpAndSettle();
    expect(api.command,isNull);await tester.tap(find.text('إلغاء'));await tester.pumpAndSettle();expect(api.command,isNull);
    await tester.ensureVisible(control);await tester.tap(control);await tester.pumpAndSettle();
    await tester.tap(find.text('كتم ١٠ دقائق'));await tester.pumpAndSettle();
    await tester.tap(find.text('تأكيد'));await tester.pumpAndSettle();
    expect(api.command,{'targetUserId':'profile_test_123','action':'mute'});expect(tester.takeException(),isNull);
  });}
}
