import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:samidev/runtime/api.dart';
import 'package:samidev/runtime/policy.dart';
import 'package:samidev/runtime/friend_notifications.dart';

class MemoryVault implements SessionVault {
  final values = <String, String>{};
  @override
  Future<String?> read(String key) async => values[key];
  @override
  Future<void> write(String key, String? value) async {
    if (value == null) {
      values.remove(key);
    } else {
      values[key] = value;
    }
  }
}

class NotificationApi extends PlatformApi {
  NotificationApi()
    : super(RuntimePolicy('https://example.test'), MemoryVault());
  final updates = StreamController<Map<String, dynamic>>.broadcast();
  List<Map<String, dynamic>> threads = [];
  @override
  bool get signedIn => true;
  @override
  Future<ApiResponse> request(
    String method,
    String path, {
    String? query,
    List<int>? body,
  }) async => ApiResponse(
    200,
    'application/json',
    Uint8List.fromList(
      utf8.encode(jsonEncode({'ok': true, 'threads': threads})),
    ),
  );
  @override
  Stream<Map<String, dynamic>> events(String path) => updates.stream;
}

void main() {
  test('table push taps are restricted to the active account and valid room', () async {
    final api = NotificationApi(), opened = <String>[];
    final service = FriendNotifications(api, 'owner', onMessage: (_) {}, onOpen: (_) {}, onGameOpen: opened.add);
    service.openMessage(const RemoteMessage(data: {'type':'game_turn','accountId':'other','roomId':'ABC123'}));
    service.openMessage(const RemoteMessage(data: {'type':'game_started','accountId':'owner','roomId':'../bad'}));
    expect(opened, isEmpty);
    service.openMessage(const RemoteMessage(data: {'type':'game_started','accountId':'owner','roomId':'ABC123'}));
    service.openMessage(const RemoteMessage(data: {'type':'game_turn','accountId':'owner','roomId':'ABC123'}));
    expect(opened, ['ABC123','ABC123']);
    await service.stop();
    service.openMessage(const RemoteMessage(data: {'type':'game_turn','accountId':'owner','roomId':'ABC123'}));
    expect(opened.length, 2);
    await api.updates.close(); api.close();
  });
  test('foreground notifications suppress history, duplicates, muted and stopped accounts', () async {
    final api = NotificationApi(), seen = <String>[];
    Map<String, dynamic> thread(String id, {bool muted = false}) => {
      'user': {'id': 'peer'},
      'lastMessage': {'id': id, 'senderId': 'peer'},
      'unread': 1,
      'muted': muted,
    };
    api.threads = [thread('old')];
    final service = FriendNotifications(
      api,
      'owner',
      onMessage: (t) => seen.add((t['lastMessage'] as Map)['id'] as String),
      onOpen: (_) {},
    );
    await service.start();
    expect(seen, isEmpty);
    api.threads = [thread('new')];
    await service.refresh();
    await service.refresh();
    expect(seen, ['new']);
    api.threads = [thread('muted', muted: true)];
    await service.refresh();
    expect(seen, ['new']);
    await service.background(true);
    api.threads = [thread('background')];
    await service.refresh();
    expect(seen, ['new']);
    await service.background(false);
    expect(seen, ['new', 'background']);
    await service.stop();
    api.threads = [thread('wrong-account')];
    await service.refresh();
    expect(seen, ['new', 'background']);
    await api.updates.close();
    api.close();
  });
}
