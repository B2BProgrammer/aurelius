import 'package:atrium_mobile/main.dart';
import 'package:atrium_mobile/state/session.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'helpers.dart';

/// LEARN: widget tests run the real screens without a phone. `pumpAndSettle`
/// lets the fake network calls finish and the animations end.
void main() {
  // A phone-sized screen, so layout problems show up here too.
  void phoneSize(WidgetTester tester) {
    tester.view.physicalSize = const Size(1170, 2532);
    tester.view.devicePixelRatio = 3;
    addTearDown(tester.view.reset);
  }

  testWidgets('signs in and lists the households', (tester) async {
    phoneSize(tester);
    final fake = FakeConductor();
    final session = Session(api: fake.api(), store: MemoryTokenStore());
    await tester.pumpWidget(AtriumApp(session: session, liveNews: false));
    await tester.pumpAndSettle();

    expect(find.text('Atrium'), findsOneWidget);
    await tester.enterText(find.widgetWithText(TextField, 'Password'), 'a-long-dev-password');
    await tester.tap(find.widgetWithText(FilledButton, 'Sign in'));
    await tester.pumpAndSettle();

    expect(find.text('Your households'), findsOneWidget);
    expect(find.text('Patel'), findsOneWidget);
    expect(find.text('Chen family'), findsOneWidget);
  });

  testWidgets('says plainly when the password is wrong', (tester) async {
    phoneSize(tester);
    final fake = FakeConductor((r) async =>
        r.url.path == '/v1/auth/login' ? jsonResponse({'detail': 'Wrong username or password'}, status: 401) : null);
    final session = Session(api: fake.api(), store: MemoryTokenStore());
    await tester.pumpWidget(AtriumApp(session: session, liveNews: false));
    await tester.pumpAndSettle();

    await tester.enterText(find.widgetWithText(TextField, 'Password'), 'nope');
    await tester.tap(find.widgetWithText(FilledButton, 'Sign in'));
    await tester.pumpAndSettle();

    expect(find.text("That username and password don't match."), findsOneWidget);
  });

  testWidgets('opens a household: needs, agents and retirement odds', (tester) async {
    phoneSize(tester);
    final fake = FakeConductor();
    final session = await fake.signedInSession();
    await tester.pumpWidget(AtriumApp(session: session, liveNews: false));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Patel'));
    await tester.pumpAndSettle();

    expect(find.text('Patel household'), findsOneWidget);
    expect(find.text('\$2.35M'), findsOneWidget);
    for (final agent in ['Liaison', 'Analyst', 'Notary', 'Actuary', 'Pulse', 'Scribe']) {
      expect(find.text(agent), findsOneWidget);
    }
    expect(find.text('Paperwork'), findsOneWidget);
    expect(find.text('Stocks are 8 points over target.'), findsOneWidget);

    await tester.scrollUntilVisible(find.text('87%'), 300, scrollable: find.byType(Scrollable).first);
    expect(find.text('87%'), findsOneWidget);
  });

  testWidgets('email: approve stays off until the placeholders are filled in', (tester) async {
    phoneSize(tester);
    final fake = FakeConductor();
    final session = await fake.signedInSession();
    await tester.pumpWidget(AtriumApp(session: session, liveNews: false));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Patel'));
    await tester.pumpAndSettle();

    await tester.scrollUntilVisible(find.text('Write to them'), 400, scrollable: find.byType(Scrollable).first);
    await tester.tap(find.text('Write to them'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Draft email'));
    await tester.pumpAndSettle();

    final approve = find.widgetWithText(FilledButton, 'Approve and log to CRM');
    expect(tester.widget<FilledButton>(approve).onPressed, isNull);
    expect(find.text('Fill in the [bracketed] placeholders first.'), findsOneWidget);

    await tester.enterText(find.widgetWithText(TextField, 'Email body'),
        'Hi Raj and Anita,\n\nBoth retirement scenarios are attached.\n\nThanks,\nSam');
    await tester.pump();
    expect(tester.widget<FilledButton>(approve).onPressed, isNotNull);

    await tester.ensureVisible(approve);
    await tester.tap(approve);
    await tester.pumpAndSettle();
    expect(find.textContaining('note N-5100'), findsOneWidget);
    expect(fake.bodyOf('/v1/drafts/approve')!['client_id'], 'patel-001');
  });
}
