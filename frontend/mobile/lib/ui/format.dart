/// Money, dates and odds, written the same way everywhere (and the same as the web app).
library;

String _thousands(int n) {
  final s = n.toString();
  final b = StringBuffer();
  for (var i = 0; i < s.length; i++) {
    if (i > 0 && (s.length - i) % 3 == 0) b.write(',');
    b.write(s[i]);
  }
  return b.toString();
}

/// 2350000 -> $2,350,000 ; -29610 -> −$29,610 (a real minus sign)
String money(num n) => '${n < 0 ? '−' : ''}\$${_thousands(n.abs().round())}';

/// +$11,000 / −$29,610
String signedMoney(num n) => n < 0 ? money(n) : '+${money(n)}';

/// $2.35M, $329k: for headers where space is tight.
String moneyShort(num n) {
  final abs = n.abs();
  final sign = n < 0 ? '−' : '';
  if (abs >= 1000000) return '$sign\$${(abs / 1000000).toStringAsFixed(abs >= 10000000 ? 1 : 2)}M';
  if (abs >= 1000) return '$sign\$${(abs / 1000).round()}k';
  return '$sign\$${abs.round()}';
}

/// Never "100%" or "0%" for a projection: it must not sound certain.
String chance(double pct) {
  if (pct >= 99.5) return 'over 99%';
  if (pct < 0.5) return 'under 1%';
  return '${pct.round()}%';
}

const _days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const _months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

DateTime? _calendarDay(String iso) {
  if (iso.length < 10) return null;
  return DateTime.tryParse('${iso.substring(0, 10)}T00:00:00Z');
}

/// "2026-10-08" -> "Thu, Oct 8" (a calendar day: read as UTC so time zones can't shift it)
String day(String iso) {
  final d = _calendarDay(iso);
  return d == null ? iso : '${_days[d.weekday - 1]}, ${_months[d.month - 1]} ${d.day}';
}

/// "2026-10-08" -> "Oct 8"
String shortDay(String iso) {
  final d = _calendarDay(iso);
  return d == null ? iso : '${_months[d.month - 1]} ${d.day}';
}

const classLabel = {'equity': 'Stocks', 'fixed_income': 'Bonds', 'cash': 'Cash'};

const agentName = {
  'liaison': 'Liaison',
  'analyst': 'Analyst',
  'notary': 'Notary',
  'actuary': 'Actuary',
  'pulse': 'Pulse',
  'scribe': 'Scribe',
  'herald': 'Herald',
  'librarian': 'Librarian',
  'sentinel': 'Sentinel',
};

String agentLabel(String code) => agentName[code] ?? code;

/// The Conductor's answers use light Markdown. Show it as clean text on the phone.
String plainText(String markdown) => markdown
    .replaceAll('**', '')
    .replaceAll('__', '')
    .split('\n')
    .map((line) => line.startsWith('- ') || line.startsWith('* ') ? '• ${line.substring(2)}' : line)
    .join('\n');
