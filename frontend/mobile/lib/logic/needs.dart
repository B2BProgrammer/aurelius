/// What the advisor must act on, pulled out of six agents' answers, most urgent first.
/// A plain function with no widgets, so it's easy to unit-test. Same rules as the web app.
library;

import '../api/models.dart';
import '../ui/format.dart';

class Need {
  const Need(this.kind, this.text, {this.detail, this.blocker = false});
  final String kind;
  final String text;
  final String? detail;
  final bool blocker;
}

List<Need> collectNeeds(Overview o) {
  final needs = <Need>[];

  final kyc = o.kyc.output;
  if (kyc != null) {
    for (final i in kyc.issues.where((i) => i.severity == 'BLOCKER')) {
      needs.add(Need('Blocker', i.message, detail: i.fix, blocker: true));
    }
    for (final i in kyc.issues.where((i) => i.severity == 'ACTION')) {
      needs.add(Need('Paperwork', i.message, detail: i.fix));
    }
  }

  final household = o.household.output;
  if (household != null) {
    for (final t in household.openTasks.where((t) => t.overdue && t.owner == 'advisor')) {
      needs.add(Need('Overdue', t.title, detail: t.due == null ? null : 'Was due ${day(t.due!)}'));
    }
  }

  final events = o.events.output;
  if (events != null) {
    for (final e in events.events.where((e) => e.severity == 'high' && e.match == 'direct')) {
      final impact = e.estimatedImpact;
      needs.add(Need('Market', e.headline,
          detail: impact == null ? e.why : 'About ${signedMoney(impact)} for this household'));
    }
  }

  final p = o.portfolio.output;
  if (p != null) {
    if (p.needsRebalance) {
      final eq = p.driftPts['equity'] ?? 0;
      needs.add(Need(
        'Rebalance',
        'Stocks are ${_pts(eq.abs())} points ${eq > 0 ? 'over' : 'under'} target.',
        detail: p.actions.isEmpty ? null : p.actions.first,
      ));
    }
    for (final c in p.concentration) {
      needs.add(Need('Concentration', c));
    }
  }

  final risk = o.risk.output;
  if (risk != null && risk.alignment.isNotEmpty && risk.alignment != 'aligned') {
    needs.add(Need('Risk', risk.headline));
  }
  return needs;
}

/// 8.0 -> "8", 7.5 -> "7.5"
String _pts(double v) => v == v.roundToDouble() ? v.round().toString() : v.toStringAsFixed(1);
