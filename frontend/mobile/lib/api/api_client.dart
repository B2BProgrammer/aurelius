/// The ONLY class that talks to the network.
///
/// LEARN:
///  - The app knows one address: the Conductor. Agent URLs and the SERVICE_TOKEN
///    never reach the phone.
///  - The advisor's token is attached here and nowhere else.
///  - An expired token or a 401 signs the advisor out (onUnauthorized).
///  - Every error keeps the X-Trace-Id, so it can be found in every agent's log.
///  - The http.Client is passed in, so tests can use a fake Conductor (MockClient).
library;

import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import 'models.dart';
import 'sse.dart';

class ApiException implements Exception {
  ApiException(this.message, {required this.status, this.traceId});
  final String message;
  final int status; // 0 = never reached the Conductor
  final String? traceId;

  @override
  String toString() => message;
}

class ApiClient {
  ApiClient({required this.baseUrl, http.Client? client}) : _http = client ?? http.Client();

  final String baseUrl;
  final http.Client _http;
  static const _timeout = Duration(seconds: 30);

  String? token;
  DateTime? tokenExpiresAt;
  void Function()? onUnauthorized;

  Uri _uri(String path) => Uri.parse('$baseUrl$path');

  Map<String, String> _headers({bool json = false}) => {
        'Accept': 'application/json',
        if (json) 'Content-Type': 'application/json',
        if (token != null) 'Authorization': 'Bearer $token',
      };

  void _checkExpiry() {
    final exp = tokenExpiresAt;
    if (token != null && exp != null && DateTime.now().isAfter(exp)) {
      onUnauthorized?.call();
      throw ApiException('Your sign-in expired. Sign in again.', status: 401);
    }
  }

  Future<dynamic> _send(Future<http.Response> Function() call) async {
    _checkExpiry();
    final http.Response res;
    try {
      res = await call().timeout(_timeout);
    } on TimeoutException {
      throw ApiException('The Conductor took too long to answer.', status: 0);
    } on Exception {
      // http.ClientException, or a SocketException on some platforms: no answer at all
      throw ApiException("The Conductor isn't reachable. Check it's running on port 8000.", status: 0);
    }
    final traceId = res.headers['x-trace-id'];
    if (res.statusCode == 401 && token != null) onUnauthorized?.call();
    if (res.statusCode < 200 || res.statusCode >= 300) {
      var detail = '${res.statusCode} ${res.reasonPhrase ?? ''}'.trim();
      try {
        final body = jsonDecode(res.body);
        if (body is Map && body['detail'] is String) {
          detail = body['detail'] as String;
        } else if (body is Map && body['detail'] is List) {
          detail = 'Some fields are not valid.';
        }
      } on FormatException {
        // not JSON: keep the status text
      }
      throw ApiException(detail, status: res.statusCode, traceId: traceId);
    }
    return jsonDecode(utf8.decode(res.bodyBytes));
  }

  Future<dynamic> _get(String path) => _send(() => _http.get(_uri(path), headers: _headers()));

  Future<dynamic> _post(String path, Object body) =>
      _send(() => _http.post(_uri(path), headers: _headers(json: true), body: jsonEncode(body)));

  // ---------------------------------------------------------------- endpoints
  Future<Login> login(String username, String password) async =>
      Login.fromJson(await _post('/v1/auth/login', {'username': username, 'password': password}) as Json);

  Future<List<ClientSummary>> clients() async {
    final list = await _get('/v1/clients') as List<dynamic>;
    return list.whereType<Map<String, dynamic>>().map(ClientSummary.fromJson).toList();
  }

  Future<Overview> overview(String clientId) async =>
      Overview.fromJson(await _get('/v1/clients/${Uri.encodeComponent(clientId)}/overview') as Json);

  Future<SkillResult> skill(String agent, String name, Json input) async =>
      SkillResult.fromJson(await _post('/v1/skills/$agent/$name', {'input': input}) as Json);

  Future<Approval> approveDraft({required String clientId, required String subject, required String body}) async =>
      Approval.fromJson(
          await _post('/v1/drafts/approve', {'client_id': clientId, 'subject': subject, 'body': body}) as Json);

  Future<ChatAnswer> ask(String message, {String? clientId}) async => ChatAnswer.fromJson(
      await _post('/v1/chat', {'message': message, if (clientId != null) 'client_id': clientId}) as Json);

  /// Live market news. The stream stays open until the server closes it
  /// (every 30 minutes) or the caller cancels.
  ///
  /// LEARN: the token goes in a header, never in the URL (URLs end up in logs).
  Stream<MarketEvent> marketEvents({void Function()? onConnected}) async* {
    _checkExpiry();
    final request = http.Request('GET', _uri('/v1/stream'))
      ..headers.addAll({
        'Accept': 'text/event-stream',
        if (token != null) 'Authorization': 'Bearer $token',
      });
    final res = await _http.send(request);
    if (res.statusCode == 401 && token != null) onUnauthorized?.call();
    if (res.statusCode != 200) {
      throw ApiException('Live news unavailable (${res.statusCode})', status: res.statusCode);
    }
    onConnected?.call();
    await for (final message in sseMessages(res.stream)) {
      if (message.event != 'market_event') continue;
      final data = jsonDecode(message.data);
      if (data is Map<String, dynamic>) yield MarketEvent.fromJson(data);
    }
  }
}
