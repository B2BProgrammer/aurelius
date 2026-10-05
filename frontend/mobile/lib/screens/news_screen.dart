import 'package:flutter/material.dart';

import '../state/news_controller.dart';
import '../ui/theme.dart';
import '../ui/widgets.dart';
import 'household_screen.dart' show EventRow;

/// Live market news from Pulse (Go), relayed by the Conductor. Arrives without refreshing.
class NewsScreen extends StatelessWidget {
  const NewsScreen({super.key, required this.news});
  final NewsController news;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Market news', style: serifStyle(22, weight: FontWeight.w500))),
      body: ListenableBuilder(
        listenable: news,
        builder: (context, _) {
          final (label, color) = switch (news.status) {
            NewsStatus.live => ('Listening to Pulse', AppColors.ledger),
            NewsStatus.connecting => ('Connecting…', AppColors.ink3),
            NewsStatus.offline => ('Offline, retrying', AppColors.attention),
            NewsStatus.off => (
                news.supported ? 'Live news is off' : 'Live news works in the phone app, not in the browser',
                AppColors.ink3
              ),
          };
          return ListView(
            padding: const EdgeInsets.all(20),
            children: [
              Semantics(
                liveRegion: true,
                child: Row(children: [
                  Dot(color),
                  const SizedBox(width: 8),
                  Expanded(child: Text(label, style: const TextStyle(color: AppColors.ink3))),
                ]),
              ),
              const SizedBox(height: 18),
              if (news.events.isEmpty && news.status == NewsStatus.live)
                const Text('Nothing new yet. Events appear here the moment Pulse sees them.',
                    style: TextStyle(color: AppColors.ink2)),
              for (final e in news.events) EventRow(event: e),
            ],
          );
        },
      ),
    );
  }
}
