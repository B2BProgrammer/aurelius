/// Small building blocks shared by the screens.
library;

import 'package:flutter/material.dart';

import '../api/api_client.dart';
import '../api/models.dart';
import '../ui/format.dart';
import 'theme.dart';

/// A dossier section: its name (and which agent it came from), then the content.
class DossierSection extends StatelessWidget {
  const DossierSection({super.key, required this.title, this.by, required this.child});
  final String title;
  final String? by;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 24, 20, 24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Semantics(
            header: true,
            child: Text(title, style: serifStyle(19, weight: FontWeight.w500, color: AppColors.ink2)),
          ),
          if (by != null)
            Padding(
              padding: const EdgeInsets.only(top: 2),
              child: Text('from $by', style: const TextStyle(fontSize: 12, color: AppColors.ink3)),
            ),
          const SizedBox(height: 14),
          child,
        ],
      ),
    );
  }
}

enum NoteKind { info, ok, warn, error }

/// A note with a coloured rule on the left: errors, warnings, confirmations.
class NoteBox extends StatelessWidget {
  const NoteBox(this.text, {super.key, this.kind = NoteKind.info, this.traceId});
  final String text;
  final NoteKind kind;
  final String? traceId;

  @override
  Widget build(BuildContext context) {
    final color = switch (kind) {
      NoteKind.ok => AppColors.ledger,
      NoteKind.warn => AppColors.attention,
      NoteKind.error => AppColors.blocker,
      NoteKind.info => AppColors.ink3,
    };
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
      decoration: BoxDecoration(
        color: AppColors.sheet,
        border: Border(left: BorderSide(color: color, width: 3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(text, style: const TextStyle(fontSize: 14, height: 1.4)),
          if (traceId != null)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: SelectableText('Trace $traceId', style: const TextStyle(fontSize: 11, color: AppColors.ink3)),
            ),
        ],
      ),
    );
  }
}

/// Says what went wrong, with the trace ID when there is one.
class ErrorNote extends StatelessWidget {
  const ErrorNote({super.key, required this.error, required this.what});
  final Object? error;
  final String what;

  @override
  Widget build(BuildContext context) {
    final e = error;
    final message = e is ApiException ? e.message : '$e';
    return NoteBox("Couldn't load $what. $message",
        kind: NoteKind.error, traceId: e is ApiException ? e.traceId : null);
  }
}

/// Shown instead of a section whose agent didn't answer: the rest of the file still works.
class AgentDown extends StatelessWidget {
  const AgentDown(this.section, {super.key});
  final Section<Object?> section;

  @override
  Widget build(BuildContext context) => NoteBox(
        "${agentLabel(section.agent)} didn't answer: ${section.error ?? 'unknown error'}. The rest of the file is still current.",
        kind: NoteKind.error,
      );
}

/// A small dot: green for live/ok, red for high severity, amber for medium.
class Dot extends StatelessWidget {
  const Dot(this.color, {super.key, this.size = 8});
  final Color color;
  final double size;

  @override
  Widget build(BuildContext context) =>
      Container(width: size, height: size, decoration: BoxDecoration(color: color, shape: BoxShape.circle));
}

Color severityColor(String severity) => switch (severity) {
      'high' => AppColors.blocker,
      'medium' => AppColors.attention,
      _ => AppColors.ink3,
    };

/// Which agents prepared this file and how long each took.
/// The one animation: the names fade in one after another.
class AgentStrip extends StatelessWidget {
  const AgentStrip({super.key, required this.sections});
  final List<Section<Object?>> sections;

  @override
  Widget build(BuildContext context) {
    final reduceMotion = MediaQuery.maybeDisableAnimationsOf(context) ?? false;
    return Semantics(
      label: 'Agents that prepared this file',
      child: Wrap(
        spacing: 16,
        runSpacing: 6,
        children: [
          for (var i = 0; i < sections.length; i++)
            TweenAnimationBuilder<double>(
              tween: Tween<double>(begin: reduceMotion ? 1.0 : 0.0, end: 1.0),
              duration: Duration(milliseconds: reduceMotion ? 0 : 300 + i * 80),
              builder: (context, t, child) => Opacity(opacity: t, child: child),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Dot(sections[i].ok ? AppColors.ledger : AppColors.blocker, size: 7),
                  const SizedBox(width: 6),
                  Text(agentLabel(sections[i].agent),
                      style: TextStyle(fontSize: 13, color: sections[i].ok ? AppColors.ink2 : AppColors.blocker)),
                  const SizedBox(width: 4),
                  Text(sections[i].ok ? '${sections[i].durationMs} ms' : "didn't answer",
                      style: const TextStyle(fontSize: 12, color: AppColors.ink3)),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

/// Grey placeholder lines while something loads.
class LoadingLines extends StatelessWidget {
  const LoadingLines({super.key, this.label});
  final String? label;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (label != null) Text(label!, style: const TextStyle(color: AppColors.ink3)),
          const SizedBox(height: 12),
          const LinearProgressIndicator(minHeight: 2, color: AppColors.ledger, backgroundColor: AppColors.rule),
        ],
      ),
    );
  }
}
