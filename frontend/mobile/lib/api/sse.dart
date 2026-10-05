/// Server-Sent Events: the text format the Conductor uses for live news.
///
///   event: market_event
///   data: {"event_id":"EV-1001", ...}
///   <blank line>
///
/// LEARN: an SSE stream is just a long HTTP response that never finishes.
/// We read it piece by piece, cut it at blank lines, and parse each block.
library;

import 'dart:convert';

class SseMessage {
  const SseMessage(this.event, this.data);
  final String event;
  final String data;

  @override
  bool operator ==(Object other) => other is SseMessage && other.event == event && other.data == data;

  @override
  int get hashCode => Object.hash(event, data);

  @override
  String toString() => 'SseMessage($event, $data)';
}

/// Parses complete blocks. Comment lines (": ping") and blocks without data are skipped.
List<SseMessage> parseSse(String text) {
  final out = <SseMessage>[];
  for (final block in text.replaceAll('\r\n', '\n').split('\n\n')) {
    var event = 'message';
    final data = <String>[];
    for (final line in block.split('\n')) {
      if (line.startsWith('event:')) {
        event = line.substring(6).trim();
      } else if (line.startsWith('data:')) {
        data.add(line.substring(5).trim());
      }
    }
    if (data.isNotEmpty) out.add(SseMessage(event, data.join('\n')));
  }
  return out;
}

/// Turns the raw bytes of a streaming response into messages, as they arrive.
Stream<SseMessage> sseMessages(Stream<List<int>> bytes) async* {
  var buffer = '';
  await for (final text in bytes.transform(utf8.decoder)) {
    buffer = (buffer + text).replaceAll('\r\n', '\n');
    final cut = buffer.lastIndexOf('\n\n');
    if (cut < 0) continue;
    for (final message in parseSse(buffer.substring(0, cut))) {
      yield message;
    }
    buffer = buffer.substring(cut + 2);
  }
}
