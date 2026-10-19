import 'package:flutter/foundation.dart';

class RuntimePolicy {
  static bool isCommunityId(String? value) => value != null && RegExp(r'^[a-z][a-z0-9_-]{1,31}$').hasMatch(value);
  RuntimePolicy(String value, {bool allowLocalDevelopment = false}) {
    final uri = Uri.tryParse(value);
    if (uri == null || !uri.hasAuthority || uri.userInfo.isNotEmpty ||
        uri.hasQuery || uri.hasFragment || (uri.path.isNotEmpty && uri.path != '/')) {
      throw const FormatException('يجب ضبط عنوان خادم المنصة فقط');
    }
    final local = !kReleaseMode && allowLocalDevelopment &&
        {'127.0.0.1', 'localhost', '10.0.2.2'}.contains(uri.host);
    if (uri.scheme != 'https' && !(local && uri.scheme == 'http')) {
      throw const FormatException('اتصال HTTPS مطلوب');
    }
    backend = uri.replace(path: '');
  }
  late final Uri backend;
  static const entries = {'/platform/', '/platform/index.html', '/index.html',
    '/games/carrom/index.html', '/games/crazy8/index.html',
    '/games/pool/index.html', '/games/tablesoccer/index.html'};
  static bool isGame(String path) => entries.contains(path) && !path.startsWith('/platform');
  static bool allowApi(String method, String path) {
    if (path.contains('%') || path.contains('..') || path.contains('\\')) return false;
    const get = {'/api/direct/inbox','/api/direct/events','/api/account','/api/account/devices','/api/auth/config','/api/me','/api/games','/api/build','/api/store','/api/communities',
      '/api/lobby/rooms','/api/friends','/api/users/search','/api/admin/users',
      '/api/admin/stats','/api/admin/reports','/api/admin/bots','/api/admin/communities'};
    const post = {'/api/direct/link','/api/direct/redeem','/api/direct/device','/api/admin/communities','/api/admin/bots','/api/account/logout-all','/api/account/delete','/api/auth/guest','/api/store/buy','/api/auth/firebase','/api/auth/login','/api/auth/register','/api/auth/logout',
      '/api/store/equip','/api/heartbeat','/api/game-ticket','/api/friends/request','/api/friends/respond'};
    if (method == 'GET' && get.contains(path)) return true;
    if (method == 'POST' && post.contains(path)) return true;
    if (method == 'PATCH' && path == '/api/profile') return true;
    const id = r'[A-Za-z0-9_-]{1,64}';
    return switch (method) {
      'PATCH' => path == '/api/admin/bots' || RegExp('^/api/admin/bots/$id\$').hasMatch(path) || RegExp('^/api/admin/communities/$id\$').hasMatch(path),
      'PUT' => RegExp('^/api/admin/communities/$id/policy\$').hasMatch(path),
      'GET' => RegExp('^/api/direct/$id/messages\$').hasMatch(path)||RegExp('^/api/admin/communities/$id/policy\$').hasMatch(path)||RegExp('^/api/(avatar|public-profile|communities)/$id\$').hasMatch(path)||RegExp('^/api/communities/$id/events\$').hasMatch(path),
      'POST' => RegExp('^/api/direct/$id/(messages|read|mute)\$').hasMatch(path)||RegExp('^/api/(communities/$id/(enter|leave|chat|moderation)|users/$id/(reputation|report|block)|admin/users/$id/(ban|role))\$').hasMatch(path),
      'DELETE' => RegExp('^/api/(friends|account/devices)/$id\$').hasMatch(path),
      _ => false,
    };
  }
  Uri upstream(String path, [String? query]) {
    if (!path.startsWith('/') || path.startsWith('//') || path.contains('..') || path.contains('\\')) {
      throw const FormatException('Invalid route');
    }
    return backend.replace(path: path, query: query?.isEmpty == true ? null : query);
  }
}
