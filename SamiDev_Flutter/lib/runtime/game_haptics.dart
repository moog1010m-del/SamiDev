import 'dart:async';

import 'package:flutter/services.dart';

/// Short, bounded feedback from the owned game document; never a physics timer.
class GameHaptics {
  GameHaptics({Future<void> Function(double)? impact})
    : _impact = impact ?? _nativeImpact;
  final Future<void> Function(double) _impact;
  final List<Timer> _timers = [];
  final Stopwatch _clock = Stopwatch()..start();
  int _lastStart = -1000;
  bool _disposed = false;

  static Future<void> _nativeImpact(double strength) {
    if (strength < .35) return HapticFeedback.selectionClick();
    if (strength < .7) return HapticFeedback.lightImpact();
    if (strength < .9) return HapticFeedback.mediumImpact();
    return HapticFeedback.heavyImpact();
  }

  void cancel() {
    for (final timer in _timers) {
      timer.cancel();
    }
    _timers.clear();
  }

  void dispose() {
    _disposed = true;
    cancel();
  }

  void play(Map message) {
    if (_disposed) return;
    if (message['action'] == 'cancel') {
      cancel();
      return;
    }
    final amplitudes = message['amplitudes'], durations = message['durations'];
    if (amplitudes is! List ||
        durations is! List ||
        amplitudes.isEmpty ||
        amplitudes.length > 16 ||
        amplitudes.length != durations.length) {
      return;
    }
    final pulses = <(double, int)>[];
    int total = 0;
    for (int i = 0; i < amplitudes.length; i++) {
      final amplitude = amplitudes[i], duration = durations[i];
      if (amplitude is! num ||
          duration is! num ||
          !amplitude.isFinite ||
          !duration.isFinite ||
          amplitude < 0 ||
          amplitude > 1 ||
          duration < 0 ||
          duration > 500) {
        return;
      }
      final ms = duration.round();
      total += ms;
      if (total > 2000) return;
      pulses.add((amplitude.toDouble(), ms));
    }
    if (!pulses.any((p) => p.$1 > 0 && p.$2 > 0) ||
        _clock.elapsedMilliseconds - _lastStart < 45) {
      return;
    }
    _lastStart = _clock.elapsedMilliseconds;
    cancel();
    int offset = 0;
    for (final pulse in pulses) {
      if (pulse.$1 > 0 && pulse.$2 > 0) {
        void fire() {
          if (!_disposed) {
            unawaited(_impact(pulse.$1).catchError((Object _) {}));
          }
        }

        if (offset == 0) {
          fire();
        } else {
          _timers.add(Timer(Duration(milliseconds: offset), fire));
        }
      }
      offset += pulse.$2;
    }
  }
}
