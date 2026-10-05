import 'package:flutter/material.dart';

import '../state/news_controller.dart';
import '../state/app_scope.dart';
import 'ask_screen.dart';
import 'households_screen.dart';
import 'news_screen.dart';

/// The three tabs at the bottom: Households, News, Ask.
///
/// LEARN: IndexedStack keeps every tab alive while you switch, so the news
/// stream keeps listening and a half-typed question isn't lost.
class HomeShell extends StatefulWidget {
  const HomeShell({super.key, this.liveNews = true});
  final bool liveNews;

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  int _tab = 0;
  NewsController? _news;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _news ??= NewsController(AppScope.of(context).api, enabled: widget.liveNews)..start();
  }

  @override
  void dispose() {
    _news?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final news = _news!;
    return Scaffold(
      body: IndexedStack(
        index: _tab,
        children: [
          const HouseholdsScreen(),
          NewsScreen(news: news),
          const AskScreen(),
        ],
      ),
      bottomNavigationBar: ListenableBuilder(
        listenable: news,
        builder: (context, _) => NavigationBar(
          selectedIndex: _tab,
          onDestinationSelected: (i) {
            setState(() => _tab = i);
            if (i == 1) news.markSeen();
          },
          destinations: [
            const NavigationDestination(icon: Icon(Icons.people_outline), selectedIcon: Icon(Icons.people), label: 'Households'),
            NavigationDestination(
              icon: Badge(
                isLabelVisible: news.unseen > 0,
                label: Text('${news.unseen}'),
                child: const Icon(Icons.newspaper_outlined),
              ),
              selectedIcon: const Icon(Icons.newspaper),
              label: 'News',
            ),
            const NavigationDestination(icon: Icon(Icons.chat_bubble_outline), selectedIcon: Icon(Icons.chat_bubble), label: 'Ask'),
          ],
        ),
      ),
    );
  }
}
