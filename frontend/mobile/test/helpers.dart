/// Test helpers: a fake Conductor that answers from REAL recorded agent outputs.
///
/// LEARN: package:http ships MockClient. We hand it to ApiClient instead of the
/// real network client, so every test runs offline and in milliseconds.
library;

import 'dart:convert';
import 'dart:io';

import 'package:atrium_mobile/api/api_client.dart';
import 'package:atrium_mobile/state/session.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

Map<String, dynamic> readFixture(String name) =>
    jsonDecode(File('test/fixtures/$name').readAsStringSync()) as Map<String, dynamic>;

final overviewJson = readFixture('overview-patel.json');
final skillsJson = readFixture('skills-patel.json');

http.Response jsonResponse(Object body, {int status = 200, String traceId = 'trace-test-1'}) => http.Response(
      jsonEncode(body),
      status,
      headers: {'content-type': 'application/json; charset=utf-8', 'x-trace-id': traceId},
    );

/// A JWT with only "sub" and "exp": enough for the app to read the expiry.
String fakeJwt({Duration validFor = const Duration(hours: 1)}) {
  String b64(Map<String, Object> m) => base64Url.encode(utf8.encode(jsonEncode(m))).replaceAll('=', '');
  final exp = DateTime.now().add(validFor).millisecondsSinceEpoch ~/ 1000;
  return '${b64({'alg': 'HS256'})}.${b64({'sub': 'advisor', 'exp': exp})}.sig';
}

Map<String, Object?> _skill(String agent, String name, Object? output) => {
      'agent': agent,
      'skill': name,
      'status': 'ok',
      'error': null,
      'trace_id': 'trace-test-1',
      'duration_ms': 20,
      'output': output,
      'guardrail_notes': <String>[],
    };

typedef FakeRoute = Future<http.Response?> Function(http.Request request);

/// Records every call so tests can check what the app sent.
class FakeConductor {
  FakeConductor([this.override]);
  final FakeRoute? override;
  final List<http.Request> calls = [];

  Map<String, dynamic>? bodyOf(String path) {
    final r = calls.lastWhere((c) => c.url.path == path);
    return r.body.isEmpty ? null : jsonDecode(r.body) as Map<String, dynamic>;
  }

  late final MockClient client = MockClient((request) async {
    calls.add(request);
    final custom = override == null ? null : await override!(request);
    if (custom != null) return custom;
    switch (request.url.path) {
      case '/v1/auth/login':
        return jsonResponse({'access_token': fakeJwt(), 'token_type': 'bearer', 'expires_in': 3600, 'user': 'advisor'});
      case '/v1/clients':
        return jsonResponse([
          {'client_id': 'patel-001', 'household': 'Patel household'},
          {'client_id': 'chen-002', 'household': 'Chen family'},
        ]);
      case '/v1/clients/patel-001/overview':
        return jsonResponse(overviewJson);
      case '/v1/skills/actuary/project_retirement':
        return jsonResponse(_skill('actuary', 'project_retirement', skillsJson['actuary.project_retirement']));
      case '/v1/skills/herald/draft_email':
        return jsonResponse(_skill('herald', 'draft_email', skillsJson['herald.draft_email']));
      case '/v1/drafts/approve':
        return jsonResponse({
          'approved': true,
          'note_id': 'N-5100',
          'next_step': 'Send it from your own mailbox.',
          'guardrail_notes': <String>[],
        });
    }
    if (request.url.path.startsWith('/v1/clients/')) {
      return jsonResponse({'detail': "No household with id 'x'"}, status: 404);
    }
    return jsonResponse({'detail': 'Not Found'}, status: 404);
  });

  ApiClient api() => ApiClient(baseUrl: 'http://conductor.test', client: client);

  /// A session that's already signed in (as if restored from the keystore).
  Future<Session> signedInSession() async {
    final store = MemoryTokenStore()..value = jsonEncode({'token': fakeJwt(), 'user': 'advisor'});
    final s = Session(api: api(), store: store);
    await s.restore();
    return s;
  }
}
