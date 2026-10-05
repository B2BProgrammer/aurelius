import 'package:flutter/widgets.dart';

import '../api/api_client.dart';
import 'session.dart';

/// Makes the session (and through it, the API client) reachable from any screen:
///   final api = AppScope.of(context).api;
///
/// LEARN: an InheritedWidget is Flutter's built-in way to pass something down the
/// widget tree without handing it through every constructor. Packages like
/// Provider and Riverpod are built on the same idea.
class AppScope extends InheritedWidget {
  const AppScope({super.key, required this.session, required super.child});

  final Session session;

  ApiClient get api => session.api;

  static AppScope of(BuildContext context) {
    final scope = context.dependOnInheritedWidgetOfExactType<AppScope>();
    assert(scope != null, 'AppScope is missing above this widget');
    return scope!;
  }

  @override
  bool updateShouldNotify(AppScope oldWidget) => session != oldWidget.session;
}
