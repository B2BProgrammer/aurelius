/// What the Conductor returns, as Dart classes.
///
/// LEARN: JSON arrives as Map<String, dynamic>. Each class has a
/// factory that reads it defensively: a missing field becomes an empty value
/// instead of a crash, so one agent changing its output can't take the app down.
/// The shapes mirror the REAL agent outputs (see test/fixtures).
library;

typedef Json = Map<String, dynamic>;

Json _map(Object? v) => v is Map<String, dynamic> ? v : <String, dynamic>{};
List<Json> _maps(Object? v) => v is List ? v.whereType<Map<String, dynamic>>().toList() : <Json>[];
List<String> _strings(Object? v) => v is List ? v.map((e) => '$e').toList() : <String>[];
double _num(Object? v) => v is num ? v.toDouble() : 0;
int _int(Object? v) => v is num ? v.round() : 0;
String _str(Object? v) => v == null ? '' : '$v';
String? _strOrNull(Object? v) => v == null ? null : '$v';
bool _bool(Object? v) => v == true;

Map<String, double> _numMap(Object? v) =>
    _map(v).map((key, value) => MapEntry(key, _num(value)));

// ------------------------------------------------------------------ sign-in, clients
class Login {
  Login({required this.token, required this.user, required this.expiresIn});
  final String token;
  final String user;
  final int expiresIn;

  factory Login.fromJson(Json j) =>
      Login(token: _str(j['access_token']), user: _str(j['user']), expiresIn: _int(j['expires_in']));
}

class ClientSummary {
  ClientSummary({required this.clientId, required this.household});
  final String clientId;
  final String household;

  factory ClientSummary.fromJson(Json j) =>
      ClientSummary(clientId: _str(j['client_id']), household: _str(j['household']));

  /// "Patel household" -> "Patel"
  String get shortName => household.replaceAll(RegExp(r'\s+household$', caseSensitive: false), '');
}

// ------------------------------------------------------------------ overview
/// One agent's part of the overview. Each section can fail on its own.
class Section<T> {
  Section({required this.agent, required this.skill, required this.ok, this.error, required this.durationMs, this.output});
  final String agent;
  final String skill;
  final bool ok;
  final String? error;
  final int durationMs;
  final T? output;

  factory Section.fromJson(Json j, T Function(Json) parse) {
    final ok = j['status'] == 'ok';
    return Section(
      agent: _str(j['agent']),
      skill: _str(j['skill']),
      ok: ok,
      error: _strOrNull(j['error']),
      durationMs: _int(j['duration_ms']),
      output: ok ? parse(_map(j['output'])) : null,
    );
  }
}

class Overview {
  Overview({
    required this.clientId,
    required this.traceId,
    required this.generatedAt,
    required this.household,
    required this.portfolio,
    required this.kyc,
    required this.risk,
    required this.events,
    required this.meetings,
  });

  final String clientId;
  final String traceId;
  final String generatedAt;
  final Section<Household> household;
  final Section<Portfolio> portfolio;
  final Section<Kyc> kyc;
  final Section<Risk> risk;
  final Section<EventsAnswer> events;
  final Section<Meetings> meetings;

  List<Section<Object?>> get all => [household, portfolio, kyc, risk, events, meetings];

  factory Overview.fromJson(Json j) {
    final s = _map(j['sections']);
    return Overview(
      clientId: _str(j['client_id']),
      traceId: _str(j['trace_id']),
      generatedAt: _str(j['generated_at']),
      household: Section.fromJson(_map(s['household']), Household.fromJson),
      portfolio: Section.fromJson(_map(s['portfolio']), Portfolio.fromJson),
      kyc: Section.fromJson(_map(s['kyc']), Kyc.fromJson),
      risk: Section.fromJson(_map(s['risk']), Risk.fromJson),
      events: Section.fromJson(_map(s['events']), EventsAnswer.fromJson),
      meetings: Section.fromJson(_map(s['meetings']), Meetings.fromJson),
    );
  }
}

// ------------------------------------------------------------------ Liaison
class Member {
  Member(this.name, this.role, this.age);
  final String name;
  final String role;
  final int age;
}

class Task {
  Task({required this.title, required this.owner, this.due, required this.overdue});
  final String title;
  final String owner;
  final String? due;
  final bool overdue;
}

class Household {
  Household({required this.name, required this.segment, required this.members, this.nextReview, required this.openTasks});
  final String name;
  final String segment;
  final List<Member> members;
  final String? nextReview;
  final List<Task> openTasks;

  factory Household.fromJson(Json j) => Household(
        name: _str(j['household']),
        segment: _str(j['segment']),
        members: _maps(j['members']).map((m) => Member(_str(m['name']), _str(m['role']), _int(m['age']))).toList(),
        nextReview: _strOrNull(j['next_review']),
        openTasks: _maps(j['open_tasks'])
            .map((t) => Task(title: _str(t['title']), owner: _str(t['owner']), due: _strOrNull(t['due']), overdue: _bool(t['overdue'])))
            .toList(),
      );
}

// ------------------------------------------------------------------ Analyst
class TaxLossIdea {
  TaxLossIdea({required this.name, required this.loss, required this.replacements, required this.note});
  final String name;
  final double loss;
  final List<String> replacements;
  final String note;
}

class Portfolio {
  Portfolio({
    required this.totalValue,
    required this.summary,
    required this.currentPct,
    required this.targetPct,
    required this.driftPts,
    required this.needsRebalance,
    required this.concentration,
    required this.actions,
    required this.taxLossIdeas,
  });

  final double totalValue;
  final String summary;
  final Map<String, double> currentPct;
  final Map<String, double> targetPct;
  final Map<String, double> driftPts;
  final bool needsRebalance;
  final List<String> concentration;
  final List<String> actions;
  final List<TaxLossIdea> taxLossIdeas;

  factory Portfolio.fromJson(Json j) {
    final a = _map(j['allocation']);
    return Portfolio(
      totalValue: _num(j['total_value']),
      summary: _str(j['summary']),
      currentPct: _numMap(a['current_pct']),
      targetPct: _numMap(a['target_pct']),
      driftPts: _numMap(a['drift_pts']),
      needsRebalance: _bool(a['needs_rebalance']),
      concentration: _maps(j['concentration']).map((c) => _str(c['message'])).toList(),
      actions: _strings(j['actions']),
      taxLossIdeas: _maps(j['tax_loss_ideas'])
          .map((t) => TaxLossIdea(
                name: _str(t['name']),
                loss: _num(t['unrealized_loss']),
                replacements: _strings(t['replacements']),
                note: _str(t['note']),
              ))
          .toList(),
    );
  }
}

// ------------------------------------------------------------------ Notary
class KycIssue {
  KycIssue({required this.severity, required this.message, required this.fix});
  final String severity; // BLOCKER, ACTION, INFO
  final String message;
  final String fix;
}

class Kyc {
  Kyc({required this.status, required this.headline, required this.issues});
  final String status;
  final String headline;
  final List<KycIssue> issues;

  factory Kyc.fromJson(Json j) => Kyc(
        status: _str(j['status']),
        headline: _str(j['headline']),
        issues: _maps(j['issues'])
            .map((i) => KycIssue(severity: _str(i['severity']), message: _str(i['message']), fix: _str(i['fix'])))
            .toList(),
      );
}

// ------------------------------------------------------------------ Actuary
class Risk {
  Risk({
    required this.riskScore,
    required this.band,
    required this.headline,
    required this.limitingFactor,
    required this.suggestedEquityPct,
    required this.currentEquityPct,
    required this.alignment,
  });

  final int riskScore;
  final String band;
  final String headline;
  final String limitingFactor;
  final double suggestedEquityPct;
  final double currentEquityPct;
  final String alignment;

  factory Risk.fromJson(Json j) => Risk(
        riskScore: _int(j['risk_score']),
        band: _str(j['band']),
        headline: _str(j['headline']),
        limitingFactor: _str(j['limiting_factor']),
        suggestedEquityPct: _num(j['suggested_equity_pct']),
        currentEquityPct: _num(j['current_equity_pct']),
        alignment: _str(j['alignment']),
      );
}

class RetirementScenario {
  RetirementScenario({required this.retireAge, required this.probabilityPct, required this.medianAtRetirement, required this.worstCaseAge});
  final int retireAge;
  final double probabilityPct;
  final double medianAtRetirement;
  final int worstCaseAge;
}

class Retirement {
  Retirement({
    required this.headline,
    required this.alreadyRetired,
    required this.agesAreOf,
    required this.scenarios,
    required this.annualSpending,
    required this.disclosure,
  });

  final String headline;
  final bool alreadyRetired;
  final String agesAreOf;
  final List<RetirementScenario> scenarios;
  final double annualSpending;
  final String disclosure;

  factory Retirement.fromJson(Json j) => Retirement(
        headline: _str(j['headline']),
        alreadyRetired: _bool(j['already_retired']),
        agesAreOf: _str(j['ages_are_of']),
        scenarios: _maps(j['scenarios'])
            .map((s) => RetirementScenario(
                  retireAge: _int(s['retire_age']),
                  probabilityPct: _num(s['probability_of_success_pct']),
                  medianAtRetirement: _num(s['median_at_retirement']),
                  worstCaseAge: _int(s['worst_case_age_money_lasts']),
                ))
            .toList(),
        annualSpending: _num(_map(j['inputs'])['annual_spending']),
        disclosure: _str(j['disclosure']),
      );
}

// ------------------------------------------------------------------ Pulse
class MarketEvent {
  MarketEvent({
    required this.eventId,
    required this.date,
    required this.severity,
    required this.headline,
    this.match,
    this.why,
    this.estimatedImpact,
  });

  final String eventId;
  final String date;
  final String severity; // low, medium, high
  final String headline;
  final String? match; // direct, indirect
  final String? why;
  final double? estimatedImpact;

  factory MarketEvent.fromJson(Json j) => MarketEvent(
        eventId: _str(j['event_id']),
        date: _str(j['date']),
        severity: _str(j['severity']),
        headline: _str(j['headline']),
        match: _strOrNull(j['match']),
        why: _strOrNull(j['why']),
        estimatedImpact: j['estimated_impact'] is num ? (j['estimated_impact'] as num).toDouble() : null,
      );
}

class EventsAnswer {
  EventsAnswer({required this.headline, required this.events});
  final String headline;
  final List<MarketEvent> events;

  factory EventsAnswer.fromJson(Json j) =>
      EventsAnswer(headline: _str(j['headline']), events: _maps(j['events']).map(MarketEvent.fromJson).toList());
}

// ------------------------------------------------------------------ Scribe
class ActionItem {
  ActionItem(this.owner, this.task, this.due);
  final String owner;
  final String task;
  final String? due;
}

class Meetings {
  Meetings({
    required this.meetingsFound,
    this.lastMeeting,
    required this.summary,
    required this.actionItems,
    required this.concerns,
    required this.complianceFlags,
  });

  final int meetingsFound;
  final String? lastMeeting;
  final String summary;
  final List<ActionItem> actionItems;
  final List<String> concerns;
  final List<String> complianceFlags;

  factory Meetings.fromJson(Json j) => Meetings(
        meetingsFound: _int(j['meetings_found']),
        lastMeeting: _strOrNull(j['last_meeting']),
        summary: _str(j['summary']),
        actionItems: _maps(j['open_action_items'])
            .map((a) => ActionItem(_str(a['owner']), _str(a['task']), _strOrNull(a['due'])))
            .toList(),
        concerns: _strings(j['client_concerns']),
        complianceFlags: _maps(j['compliance_flags']).map((f) => _str(f['detail'])).toList(),
      );
}

// ------------------------------------------------------------------ skills, Herald, chat
class SkillResult {
  SkillResult({required this.ok, this.error, required this.output, required this.traceId});
  final bool ok;
  final String? error;
  final Json output;
  final String traceId;

  factory SkillResult.fromJson(Json j) => SkillResult(
        ok: j['status'] == 'ok',
        error: _strOrNull(j['error']),
        output: _map(j['output']),
        traceId: _str(j['trace_id']),
      );
}

class EmailDraft {
  EmailDraft({required this.subject, required this.body, required this.to, required this.warnings, required this.fixes});
  final String subject;
  final String body;
  final List<String> to;
  final List<String> warnings;
  final List<String> fixes;

  factory EmailDraft.fromJson(Json j) {
    final c = _map(j['compliance']);
    return EmailDraft(
      subject: _str(j['subject']),
      body: _str(j['body']),
      to: _strings(j['to']),
      warnings: [..._strings(c['warnings']), ..._strings(j['warnings'])],
      fixes: _strings(c['fixes']),
    );
  }
}

class Approval {
  Approval({required this.approved, this.noteId, this.nextStep, this.reason, this.revisedBody, required this.notes});
  final bool approved;
  final String? noteId;
  final String? nextStep;
  final String? reason;
  final String? revisedBody;
  final List<String> notes;

  factory Approval.fromJson(Json j) => Approval(
        approved: _bool(j['approved']),
        noteId: _strOrNull(j['note_id']),
        nextStep: _strOrNull(j['next_step']),
        reason: _strOrNull(j['reason']),
        revisedBody: _strOrNull(j['revised_body']),
        notes: _strings(j['guardrail_notes']),
      );
}

class ChatStep {
  ChatStep(this.agent, this.ok, this.durationMs);
  final String agent;
  final bool ok;
  final int durationMs;
}

class ChatAnswer {
  ChatAnswer({required this.answer, required this.steps, required this.plannedBy, required this.notes, required this.traceId});
  final String answer;
  final List<ChatStep> steps;
  final String plannedBy; // llm or rules
  final List<String> notes;
  final String traceId;

  factory ChatAnswer.fromJson(Json j) => ChatAnswer(
        answer: _str(j['answer']),
        steps: _maps(j['steps']).map((s) => ChatStep(_str(s['agent']), s['status'] == 'ok', _int(s['duration_ms']))).toList(),
        plannedBy: _str(_map(j['plan'])['source']),
        notes: _strings(j['guardrail_notes']),
        traceId: _str(j['trace_id']),
      );
}
