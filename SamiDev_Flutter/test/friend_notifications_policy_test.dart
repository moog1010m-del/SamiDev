import 'package:flutter_test/flutter_test.dart';
import 'package:samidev/runtime/policy.dart';

void main() {
  test('private API methods stay narrow', () {
    expect(RuntimePolicy.allowApi('GET', '/api/direct/events'), isTrue);
    expect(RuntimePolicy.allowApi('GET', '/api/direct/inbox'), isTrue);
    expect(RuntimePolicy.allowApi('POST', '/api/direct/device'), isTrue);
    expect(RuntimePolicy.allowApi('POST', '/api/direct/link'), isTrue);
    expect(RuntimePolicy.allowApi('POST', '/api/direct/redeem'), isTrue);
    for (final op in ['messages', 'read', 'mute']) {
      expect(
        RuntimePolicy.allowApi('POST', '/api/direct/user_12345678/$op'),
        isTrue,
      );
    }
    expect(
      RuntimePolicy.allowApi('GET', '/api/direct/user_12345678/messages'),
      isTrue,
    );
    for (final path in [
      '/api/direct/../inbox',
      '/api/direct/%2e%2e/messages',
      '/api/direct/user_12345678/admin',
      '/api/direct/user_12345678/read',
    ]) {
      expect(RuntimePolicy.allowApi('GET', path), isFalse);
    }
    expect(
      RuntimePolicy.allowApi('DELETE', '/api/direct/user_12345678/messages'),
      isFalse,
    );
  });
}
