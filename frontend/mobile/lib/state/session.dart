/// Sign-in state for the whole app.
///
/// LEARN:
///  - The token is saved with flutter_secure_storage: the Android Keystore or the
///    iOS Keychain, encrypted by the phone. Never in plain SharedPreferences.
///  - We read the token's expiry ("exp") and sign out once it passes, or on any 401.
///  - Session is a ChangeNotifier: when it changes, the widgets listening to it
///    rebuild (signed in -> home, signed out -> sign-in screen).
library;

import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../api/api_client.dart';

/// Where the session is kept. An interface, so tests can use memory instead.
abstract class TokenStore {
  Future<String?> read();
  Future<void> write(String value);
  Future<void> clear();
}

class SecureTokenStore implements TokenStore {
  static const _key = 'atrium.session';
  final _storage = const FlutterSecureStorage();

  @override
  Future<String?> read() => _storage.read(key: _key);

  @override
  Future<void> write(String value) => _storage.write(key: _key, value: value);

  @override
  Future<void> clear() => _storage.delete(key: _key);
}

class MemoryTokenStore implements TokenStore {
  String? value;

  @override
  Future<String?> read() async => value;

  @override
  Future<void> write(String v) async {
    value = v;
  }

  @override
  Future<void> clear() async {
    value = null;
  }
}

/// Reads "exp" from a JWT. Display only: the SERVER checks the signature.
DateTime? jwtExpiry(String token) {
  try {
    final parts = token.split('.');
    if (parts.length < 2) return null;
    final payload = jsonDecode(utf8.decode(base64Url.decode(base64Url.normalize(parts[1]))));
    final exp = payload is Map ? payload['exp'] : null;
    return exp is num ? DateTime.fromMillisecondsSinceEpoch(exp.toInt() * 1000) : null;
  } on FormatException {
    return null;
  }
}

class Session extends ChangeNotifier {
  Session({required this.api, required this.store}) {
    api.onUnauthorized = () => signOut('Your sign-in expired. Sign in again.');
  }

  final ApiClient api;
  final TokenStore store;

  String? user;
  String? notice;

  bool get signedIn => user != null;

  /// On app start: pick up a saved session if it's still valid.
  Future<void> restore() async {
    try {
      final raw = await store.read();
      if (raw == null) return;
      final saved = jsonDecode(raw) as Map<String, dynamic>;
      final token = saved['token'] as String;
      final exp = jwtExpiry(token);
      if (exp == null || exp.isBefore(DateTime.now().add(const Duration(seconds: 5)))) {
        await store.clear();
        return;
      }
      _apply(token, saved['user'] as String, exp);
    } catch (_) {
      // unreadable or from an older version: start signed out
      await store.clear();
    }
  }

  Future<void> signIn(String username, String password) async {
    final login = await api.login(username, password);
    final exp = jwtExpiry(login.token) ?? DateTime.now().add(Duration(seconds: login.expiresIn));
    await store.write(jsonEncode({'token': login.token, 'user': login.user}));
    notice = null;
    _apply(login.token, login.user, exp);
  }

  Future<void> signOut([String? reason]) async {
    if (user == null && reason == null) return;
    api.token = null;
    api.tokenExpiresAt = null;
    user = null;
    notice = reason;
    await store.clear();
    notifyListeners();
  }

  void _apply(String token, String name, DateTime expiresAt) {
    api.token = token;
    api.tokenExpiresAt = expiresAt;
    user = name;
    notifyListeners();
  }
}
