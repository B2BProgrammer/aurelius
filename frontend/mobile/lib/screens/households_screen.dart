import 'package:flutter/material.dart';

import '../api/models.dart';
import '../state/app_scope.dart';
import '../ui/theme.dart';
import '../ui/widgets.dart';
import 'household_screen.dart';

class HouseholdsScreen extends StatefulWidget {
  const HouseholdsScreen({super.key});

  @override
  State<HouseholdsScreen> createState() => _HouseholdsScreenState();
}

class _HouseholdsScreenState extends State<HouseholdsScreen> {
  Future<List<ClientSummary>>? _clients;

  // LEARN: start the request once (not in build), or every rebuild would refetch.
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _clients ??= AppScope.of(context).api.clients();
  }

  Future<void> _refresh() async {
    final next = AppScope.of(context).api.clients();
    setState(() => _clients = next);
    await next;
  }

  @override
  Widget build(BuildContext context) {
    final session = AppScope.of(context).session;
    return Scaffold(
      appBar: AppBar(
        title: Text('Your households', style: serifStyle(22, weight: FontWeight.w500)),
        actions: [
          IconButton(
            tooltip: 'Sign out',
            icon: const Icon(Icons.logout),
            onPressed: () => session.signOut(),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: FutureBuilder<List<ClientSummary>>(
          future: _clients,
          builder: (context, snap) {
            if (snap.connectionState != ConnectionState.done) {
              return ListView(children: const [LoadingLines()]);
            }
            if (snap.hasError) {
              return ListView(
                padding: const EdgeInsets.all(20),
                children: [ErrorNote(error: snap.error, what: 'your households')],
              );
            }
            final clients = snap.data ?? const <ClientSummary>[];
            return ListView.separated(
              itemCount: clients.length + 1,
              separatorBuilder: (_, __) => const Divider(indent: 20, endIndent: 20),
              itemBuilder: (context, i) {
                if (i == clients.length) {
                  return Padding(
                    padding: const EdgeInsets.all(20),
                    child: Text('Signed in as ${session.user}. All households are fictional.',
                        style: const TextStyle(fontSize: 12, color: AppColors.ink3)),
                  );
                }
                final c = clients[i];
                return ListTile(
                  contentPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 6),
                  title: Text(c.shortName, style: serifStyle(22)),
                  // Only when it adds something: "Chen family" would just repeat the title.
                  subtitle: c.household == c.shortName
                      ? null
                      : Text(c.household, style: const TextStyle(color: AppColors.ink3)),
                  trailing: const Icon(Icons.chevron_right, color: AppColors.ink3),
                  onTap: () => Navigator.of(context).push(
                    MaterialPageRoute<void>(builder: (_) => HouseholdScreen(client: c)),
                  ),
                );
              },
            );
          },
        ),
      ),
    );
  }
}
