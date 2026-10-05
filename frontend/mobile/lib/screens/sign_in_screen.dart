import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../state/app_scope.dart';
import '../ui/theme.dart';
import '../ui/widgets.dart';

class SignInScreen extends StatefulWidget {
  const SignInScreen({super.key});

  @override
  State<SignInScreen> createState() => _SignInScreenState();
}

class _SignInScreenState extends State<SignInScreen> {
  final _username = TextEditingController(text: 'advisor');
  final _password = TextEditingController();
  bool _busy = false;
  String? _error;

  @override
  void dispose() {
    _username.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final session = AppScope.of(context).session;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await session.signIn(_username.text.trim(), _password.text);
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _error = switch (e.status) {
            401 => "That username and password don't match.",
            404 => 'Sign-in is turned off. Set DEV_LOGIN_PASSWORD in aurelius\\.env and restart the Conductor.',
            429 => 'Too many attempts. Wait five minutes, then try again.',
            _ => e.message,
          });
    } finally {
      // After a successful sign-in this screen is already gone, so check `mounted` first.
      if (mounted) {
        _password.clear();
        setState(() => _busy = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final notice = AppScope.of(context).session.notice;
    return Scaffold(
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(24, 48, 24, 24),
          children: [
            Text('Atrium', style: serifStyle(48, height: 1)),
            const SizedBox(height: 14),
            const Text(
              'Every household you look after, prepared by the Aurelius agents before you open the file.',
              style: TextStyle(fontSize: 16, color: AppColors.ink2, height: 1.45),
            ),
            const SizedBox(height: 40),
            Text('Sign in', style: serifStyle(24, weight: FontWeight.w500)),
            const SizedBox(height: 16),
            if (notice != null) NoteBox(notice, kind: NoteKind.warn),
            TextField(
              controller: _username,
              decoration: const InputDecoration(labelText: 'Username'),
              autofillHints: const [AutofillHints.username],
              textInputAction: TextInputAction.next,
            ),
            const SizedBox(height: 14),
            TextField(
              controller: _password,
              decoration: const InputDecoration(
                labelText: 'Password',
                helperText: 'The DEV_LOGIN_PASSWORD from your .env file.',
              ),
              obscureText: true,
              autofillHints: const [AutofillHints.password],
              onSubmitted: (_) => _busy ? null : _submit(),
            ),
            const SizedBox(height: 16),
            if (_error != null) NoteBox(_error!, kind: NoteKind.error),
            Align(
              alignment: Alignment.centerLeft,
              child: FilledButton(
                onPressed: _busy ? null : _submit,
                child: Text(_busy ? 'Signing in…' : 'Sign in'),
              ),
            ),
            const SizedBox(height: 40),
            const Text(
              'Nothing reaches a client until you approve it.',
              style: TextStyle(fontSize: 13, color: AppColors.ink3),
            ),
          ],
        ),
      ),
    );
  }
}
