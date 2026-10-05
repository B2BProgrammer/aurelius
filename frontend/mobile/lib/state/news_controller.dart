/// Keeps the live news stream open and holds the latest events.
///
/// LEARN: the stream can drop at any time (server restart, Wi-Fi change, the
/// 30-minute limit). We reconnect with "exponential backoff": wait 1s, 2s, 4s…
/// up to 30s, so a server that's down isn't hammered.
library;

import 'dart:async';

import 'package:flutter/foundation.dart';

import '../api/api_client.dart';
import '../api/models.dart';

enum NewsStatus { off, connecting, live, offline }

class NewsController extends ChangeNotifier {
  NewsController(this._api, {this.enabled = true});

  final ApiClient _api;
  final bool enabled;

  final List<MarketEvent> events = [];
  NewsStatus status = NewsStatus.off;
  int unseen = 0;

  StreamSubscription<MarketEvent>? _sub;
  Timer? _retry;
  Duration _delay = const Duration(seconds: 1);
  bool _disposed = false;

  /// On the web, Flutter's http client waits for the whole response before
  /// handing it over, and a news stream never ends. So live news is mobile-only.
  bool get supported => !kIsWeb;

  void start() {
    if (!enabled || !supported || _disposed) return;
    _setStatus(NewsStatus.connecting);
    _sub = _api.marketEvents(onConnected: () {
      _delay = const Duration(seconds: 1);
      _setStatus(NewsStatus.live);
    }).listen(
      (e) {
        events.removeWhere((x) => x.eventId == e.eventId);
        events.insert(0, e);
        if (events.length > 30) events.removeLast();
        unseen++;
        notifyListeners();
      },
      onError: (Object _) => _scheduleRetry(),
      onDone: _scheduleRetry,
      cancelOnError: true,
    );
  }

  void markSeen() {
    if (unseen == 0) return;
    unseen = 0;
    notifyListeners();
  }

  void _scheduleRetry() {
    if (_disposed) return;
    _sub = null;
    _setStatus(NewsStatus.offline);
    _retry?.cancel();
    _retry = Timer(_delay, start);
    final next = _delay * 2;
    _delay = next > const Duration(seconds: 30) ? const Duration(seconds: 30) : next;
  }

  void _setStatus(NewsStatus s) {
    if (status == s) return;
    status = s;
    notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    _retry?.cancel();
    _sub?.cancel();
    super.dispose();
  }
}
