import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../api/models.dart';
import '../logic/needs.dart';
import '../state/app_scope.dart';
import '../ui/format.dart';
import '../ui/theme.dart';
import '../ui/widgets.dart';
import 'ask_screen.dart';
import 'email_screen.dart';

/// One household's file, top to bottom, like the web dossier but one column.
class HouseholdScreen extends StatefulWidget {
  const HouseholdScreen({super.key, required this.client});
  final ClientSummary client;

  @override
  State<HouseholdScreen> createState() => _HouseholdScreenState();
}

class _HouseholdScreenState extends State<HouseholdScreen> {
  Future<Overview>? _overview;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _overview ??= AppScope.of(context).api.overview(widget.client.clientId);
  }

  Future<void> _refresh() async {
    final next = AppScope.of(context).api.overview(widget.client.clientId);
    setState(() => _overview = next);
    await next;
  }

  @override
  Widget build(BuildContext context) {
    final c = widget.client;
    return Scaffold(
      appBar: AppBar(
        title: Text(c.shortName, style: serifStyle(20, weight: FontWeight.w500)),
        actions: [
          IconButton(
            tooltip: 'Ask about this household',
            icon: const Icon(Icons.chat_bubble_outline),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(builder: (_) => AskScreen(client: c)),
            ),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: FutureBuilder<Overview>(
          future: _overview,
          builder: (context, snap) {
            if (snap.connectionState != ConnectionState.done) {
              return ListView(children: const [LoadingLines(label: 'Asking six agents for this file…')]);
            }
            final error = snap.error;
            if (error != null) {
              final notFound = error is ApiException && error.status == 404;
              return ListView(padding: const EdgeInsets.all(20), children: [
                notFound
                    ? NoteBox("There's no household with the id ${c.clientId}.", kind: NoteKind.error)
                    : ErrorNote(error: error, what: 'this household'),
              ]);
            }
            return _Dossier(overview: snap.data!, client: c);
          },
        ),
      ),
    );
  }
}

class _Dossier extends StatelessWidget {
  const _Dossier({required this.overview, required this.client});
  final Overview overview;
  final ClientSummary client;

  @override
  Widget build(BuildContext context) {
    final o = overview;
    final h = o.household.output;
    final p = o.portfolio.output;
    return ListView(
      children: [
        // ---------------------------------------------------------- header
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(h?.name ?? client.household, style: serifStyle(32, height: 1.1)),
              if (h != null) ...[
                const SizedBox(height: 6),
                Text(
                  '${h.members.map((m) => '${m.name}, ${m.age}').join(' and ')}. ${h.segment}.'
                  '${h.nextReview != null ? ' Next review ${day(h.nextReview!)}.' : ''}',
                  style: const TextStyle(color: AppColors.ink2, height: 1.4),
                ),
              ],
              if (p != null) ...[
                const SizedBox(height: 14),
                Text(moneyShort(p.totalValue), style: serifStyle(34, height: 1)),
                const Text('under management', style: TextStyle(fontSize: 13, color: AppColors.ink3)),
              ],
            ],
          ),
        ),
        const Divider(color: AppColors.ink, thickness: 1, indent: 20, endIndent: 20),
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 10, 20, 10),
          child: AgentStrip(sections: o.all),
        ),
        const Divider(indent: 20, endIndent: 20),

        // ---------------------------------------------------------- sections
        DossierSection(title: 'Needs you', child: _NeedsList(needs: collectNeeds(o))),
        const Divider(indent: 20, endIndent: 20),
        DossierSection(
          title: 'Portfolio',
          by: 'Analyst and Actuary',
          child: p == null ? AgentDown(o.portfolio) : _PortfolioBody(p: p, risk: o.risk.output),
        ),
        const Divider(indent: 20, endIndent: 20),
        DossierSection(title: 'Retirement', by: 'Actuary', child: RetirementPanel(clientId: client.clientId)),
        const Divider(indent: 20, endIndent: 20),
        DossierSection(
          title: 'Market',
          by: 'Pulse',
          child: o.events.output == null ? AgentDown(o.events) : _EventsList(events: o.events.output!.events),
        ),
        const Divider(indent: 20, endIndent: 20),
        DossierSection(
          title: 'Meetings',
          by: 'Scribe',
          child: o.meetings.output == null ? AgentDown(o.meetings) : _MeetingsBody(m: o.meetings.output!),
        ),
        const Divider(indent: 20, endIndent: 20),
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 24, 20, 8),
          child: FilledButton.icon(
            icon: const Icon(Icons.edit_outlined, size: 18),
            label: const Text('Write to them'),
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute<void>(builder: (_) => EmailScreen(client: client)),
            ),
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 12, 20, 32),
          child: SelectableText('Trace ${o.traceId}. All households are fictional.',
              style: const TextStyle(fontSize: 11, color: AppColors.ink3)),
        ),
      ],
    );
  }
}

class _NeedsList extends StatelessWidget {
  const _NeedsList({required this.needs});
  final List<Need> needs;

  @override
  Widget build(BuildContext context) {
    if (needs.isEmpty) {
      return const Text('Nothing needs you today. The file is in order.', style: TextStyle(color: AppColors.ledger));
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final n in needs)
          Padding(
            padding: const EdgeInsets.only(bottom: 14),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(n.kind,
                    style: TextStyle(
                        fontSize: 12.5,
                        fontWeight: FontWeight.w600,
                        color: n.blocker ? AppColors.blocker : AppColors.brass)),
                const SizedBox(height: 2),
                Text(n.text, style: const TextStyle(fontSize: 15, height: 1.4)),
                if (n.detail != null)
                  Text(n.detail!, style: const TextStyle(fontSize: 13, color: AppColors.ink3, height: 1.4)),
              ],
            ),
          ),
      ],
    );
  }
}

class _PortfolioBody extends StatelessWidget {
  const _PortfolioBody({required this.p, required this.risk});
  final Portfolio p;
  final Risk? risk;

  @override
  Widget build(BuildContext context) {
    final r = risk;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(p.summary, style: serifStyle(17, height: 1.45)),
        const SizedBox(height: 16),
        for (final cls in const ['equity', 'fixed_income', 'cash']) _AllocationRow(p: p, cls: cls),
        const Padding(
          padding: EdgeInsets.only(top: 4, bottom: 12),
          child: Text('Thick bar: now. Thin bar: target.', style: TextStyle(fontSize: 12, color: AppColors.ink3)),
        ),
        if (r != null)
          Text(
            'Risk score ${r.riskScore} of 100, ${r.band.toLowerCase()}, set by '
            '${r.limitingFactor == 'capacity' ? 'their capacity to take losses' : 'their stated willingness'}. '
            'The profile suggests about ${r.suggestedEquityPct.round()}% in stocks; they hold ${r.currentEquityPct.round()}%.',
            style: const TextStyle(color: AppColors.ink2, height: 1.45),
          ),
        for (final t in p.taxLossIdeas) ...[
          const SizedBox(height: 14),
          Text('Tax-loss idea: ${t.name}', style: const TextStyle(fontWeight: FontWeight.w600)),
          Text('${money(-t.loss.abs())} unrealized. Could swap to ${t.replacements.join(', ')}.',
              style: const TextStyle(color: AppColors.ink2)),
        ],
      ],
    );
  }
}

class _AllocationRow extends StatelessWidget {
  const _AllocationRow({required this.p, required this.cls});
  final Portfolio p;
  final String cls;

  @override
  Widget build(BuildContext context) {
    final now = p.currentPct[cls] ?? 0;
    final target = p.targetPct[cls] ?? 0;
    final drift = p.driftPts[cls] ?? 0;
    final off = drift.abs() >= 5;
    final label = classLabel[cls] ?? cls;
    return Semantics(
      label: '$label: ${now.round()}% now, target ${target.round()}%',
      excludeSemantics: true,
      child: Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: Row(
          children: [
            SizedBox(width: 56, child: Text(label)),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  FractionallySizedBox(
                    widthFactor: (now / 100).clamp(0.0, 1.0),
                    child: Container(height: 7, color: AppColors.ledger),
                  ),
                  const SizedBox(height: 3),
                  FractionallySizedBox(
                    widthFactor: (target / 100).clamp(0.0, 1.0),
                    child: Container(height: 3, color: AppColors.ink3.withValues(alpha: 0.5)),
                  ),
                ],
              ),
            ),
            SizedBox(
              width: 92,
              child: Text.rich(
                TextSpan(children: [
                  TextSpan(text: '${now.round()}% '),
                  TextSpan(
                    text: drift == 0 ? 'on target' : '${drift > 0 ? '+' : '−'}${drift.abs().round()} pts',
                    style: TextStyle(
                        fontSize: 12,
                        color: off ? AppColors.attention : AppColors.ink3,
                        fontWeight: off ? FontWeight.w600 : FontWeight.w400),
                  ),
                ]),
                textAlign: TextAlign.right,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Retirement odds from the Actuary (Java). Tap ages to compare up to three.
class RetirementPanel extends StatefulWidget {
  const RetirementPanel({super.key, required this.clientId});
  final String clientId;

  @override
  State<RetirementPanel> createState() => _RetirementPanelState();
}

class _RetirementPanelState extends State<RetirementPanel> {
  List<int> _ages = const [];
  Future<SkillResult>? _result;
  Retirement? _last;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _result ??= _load();
  }

  Future<SkillResult> _load() => AppScope.of(context).api.skill('actuary', 'project_retirement', {
        'client_id': widget.clientId,
        if (_ages.isNotEmpty) 'retire_ages': _ages,
      });

  void _toggle(int age, List<int> selected) {
    final next = selected.contains(age) ? selected.where((a) => a != age).toList() : ([...selected, age]..sort());
    if (next.isEmpty || next.length > 3) return;
    setState(() {
      _ages = next;
      _result = _load();
    });
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<SkillResult>(
      future: _result,
      builder: (context, snap) {
        final loading = snap.connectionState != ConnectionState.done;
        if (snap.hasError) return ErrorNote(error: snap.error, what: 'the retirement projection');
        final data = snap.data;
        if (!loading && data != null && !data.ok) {
          return NoteBox("Actuary couldn't run it: ${data.error}", kind: NoteKind.error);
        }
        if (!loading && data != null) _last = Retirement.fromJson(data.output);
        final r = _last;
        if (r == null) return const LinearProgressIndicator(minHeight: 2, color: AppColors.ledger);

        final shown = r.scenarios.map((s) => s.retireAge).toList();
        final selected = _ages.isNotEmpty ? _ages : shown;
        final planned = shown.isEmpty ? 65 : shown.first;
        final candidates = r.alreadyRetired
            ? <int>[]
            : [for (var a = planned - 1; a <= planned + 3; a++) if (a >= 50 && a <= 80) a];

        return Opacity(
          opacity: loading ? 0.55 : 1,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(r.headline, style: serifStyle(17, height: 1.45)),
              if (candidates.isNotEmpty) ...[
                const SizedBox(height: 14),
                Text('Retirement age for ${r.agesAreOf}', style: const TextStyle(fontSize: 13, color: AppColors.ink3)),
                const SizedBox(height: 6),
                Wrap(
                  spacing: 6,
                  children: [
                    for (final a in candidates)
                      FilterChip(
                        label: Text('$a'),
                        selected: selected.contains(a),
                        showCheckmark: false,
                        selectedColor: AppColors.ink,
                        labelStyle: TextStyle(color: selected.contains(a) ? AppColors.paper : AppColors.ink),
                        onSelected: loading ? null : (_) => _toggle(a, selected),
                      ),
                  ],
                ),
              ],
              const SizedBox(height: 16),
              Wrap(
                spacing: 28,
                runSpacing: 16,
                children: [
                  for (final s in r.scenarios)
                    SizedBox(
                      width: 140,
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(chance(s.probabilityPct),
                              style: serifStyle(36,
                                  height: 1, color: s.probabilityPct < 80 ? AppColors.attention : AppColors.ink)),
                          const SizedBox(height: 4),
                          Text(
                            'chance the money lasts, retiring at ${s.retireAge}. '
                            '${moneyShort(s.medianAtRetirement)} expected then; in a bad run it lasts to ${s.worstCaseAge}.',
                            style: const TextStyle(fontSize: 12.5, color: AppColors.ink3, height: 1.35),
                          ),
                        ],
                      ),
                    ),
                ],
              ),
              const SizedBox(height: 14),
              Text(r.disclosure, style: const TextStyle(fontSize: 11.5, color: AppColors.ink3)),
            ],
          ),
        );
      },
    );
  }
}

class _EventsList extends StatelessWidget {
  const _EventsList({required this.events});
  final List<MarketEvent> events;

  @override
  Widget build(BuildContext context) {
    if (events.isEmpty) {
      return const Text('No market news in the last two weeks touches this portfolio.',
          style: TextStyle(color: AppColors.ink2));
    }
    return Column(children: [for (final e in events) EventRow(event: e)]);
  }
}

/// One market event: date, severity dot, headline, why it matters, money impact.
class EventRow extends StatelessWidget {
  const EventRow({super.key, required this.event});
  final MarketEvent event;

  @override
  Widget build(BuildContext context) {
    final impact = event.estimatedImpact;
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(padding: const EdgeInsets.only(top: 6), child: Dot(severityColor(event.severity))),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${shortDay(event.date)}${event.severity == 'high' ? ', high severity' : ''}'
                  '${impact != null && impact != 0 ? '  ${signedMoney(impact)}' : ''}',
                  style: TextStyle(
                    fontSize: 12.5,
                    color: impact != null && impact < 0 ? AppColors.blocker : AppColors.ink3,
                  ),
                ),
                Text(event.headline, style: const TextStyle(fontSize: 15, height: 1.35)),
                if (event.why != null)
                  Text(event.why!, style: const TextStyle(fontSize: 12.5, color: AppColors.ink3, height: 1.35)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _MeetingsBody extends StatelessWidget {
  const _MeetingsBody({required this.m});
  final Meetings m;

  @override
  Widget build(BuildContext context) {
    if (m.meetingsFound == 0) {
      return const Text('No meeting notes on file yet.', style: TextStyle(color: AppColors.ink2));
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(m.summary, style: serifStyle(17, height: 1.45)),
        if (m.lastMeeting != null)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text('Last meeting ${day(m.lastMeeting!)}', style: const TextStyle(fontSize: 12.5, color: AppColors.ink3)),
          ),
        const SizedBox(height: 14),
        const Text('Promised in the meeting', style: TextStyle(fontWeight: FontWeight.w600, color: AppColors.ink2)),
        const SizedBox(height: 4),
        for (final a in m.actionItems)
          Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Text(
              '• ${a.task} (${a.owner == 'advisor' ? 'you' : a.owner}${a.due != null ? ', by ${shortDay(a.due!)}' : ''})',
              style: const TextStyle(color: AppColors.ink2, height: 1.4),
            ),
          ),
        if (m.concerns.isNotEmpty) ...[
          const SizedBox(height: 10),
          const Text("What's on their mind", style: TextStyle(fontWeight: FontWeight.w600, color: AppColors.ink2)),
          const SizedBox(height: 4),
          for (final c in m.concerns)
            Padding(
              padding: const EdgeInsets.only(bottom: 4),
              child: Text('• $c', style: const TextStyle(color: AppColors.ink2, height: 1.4)),
            ),
        ],
        if (m.complianceFlags.isNotEmpty) ...[
          const SizedBox(height: 10),
          NoteBox('Compliance: ${m.complianceFlags.join(' ')}', kind: NoteKind.warn),
        ],
      ],
    );
  }
}
