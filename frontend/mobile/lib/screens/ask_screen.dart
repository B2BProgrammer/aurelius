import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../api/models.dart';
import '../state/app_scope.dart';
import '../ui/format.dart';
import '../ui/theme.dart';
import '../ui/widgets.dart';

/// Free-form questions. The Conductor plans which agents to ask, runs them
/// in parallel and writes one answer.
class AskScreen extends StatefulWidget {
  const AskScreen({super.key, this.client});

  /// When set, questions are about this household.
  final ClientSummary? client;

  @override
  State<AskScreen> createState() => _AskScreenState();
}

const _suggestions = [
  'What does our policy say about single-stock concentration?',
  'Prepare me for the next review',
  "How exposed is this household to this week's news?",
];

class _AskScreenState extends State<AskScreen> {
  final _question = TextEditingController();
  ChatAnswer? _answer;
  Object? _error;
  bool _busy = false;

  @override
  void dispose() {
    _question.dispose();
    super.dispose();
  }

  Future<void> _ask([String? text]) async {
    final q = (text ?? _question.text).trim();
    if (q.isEmpty || _busy) return;
    _question.text = q;
    FocusScope.of(context).unfocus();
    final api = AppScope.of(context).api;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final a = await api.ask(q, clientId: widget.client?.clientId);
      if (mounted) setState(() => _answer = a);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final a = _answer;
    final about = widget.client;
    return Scaffold(
      appBar: AppBar(
        title: Text(about == null ? 'Ask Aurelius' : 'Ask about ${about.shortName}',
            style: serifStyle(22, weight: FontWeight.w500)),
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            TextField(
              controller: _question,
              maxLength: 2000,
              minLines: 1,
              maxLines: 4,
              textInputAction: TextInputAction.send,
              onSubmitted: (_) => _ask(),
              decoration: InputDecoration(
                labelText: 'Your question',
                hintText: about == null
                    ? 'About the firm’s policies or the markets'
                    : 'About ${about.shortName}, their portfolio or plans',
                counterText: '',
              ),
            ),
            const SizedBox(height: 10),
            Align(
              alignment: Alignment.centerLeft,
              child: FilledButton(onPressed: _busy ? null : _ask, child: Text(_busy ? 'Asking…' : 'Ask')),
            ),
            const SizedBox(height: 16),
            if (a == null && !_busy)
              for (final s in _suggestions)
                Align(
                  alignment: Alignment.centerLeft,
                  child: TextButton(
                    style: TextButton.styleFrom(padding: EdgeInsets.zero, alignment: Alignment.centerLeft),
                    onPressed: () => _ask(s),
                    child: Text(s, style: const TextStyle(color: AppColors.ledger, decoration: TextDecoration.underline)),
                  ),
                ),
            if (_busy) const LinearProgressIndicator(minHeight: 2, color: AppColors.ledger),
            if (_error != null) ErrorNote(error: _error, what: 'an answer'),
            if (a != null) ...[
              SelectableText(plainText(a.answer), style: serifStyle(16.5, height: 1.55)),
              const SizedBox(height: 14),
              Text(
                'Answered by ${a.steps.map((s) => '${agentLabel(s.agent)} (${s.ok ? '${s.durationMs} ms' : 'failed'})').join(', ')}. '
                'Planned by ${a.plannedBy == 'llm' ? 'the language model' : 'the fallback rules'}.',
                style: const TextStyle(fontSize: 12.5, color: AppColors.ink3),
              ),
              if (a.notes.isNotEmpty) ...[
                const SizedBox(height: 10),
                NoteBox(a.notes.join(' '), kind: NoteKind.warn),
              ],
            ],
          ],
        ),
      ),
    );
  }
}
