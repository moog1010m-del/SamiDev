import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/services.dart';

import 'api.dart';

/// Created only inside the adult/social application, never the children's path.
/// FCM initialization additionally requires a deliberate notification opt-in.
class FriendNotifications {
  FriendNotifications(
    this.api,
    this.accountId, {
    required this.onMessage,
    required this.onOpen,
    this.onUpdate,
    this.onRequests,
    this.onGameOpen,
  });
  final PlatformApi api;
  final String accountId;
  final void Function(Map<String, dynamic>) onMessage;
  final void Function(String) onOpen;
  final void Function()? onUpdate;
  final void Function()? onRequests;
  final void Function(String)? onGameOpen;
  StreamSubscription<Map<String, dynamic>>? _events;
  StreamSubscription<RemoteMessage>? _opened;
  StreamSubscription<String>? _tokens;
  Timer? _retry;
  bool _closed = false,
      _background = false,
      _checking = false,
      _again = false,
      _ready = false;
  int _epoch = 0, _streamEpoch = 0;
  final _seen = <String>{};
  String? _device;
  String get _preference =>
      'plazr.push.${api.policy.backend.origin}.$accountId';
  Future<void> start() async {
    await refresh(notify: false);
    if (_closed) return;
    connect();
    if (await api.vault.read(_preference) == 'enabled') {
      try {
        await enable(requestPermission: false);
      } catch (_) {}
    }
  }

  void connect() {
    if (_closed || _background || !api.signedIn || _events != null) return;
    final streamEpoch = ++_streamEpoch;
    _events = api
        .events('/api/direct/events')
        .listen(
          (event) {
            if (_closed || streamEpoch != _streamEpoch) return;
            if (event['type'] == 'access_denied') {
              stop();
              return;
            }
            unawaited(refresh());
          },
          onError: (_) {
            if (streamEpoch == _streamEpoch) reconnect();
          },
          onDone: () {
            if (streamEpoch == _streamEpoch) reconnect();
          },
        );
  }

  void reconnect() {
    final old = _events;
    _streamEpoch++;
    _events = null;
    unawaited(old?.cancel());
    _retry?.cancel();
    if (!_closed && !_background) {
      _retry = Timer(const Duration(seconds: 5), connect);
    }
  }

  Future<void> refresh({bool notify = true}) async {
    if (_closed || _background || !api.signedIn) return;
    if (_checking) {
      _again = true;
      return;
    }
    _checking = true;
    try {
      final r = await api.request('GET', '/api/direct/inbox');
      if (_closed || r.status != 200) return;
      for (final value in r.json['threads'] as List? ?? []) {
        final t = Map<String, dynamic>.from(value as Map);
        final m = t['lastMessage'] as Map?;
        if (m == null) continue;
        final id = m['id']?.toString() ?? '';
        if (notify &&
            !_seen.contains(id) &&
            m['senderId'] != accountId &&
            t['muted'] != true &&
            (t['unread'] as num? ?? 0) > 0) {
          onMessage(t);
        }
        _seen.add(id);
      }
      onUpdate?.call();
      while (_seen.length > 500) {
        _seen.remove(_seen.first);
      }
    } catch (_) {
    } finally {
      _checking = false;
      if (_again) {
        _again = false;
        unawaited(refresh());
      }
    }
  }

  Future<String> enable({bool requestPermission = true}) async {
    if (_closed || !api.signedIn) return 'سجّل الدخول أولًا';
    if (!Platform.isAndroid && !Platform.isIOS) {
      return 'إشعارات الهاتف متاحة على Android وiOS';
    }
    final epoch = _epoch;
    final response = await api.request('GET', '/api/direct/inbox');
    final config = response.json['pushConfig'] as Map?;
    final options = config?[Platform.isIOS ? 'ios' : 'android'] as Map?;
    if (response.status != 200 ||
        response.json['pushEnabled'] != true ||
        options == null) {
      return 'إشعارات الهاتف لم تُفعّل على الخادم بعد';
    }
    if (_closed || epoch != _epoch) return '';
    if (Platform.isAndroid) {
      final native = await const MethodChannel('plazr/notifications')
          .invokeMapMethod<String, String>('configuration');
      if (native?['projectId'] != options['projectId'] ||
          native?['appId'] != options['appId']) {
        return 'هذه النسخة تحتاج بناء بإعدادات Firebase للإشعارات؛ تواصل مع الدعم';
      }
    }
    if (Firebase.apps.isEmpty) {
      await Firebase.initializeApp(
        options: FirebaseOptions(
          apiKey: options['apiKey'] as String,
          appId: options['appId'] as String,
          messagingSenderId: options['messagingSenderId'] as String,
          projectId: options['projectId'] as String,
          iosBundleId: options['iosBundleId'] as String?,
        ),
      );
    }
    if (_closed || epoch != _epoch) return '';
    if (Firebase.app().options.projectId != options['projectId']) {
      throw StateError('مشروع إشعارات الهاتف لا يطابق إعداد الخادم');
    }
    final messaging = FirebaseMessaging.instance;
    final permission = requestPermission
        ? await messaging.requestPermission(
            alert: true,
            badge: true,
            sound: true,
          )
        : await messaging.getNotificationSettings();
    if (permission.authorizationStatus != AuthorizationStatus.authorized &&
        permission.authorizationStatus != AuthorizationStatus.provisional) {
      return 'اسمح بالإشعارات من إعدادات الهاتف';
    }
    if (_closed || epoch != _epoch) return '';
    if (Platform.isAndroid) {
      await const MethodChannel('plazr/notifications')
          .invokeMethod<void>('createChannel');
    }
    await messaging.setForegroundNotificationPresentationOptions(
      alert: false,
      badge: true,
      sound: false,
    );
    _device = await api.vault.read('plazr.push.device');
    _device ??= List.generate(
      32,
      (_) =>
          'abcdefghijklmnopqrstuvwxyz0123456789'[Random.secure().nextInt(36)],
    ).join();
    await api.vault.write('plazr.push.device', _device);
    final registered = Completer<void>();
    await _tokens?.cancel();
    _tokens = messaging.onRegistered.listen((fid) async {
      try {
        await register(fid);
        if (!registered.isCompleted) registered.complete();
      } catch (e) {
        if (!registered.isCompleted) registered.completeError(e);
      }
    });
    await messaging.setAutoInitEnabled(true);
    if (_closed || epoch != _epoch) {
      await messaging.setAutoInitEnabled(false);
      return '';
    }
    await messaging.register();
    await registered.future.timeout(const Duration(seconds: 20));
    if (_closed || epoch != _epoch) return '';
    await api.vault.write(_preference, 'enabled');
    await _opened?.cancel();
    _opened = FirebaseMessaging.onMessageOpenedApp.listen(openMessage);
    _ready = true;
    final initial = await messaging.getInitialMessage();
    if (initial != null) openMessage(initial);
    return 'تم تفعيل إشعارات الرسائل والمباريات';
  }

  Future<void> register(String? token) async {
    if (_closed || !api.signedIn || _device == null) return;
    final r = await api.request(
      'POST',
      '/api/direct/device',
      body: utf8.encode(jsonEncode({'deviceId': _device, 'fid': token})),
    );
    if (r.status != 200) throw StateError('تعذر تسجيل جهاز الإشعارات');
  }

  void openMessage(RemoteMessage message) {
    if (_closed ||
        !api.signedIn ||
        message.data['accountId'] != accountId ||
        !{'direct', 'friend_request', 'game_started', 'game_turn'}.contains(message.data['type'])) {
      return;
    }
    if ({'game_started', 'game_turn'}.contains(message.data['type'])) {
      final room = message.data['roomId'];
      if (room != null && RegExp(r'^[A-Za-z0-9_-]{4,32}$').hasMatch(room)) onGameOpen?.call(room);
      return;
    }
    if (message.data['type'] == 'friend_request') {
      onRequests?.call();
      return;
    }
    final id = message.data['peerId'];
    if (id != null && RegExp(r'^[A-Za-z0-9_-]{12,32}$').hasMatch(id)) {
      onOpen(id);
    }
  }

  Future<String> disable() async {
    await api.vault.write(_preference, null);
    _device ??= await api.vault.read('plazr.push.device');
    try {
      await register(null);
    } finally {
      if (_ready || Firebase.apps.isNotEmpty) {
        await FirebaseMessaging.instance.setAutoInitEnabled(false);
        await FirebaseMessaging.instance.unregister();
      }
      _ready = false;
      await _tokens?.cancel();
      _tokens = null;
      await _opened?.cancel();
      _opened = null;
    }
    return 'تم إيقاف إشعارات الهاتف لهذا الحساب';
  }

  Future<void> background(bool value) async {
    _background = value;
    if (value) {
      _retry?.cancel();
      final old = _events;
      _streamEpoch++;
      _events = null;
      unawaited(old?.cancel());
    } else {
      connect();
      await refresh();
    }
  }

  Future<void> stop() async {
    _closed = true;
    _epoch++;
    _retry?.cancel();
    final old = _events;
    _streamEpoch++;
    _events = null;
    unawaited(old?.cancel());
    await _opened?.cancel();
    await _tokens?.cancel();
    _seen.clear();
  }
}
