import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../api/models.dart';
import '../state/app_scope.dart';
import '../ui/theme.dart';
import '../ui/widgets.dart';

/// Human in the loop: Herald drafts, the advisor edits, Sentinel checks it again,
/// and only an explicit approval writes a note to the CRM. Atrium never sends email.
class EmailScreen extends StatefulWidget {
  const EmailScreen({super.key, required this.client});
  final ClientSummary client;

  @override
  State<EmailScreen> createState() => _EmailScreenState();
}

final _placeholder = RegExp(r'\[[^\]]+\]');

class _EmailScreenState extends State<EmailScreen> {
  final _purpose = TextEditingController(text: 'Follow up on our last meeting');
  final _points = TextEditingController();
  final _subject = TextEditingController();
  final _body = TextEditingController();

  EmailDraft? _draft;
  Approval? _approval;
  bool _busy = false;
  Object? _error;

  @override
  void initState() {
    super.initState();
    // Rebuild as the advisor types, so the placeholder check stays current.
    _body.addListener(_edited);
    _subject.addListener(_edited);
  }

  @override
  void dispose() {
    for (final c in [_purpose, _points, _subject, _body]) {
      c.dispose();
    }
    super.dispose();
  }

  void _edited() {
    if (!mounted) return;
    setState(() {
      if (_approval?.approved == true) return; // keep the confirmation visible
      _approval = null;
    });
  }

  Future<void> _run(Future<void> Function(ApiClient api) task) async {
    final api = AppScope.of(context).api;
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await task(api);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _makeDraft() => _run((api) async {
        final res = await api.skill('herald', 'draft_email', {
          'client_id': widget.client.clientId,
          'purpose': _purpose.text.trim(),
          'points': _points.text.split('\n').map((p) => p.trim()).where((p) => p.isNotEmpty).toList(),
        });
        if (!mounted) return;
        if (!res.ok) {
          setState(() => _error = ApiException("Herald couldn't draft it: ${res.error}", status: 200));
          return;
        }
        final d = EmailDraft.fromJson(res.output);
        _subject.text = d.subject;
        _body.text = d.body;
        setState(() {
          _draft = d;
          _approval = null;
        });
      });

  Future<void> _approve() => _run((api) async {
        final a = await api.approveDraft(
            clientId: widget.client.clientId, subject: _subject.text, body: _body.text);
        if (!mounted) return;
        setState(() => _approval = a);
        if (!a.approved && a.revisedBody != null) {
          _body.text = a.revisedBody!;
          setState(() => _approval = a); // the listener cleared it; show the reason again
        }
      });

  void _startOver() => setState(() {
        _draft = null;
        _approval = null;
        _error = null;
        _subject.clear();
        _body.clear();
      });

  @override
  Widget build(BuildContext context) {
    final d = _draft;
    return Scaffold(
      appBar: AppBar(title: Text('Write to ${widget.client.shortName}', style: serifStyle(20, weight: FontWeight.w500))),
      body: SafeArea(
        // A form, so build all of it at once (a lazy ListView can drop fields that scroll away).
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: d == null ? _askForDraft() : _editDraft(d),
          ),
        ),
      ),
    );
  }

  List<Widget> _askForDraft() => [
        TextField(controller: _purpose, decoration: const InputDecoration(labelText: "What's the email for?")),
        const SizedBox(height: 14),
        TextField(
          controller: _points,
          minLines: 3,
          maxLines: 6,
          decoration: const InputDecoration(
            labelText: 'Points to include, one per line',
            helperText: 'Herald adds open tasks and the review date from the CRM.',
          ),
        ),
        const SizedBox(height: 16),
        if (_error != null) ErrorNote(error: _error, what: 'a draft'),
        Align(
          alignment: Alignment.centerLeft,
          child: FilledButton(onPressed: _busy ? null : _makeDraft, child: Text(_busy ? 'Drafting…' : 'Draft email')),
        ),
      ];

  List<Widget> _editDraft(EmailDraft d) {
    final hasPlaceholder = _placeholder.hasMatch(_body.text) || _placeholder.hasMatch(_subject.text);
    final approved = _approval?.approved == true;
    // Herald's warnings describe its first draft; drop the placeholder one once it's filled in.
    final warnings = d.warnings.where((w) => hasPlaceholder || !w.toLowerCase().contains('placeholder'));
    return [
      if (d.fixes.isNotEmpty)
        NoteBox("Herald's compliance check changed the draft (${d.fixes.join(', ')}). Read it before approving.",
            kind: NoteKind.warn),
      for (final w in warnings) NoteBox(w, kind: NoteKind.warn),
      Text('To ${d.to.join(', ')}', style: const TextStyle(fontSize: 13, color: AppColors.ink3)),
      const SizedBox(height: 10),
      TextField(
        controller: _subject,
        enabled: !approved,
        style: serifStyle(18, weight: FontWeight.w500),
        decoration: const InputDecoration(labelText: 'Subject'),
      ),
      const SizedBox(height: 12),
      TextField(
        controller: _body,
        enabled: !approved,
        minLines: 10,
        maxLines: null,
        keyboardType: TextInputType.multiline,
        style: serifStyle(16, height: 1.5),
        decoration: const InputDecoration(labelText: 'Email body', alignLabelWithHint: true),
      ),
      const SizedBox(height: 14),
      if (_error != null) ErrorNote(error: _error, what: 'the approval'),
      if (approved)
        NoteBox('Approved and logged to the CRM as note ${_approval!.noteId}. ${_approval!.nextStep ?? ''}',
            kind: NoteKind.ok),
      if (_approval != null && !approved)
        NoteBox('${_approval!.reason ?? 'Not approved.'} ${_approval!.notes.join(' ')}', kind: NoteKind.error),
      if (hasPlaceholder && !approved)
        const Padding(
          padding: EdgeInsets.only(bottom: 8),
          child: Text('Fill in the [bracketed] placeholders first.', style: TextStyle(fontSize: 13, color: AppColors.ink3)),
        ),
      Wrap(
        spacing: 10,
        runSpacing: 10,
        children: [
          FilledButton(
            onPressed: _busy || approved || hasPlaceholder ? null : _approve,
            child: Text(_busy ? 'Checking…' : approved ? 'Approved' : 'Approve and log to CRM'),
          ),
          OutlinedButton(onPressed: _busy ? null : _startOver, child: const Text('Start over')),
        ],
      ),
    ];
  }
}
