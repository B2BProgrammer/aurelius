import 'dart:convert';

import 'package:atrium_mobile/api/api_client.dart';
import 'package:atrium_mobile/api/models.dart';
import 'package:atrium_mobile/api/sse.dart';
import 'package:atrium_mobile/logic/needs.dart';
import 'package:atrium_mobile/state/session.dart';
import 'package:atrium_mobile/ui/format.dart';
import 'package:flutter_test/flutter_test.dart';

import 'helpers.dart';

void main() {
  group('format', () {
    test('never says a projection is certain', () {
      expect(chance(99.8), 'over 99%');
      expect(chance(0.2), 'under 1%');
      expect(chance(87.4), '87%');
    });

    test('writes money short, long and with a real minus sign', () {
      expect(moneyShort(2350000), '\$2.35M');
      expect(moneyShort(329000), '\$329k');
      expect(money(2350000), '\$2,350,000');
      expect(signedMoney(-29610), '−\$29,610');
      expect(signedMoney(11000), '+\$11,000');
    });

    test('reads dates as calendar days', () {
      expect(day('2026-10-08'), 'Thu, Oct 8');
      expect(shortDay('2026-09-30'), 'Sep 30');
      expect(day('soon'), 'soon');
    });

    test('turns light Markdown into plain text', () {
      expect(plainText('**Briefing**\n- one\n- two'), 'Briefing\n• one\n• two');
    });
  });

  group('SSE', () {
    test('splits events, keeps names, skips pings', () {
      final msgs = parseSse('event: hello\ndata: {"a":1}\n\n: ping\n\nevent: market_event\ndata: {"event_id":"EV-1"}\n\n');
      expect(msgs, const [SseMessage('hello', '{"a":1}'), SseMessage('market_event', '{"event_id":"EV-1"}')]);
    });

    test('handles Windows line endings and events split across chunks', () async {
      final chunks = Stream<List<int>>.fromIterable([
        utf8.encode('event: market_event\r\ndata: {"event_'),
        utf8.encode('id":"EV-9"}\r\n\r\nevent: x\ndata: 2\n\n'),
      ]);
      final msgs = await sseMessages(chunks).toList();
      expect(msgs, const [SseMessage('market_event', '{"event_id":"EV-9"}'), SseMessage('x', '2')]);
    });
  });

  group('jwtExpiry', () {
    test('reads exp', () {
      final exp = jwtExpiry(fakeJwt(validFor: const Duration(hours: 2)))!;
      expect(exp.difference(DateTime.now()).inMinutes, inInclusiveRange(118, 120));
    });

    test('returns null for junk instead of throwing', () {
      expect(jwtExpiry('not-a-token'), isNull);
      expect(jwtExpiry('a.!!!.c'), isNull);
    });
  });

  group('models', () {
    test('read the real recorded overview', () {
      final o = Overview.fromJson(overviewJson);
      expect(o.household.output!.name, 'Patel household');
      expect(o.portfolio.output!.totalValue, 2350000);
      expect(o.portfolio.output!.driftPts['equity'], 8);
      expect(o.kyc.output!.issues.first.severity, 'ACTION');
      expect(o.events.output!.events.first.estimatedImpact, -29610);
      expect(o.all.length, 6);
    });

    test('a failed section has no output instead of crashing', () {
      final j = jsonDecode(jsonEncode(overviewJson)) as Map<String, dynamic>;
      (j['sections'] as Map<String, dynamic>)['events'] = {
        'agent': 'pulse',
        'skill': 'get_events',
        'status': 'error',
        'error': 'timeout',
        'duration_ms': 10000,
        'output': <String, dynamic>{},
      };
      final o = Overview.fromJson(j);
      expect(o.events.ok, isFalse);
      expect(o.events.output, isNull);
      expect(o.events.error, 'timeout');
    });
  });

  group('collectNeeds', () {
    final o = Overview.fromJson(overviewJson);

    test('puts paperwork first, then overdue tasks, market news, drift and concentration', () {
      final kinds = collectNeeds(o).map((n) => n.kind).toList();
      expect(kinds.first, 'Paperwork');
      expect(kinds, containsAll(['Overdue', 'Market', 'Rebalance', 'Concentration']));
      expect(collectNeeds(o).firstWhere((n) => n.kind == 'Rebalance').text, 'Stocks are 8 points over target.');
    });
  });

  group('ApiClient', () {
    test('sends the token and keeps the trace id on errors', () async {
      final fake = FakeConductor((r) async => r.url.path == '/v1/clients'
          ? jsonResponse({'detail': 'agent.skill is not available to the apps'}, status: 403, traceId: 'trace-xyz')
          : null);
      final api = fake.api()..token = 'tok-123';
      final err = await api.clients().then<Object?>((_) => null, onError: (Object e) => e);
      expect(err, isA<ApiException>());
      final e = err! as ApiException;
      expect(e.status, 403);
      expect(e.traceId, 'trace-xyz');
      expect(e.message, contains('not available'));
      expect(fake.calls.single.headers['Authorization'], 'Bearer tok-123');
    });

    test('a 401 signs the advisor out', () async {
      final fake = FakeConductor((r) async => jsonResponse({'detail': 'expired'}, status: 401));
      final session = await fake.signedInSession();
      expect(session.signedIn, isTrue);
      await expectLater(session.api.clients(), throwsA(isA<ApiException>()));
      await Future<void>.delayed(Duration.zero);
      expect(session.signedIn, isFalse);
      expect(session.notice, contains('expired'));
    });

    test('an expired token signs out before calling the server', () async {
      final fake = FakeConductor();
      final api = fake.api()
        ..token = 'old'
        ..tokenExpiresAt = DateTime.now().subtract(const Duration(minutes: 1));
      var signedOut = false;
      api.onUnauthorized = () => signedOut = true;
      await expectLater(api.clients(), throwsA(isA<ApiException>()));
      expect(signedOut, isTrue);
      expect(fake.calls, isEmpty);
    });
  });

  group('Session', () {
    test('signs in, saves the session, and restores it', () async {
      final fake = FakeConductor();
      final store = MemoryTokenStore();
      final s = Session(api: fake.api(), store: store);
      await s.signIn('advisor', 'a-long-dev-password');
      expect(s.signedIn, isTrue);
      expect(fake.bodyOf('/v1/auth/login'), {'username': 'advisor', 'password': 'a-long-dev-password'});
      expect(store.value, contains('advisor'));

      final again = Session(api: fake.api(), store: store);
      await again.restore();
      expect(again.signedIn, isTrue);
      expect(again.api.token, isNotNull);
    });

    test('ignores an expired saved session', () async {
      final store = MemoryTokenStore()
        ..value = jsonEncode({'token': fakeJwt(validFor: const Duration(minutes: -5)), 'user': 'advisor'});
      final s = Session(api: FakeConductor().api(), store: store);
      await s.restore();
      expect(s.signedIn, isFalse);
      expect(store.value, isNull);
    });
  });
}
