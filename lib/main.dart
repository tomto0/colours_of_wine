// lib/main.dart
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

const String apiBase = 'http://127.0.0.1:8000';

void main() {
  runApp(const ColoursOfWineApp());
}

class ColoursOfWineApp extends StatelessWidget {
  const ColoursOfWineApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Colours of Wine',
      theme: ThemeData(colorSchemeSeed: const Color(0xFF6D5BA1), useMaterial3: true),
      home: const HomePage(),
      debugShowCheckedModeBanner: false,
    );
  }
}

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  final _controller = TextEditingController(text: 'Riesling Bürklin Otto Paus 2021');
  bool _loading = false;
  String? _error;
  Map<String, dynamic>? _data;

  Future<void> _analyze() async {
    setState(() {
      _loading = true;
      _error = null;
      _data = null;
    });

    try {
      final uri = Uri.parse('$apiBase/analyze');
      final resp = await http.post(
        uri,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'wine_name': _controller.text.trim()}),
      );

      if (resp.statusCode != 200) {
        throw Exception('Backend-Fehler: HTTP ${resp.statusCode}');
      }

      final decoded = jsonDecode(resp.body) as Map<String, dynamic>;

      // Robust gegen fehlende Felder / null
      decoded['notes'] = (decoded['notes'] as List?)?.map((e) => e.toString()).toList() ?? <String>[];
      decoded['sources'] = (decoded['sources'] as List?)
          ?.whereType<Map<String, dynamic>>()
          .map((m) => {
        'title': m['title']?.toString(),
        'url': m['url']?.toString(),
        'snippet': m['snippet']?.toString(),
      })
          .toList() ??
          <Map<String, dynamic>>[];

      final color = decoded['color'] as Map<String, dynamic>;
      final hex = (color['hex'] as String?) ?? '#000000';
      final rgb = (color['rgb'] as List?)?.map((e) => e as int).toList() ?? [0, 0, 0];

      decoded['color'] = {'hex': hex, 'name': color['name'] ?? 'unknown', 'rgb': rgb};

      setState(() {
        _data = decoded;
      });
    } catch (e) {
      setState(() {
        _error = 'Keine Verbindung zum Backend oder Fehler beim Parsen: $e';
      });
    } finally {
      setState(() {
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    final colorHex = _data?['color']?['hex'] as String?;
    final swatch = colorHex != null ? _colorFromHex(colorHex) : theme.colorScheme.surface;

    return Scaffold(
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Text('Colours of Wine', style: theme.textTheme.headlineMedium),
            const SizedBox(height: 16),
            Text('Weinname (z. B. "Tignanello 2021")', style: theme.textTheme.labelMedium),
            TextField(
              controller: _controller,
              decoration: const InputDecoration(hintText: 'z. B. "Riesling Bürklin Otto Paus 2021"'),
              onSubmitted: (_) => _analyze(),
            ),
            const SizedBox(height: 16),
            Center(
              child: FilledButton.icon(
                onPressed: _loading ? null : _analyze,
                icon: const Icon(Icons.analytics_outlined),
                label: const Text('Analysieren'),
              ),
            ),
            const SizedBox(height: 24),
            if (_loading) const Center(child: CircularProgressIndicator()),
            if (_error != null)
              Text(_error!, style: theme.textTheme.bodyMedium?.copyWith(color: theme.colorScheme.error)),
            if (_data != null) ...[
              _ColorPreview(hex: _data!['color']['hex'] as String, name: _data!['color']['name'] as String),
              const SizedBox(height: 12),
              Text('RGB: ${(_data!['color']['rgb'] as List).join(", ")}  •  HEX: ${_data!['color']['hex']}'),
              const SizedBox(height: 12),
              if ((_data!['notes'] as List).isNotEmpty) ...[
                Text('Notizen:', style: theme.textTheme.titleMedium),
                const SizedBox(height: 6),
                for (final n in _data!['notes'] as List) Text('• $n'),
              ],
              const SizedBox(height: 12),
              if ((_data!['sources'] as List).isNotEmpty) ...[
                Text('Quellen:', style: theme.textTheme.titleMedium),
                const SizedBox(height: 6),
                for (final s in _data!['sources'] as List)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: _SourceTile(
                      title: (s['title'] as String?) ?? '(ohne Titel)',
                      url: (s['url'] as String?) ?? '',
                      snippet: (s['snippet'] as String?) ?? '',
                    ),
                  ),
              ],
            ],
          ],
        ),
      ),
    );
  }
}

class _ColorPreview extends StatelessWidget {
  final String hex;
  final String name;
  const _ColorPreview({required this.hex, required this.name});

  @override
  Widget build(BuildContext context) {
    final color = _colorFromHex(hex);
    return Container(
      height: 120,
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.black12),
      ),
      alignment: Alignment.center,
      child: Text(
        '$name ($hex)',
        style: Theme.of(context).textTheme.titleLarge?.copyWith(
          color: _contrastingText(color),
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}

class _SourceTile extends StatelessWidget {
  final String title;
  final String url;
  final String snippet;
  const _SourceTile({required this.title, required this.url, required this.snippet});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(title, style: theme.textTheme.bodyLarge),
      if (snippet.isNotEmpty) Text(snippet, style: theme.textTheme.bodySmall),
      if (url.isNotEmpty)
        Text(url, style: theme.textTheme.bodySmall?.copyWith(color: theme.colorScheme.primary)),
    ]);
  }
}

Color _colorFromHex(String hex) {
  final h = hex.replaceAll('#', '');
  final r = int.parse(h.substring(0, 2), radix: 16);
  final g = int.parse(h.substring(2, 4), radix: 16);
  final b = int.parse(h.substring(4, 6), radix: 16);
  return Color.fromARGB(0xFF, r, g, b);
}

Color _contrastingText(Color bg) {
  // einfache Luminanz-Heuristik
  final luminance = (0.299 * bg.red + 0.587 * bg.green + 0.114 * bg.blue);
  return luminance > 140 ? Colors.black : Colors.white;
}
