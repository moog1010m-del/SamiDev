import 'package:flutter_test/flutter_test.dart';
import 'package:samidev/runtime/policy.dart';
void main(){
 test('custom community ids stay bounded and cannot inject routes',(){
  for(final value in ['majlis','coffee_room','tech-2026']){expect(RuntimePolicy.isCommunityId(value),isTrue);}
  for(final value in [null,'../admin','x/y','https://evil','UPPER','a']){expect(RuntimePolicy.isCommunityId(value),isFalse);}
 });
 test('production origin is fixed and HTTPS',(){
  expect(RuntimePolicy('https://games.example.com').backend.origin,'https://games.example.com');
  for(final value in ['http://example.com','https://user:pass@example.com','https://example.com/path','https://example.com?x=1','javascript:alert(1)','https://example.com#frag']){
   expect(()=>RuntimePolicy(value),throwsFormatException);
  }
 });
 test('local development requires explicit flag',(){
  expect(()=>RuntimePolicy('http://127.0.0.1:8088'),throwsFormatException);
  expect(RuntimePolicy('http://127.0.0.1:8088',allowLocalDevelopment:true).backend.port,8088);
 });
 test('API proxy permits only full platform routes',(){
  expect(RuntimePolicy.allowApi('PATCH','/api/profile'),isTrue);
  expect(RuntimePolicy.allowApi('GET','/api/admin/communities'),isTrue);
  expect(RuntimePolicy.allowApi('POST','/api/admin/communities'),isTrue);
  expect(RuntimePolicy.allowApi('PATCH','/api/admin/communities/new_room'),isTrue);
  expect(RuntimePolicy.allowApi('DELETE','/api/admin/communities/new_room'),isFalse);
  expect(RuntimePolicy.allowApi('POST','/api/communities/majlis/chat'),isTrue);
  expect(RuntimePolicy.allowApi('POST','/api/admin/users/user_id/ban'),isTrue);
  expect(RuntimePolicy.allowApi('GET','/api/avatar/user_id'),isTrue);
  for(final path in ['/api/unknown','/api/../admin','/api/%2e%2e/admin','https://other.example/api/me','//other.example/api/me']){
   expect(RuntimePolicy.allowApi('GET',path),isFalse);
  }
  expect(RuntimePolicy.allowApi('DELETE','/api/me'),isFalse);
  expect(RuntimePolicy.allowApi('GET','/api/admin/communities/majlis/policy'),isTrue);
  expect(RuntimePolicy.allowApi('PUT','/api/admin/communities/majlis/policy'),isTrue);
  expect(RuntimePolicy.allowApi('POST','/api/admin/communities/majlis/policy'),isFalse);
 });
 test('managed bot admin routes stay narrowly scoped',(){
  for(final method in ['GET','POST','PATCH']){expect(RuntimePolicy.allowApi(method,'/api/admin/bots'),isTrue);}
  expect(RuntimePolicy.allowApi('PATCH','/api/admin/bots/bot_id'),isTrue);
  expect(RuntimePolicy.allowApi('DELETE','/api/admin/bots/bot_id'),isFalse);
  expect(RuntimePolicy.allowApi('PATCH','/api/admin/bots/bot_id/role'),isFalse);
 });
 test('upstream path cannot choose another origin',(){
  final p=RuntimePolicy('https://games.example.com');
  expect(()=>p.upstream('//attacker.example'),throwsFormatException);
  expect(()=>p.upstream('/api/../secret'),throwsFormatException);
  expect(p.upstream('/api/me').origin,p.backend.origin);
 });
}
