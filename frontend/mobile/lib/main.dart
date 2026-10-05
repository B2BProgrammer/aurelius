import 'package:flutter/material.dart';

import 'api/api_client.dart';
import 'config.dart';
import 'screens/home_shell.dart';
import 'screens/sign_in_screen.dart';
import 'state/app_scope.dart';
import 'state/session.dart';
import 'ui/theme.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  final api = ApiClient(baseUrl: AppConfig.conductorUrl);
  final session = Session(api: api, store: SecureTokenStore());
  runApp(AtriumApp(session: session));
}

/// The root widget.
///
/// LEARN: `liveNews` is a switch so tests can turn the never-ending news stream off.
class AtriumApp extends StatefulWidget {
  const AtriumApp({super.key, required this.session, this.liveNews = true});
  final Session session;
  final bool liveNews;

  @override
  State<AtriumApp> createState() => _AtriumAppState();
}

class _AtriumAppState extends State<AtriumApp> {
  late final Future<void> _restored = widget.session.restore();
  final _navigator = GlobalKey<NavigatorState>();

  // When the session ends (sign-out, expired token, 401) close any open screens,
  // so the sign-in page is what the advisor sees, not a stale household.
  void _onSessionChanged() {
    if (!widget.session.signedIn) _navigator.currentState?.popUntil((route) => route.isFirst);
  }

  @override
  void initState() {
    super.initState();
    widget.session.addListener(_onSessionChanged);
  }

  @override
  void dispose() {
    widget.session.removeListener(_onSessionChanged);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AppScope(
      session: widget.session,
      child: MaterialApp(
        navigatorKey: _navigator,
        title: 'Atrium',
        debugShowCheckedModeBanner: false,
        theme: buildTheme(),
        home: FutureBuilder<void>(
          future: _restored,
          builder: (context, snapshot) {
            if (snapshot.connectionState != ConnectionState.done) {
              return const Scaffold(body: Center(child: CircularProgressIndicator()));
            }
            // Rebuilds whenever the session changes: signed in -> home, signed out -> sign-in.
            return ListenableBuilder(
              listenable: widget.session,
              builder: (context, _) => widget.session.signedIn
                  ? HomeShell(liveNews: widget.liveNews)
                  : const SignInScreen(),
            );
          },
        ),
      ),
    );
  }
}
