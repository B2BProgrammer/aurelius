import 'package:flutter/foundation.dart';

/// Where the Conductor is.
///
/// LEARN: each place the app runs sees your computer at a different address.
///  - Android emulator: 10.0.2.2 is the emulator's name for YOUR computer.
///  - Chrome / Windows / iOS simulator: 127.0.0.1 (same machine).
///  - A real phone on Wi-Fi: your computer's LAN address, passed at run time:
///      flutter run --dart-define=CONDUCTOR_URL=http://192.168.1.20:8000
class AppConfig {
  static const String _fromCommandLine = String.fromEnvironment('CONDUCTOR_URL');

  static String get conductorUrl {
    if (_fromCommandLine.isNotEmpty) return _fromCommandLine;
    if (!kIsWeb && defaultTargetPlatform == TargetPlatform.android) {
      return 'http://10.0.2.2:8000';
    }
    return 'http://127.0.0.1:8000';
  }
}
