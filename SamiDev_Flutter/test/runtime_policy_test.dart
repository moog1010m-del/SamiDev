import 'package:flutter_test/flutter_test.dart';
import 'package:samidev/runtime/policy.dart';
void main(){
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
  expect(RuntimePolicy.allowApi('POST','/api/communities/majlis/chat'),isTrue);
  expect(RuntimePolicy.allowApi('POST','/api/admin/users/user_id/ban'),isTrue);
  expect(RuntimePolicy.allowApi('GET','/api/avatar/user_id'),isTrue);
  for(final path in ['/api/unknown','/api/../admin','/api/%2e%2e/admin','https://other.example/api/me','//other.example/api/me']){
   expect(RuntimePolicy.allowApi('GET',path),isFalse);
  }
  expect(RuntimePolicy.allowApi('DELETE','/api/me'),isFalse);
 });
 test('upstream path cannot choose another origin',(){
  final p=RuntimePolicy('https://games.example.com');
  expect(()=>p.upstream('//attacker.example'),throwsFormatException);
  expect(()=>p.upstream('/api/../secret'),throwsFormatException);
  expect(p.upstream('/api/me').origin,p.backend.origin);
 });
}
