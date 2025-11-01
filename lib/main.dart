import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:flutter/foundation.dart' show kIsWeb;
import 'dart:html' as html; // nur für Flutter Web


// Stelle sicher, dass diese Datei existiert (widgets/wine_viz.dart aus meiner vorherigen Antwort)
import 'widgets/wine_viz.dart';

void main() {
  runApp(const ColoursOfWineApp());
}

class ColoursOfWineApp extends StatelessWidget {
  const ColoursOfWineApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Colours of Wine',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF6D5E9E)),
        useMaterial3: true,
      ),
      home: const HomePage(),
    );
  }
}

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  final _controller =
  TextEditingController(text: 'Riesling Bürklin Otto Paus 2021');

  bool _loading = false;
  bool _showViz = false; // <- neu: Visualisierung per Button

  // Backend-Ergebnis
  List<int>? _rgb; // [r,g,b]
  String? _hex; // "#AABBCC"
  String? _note; // Hinweistext
  List<Map<String, dynamic>> _sources = [];

  // Backend-URL (lokal)
  final String _backendBase = kIsWeb
      ? 'http://${html.window.location.hostname}:8000' // z.B. localhost:8000 oder 127.0.0.1:8000
      : 'http://127.0.0.1:8000';

  Future<void> _analyze() async {
    final query = _controller.text.trim();
    if (query.isEmpty) return;

    setState(() {
      _loading = true;
      _note = null;
      _showViz = false; // nach neuer Analyse erst wieder explizit generieren
    });

    try {
      final uri = Uri.parse('$_backendBase/analyze');
      final resp = await http.post(
        uri,
        headers: {'Content-Type': 'application/json'},
        // Backend erwartet "wine_name"
        body: jsonEncode({'wine_name': query}),
      );

      if (resp.statusCode == 200) {
        final data = jsonDecode(resp.body) as Map<String, dynamic>;

        // defensive parsing
        List<int>? rgb;
        if (data['rgb'] is List) {
          final list = (data['rgb'] as List).cast<num>();
          if (list.length >= 3) {
            rgb = [list[0].toInt(), list[1].toInt(), list[2].toInt()];
          }
        }

        String? hex = data['hex'] is String ? data['hex'] as String : null;
        String? note = data['note'] is String ? data['note'] as String : null;

        final src = <Map<String, dynamic>>[];
        if (data['sources'] is List) {
          for (final s in (data['sources'] as List)) {
            if (s is Map<String, dynamic>) {
              src.add({
                'title': s['title'] ?? '',
                'snippet': s['snippet'] ?? '',
                'url': s['url'] ?? '',
              });
            }
          }
        }

        setState(() {
          _rgb = rgb;
          _hex = hex;
          _note = note;
          _sources = src;
          _loading = false;
        });
      } else {
        setState(() {
          _note = 'Backend-Fehler (${resp.statusCode}): ${resp.body}';
          _loading = false;
        });
      }
    } catch (e) {
      setState(() {
        _note = 'Keine Verbindung zum Backend: $e';
        _loading = false;
      });
    }
  }

  void _generateViz() {
    // Nur aktivieren, wenn eine Farbe vorhanden ist
    final color = _currentColor;
    if (color == null) {
      setState(() {
        _note = 'Bitte zuerst "Analysieren" ausführen – keine Farbe vorhanden.';
      });
      return;
    }
    setState(() {
      _showViz = true;
    });
  }

  Color? get _currentColor {
    if (_hex != null) return _colorFromHex(_hex!);
    if (_rgb != null) {
      return Color.fromARGB(255, _rgb![0], _rgb![1], _rgb![2]);
    }
    return null;
  }

  Color? _colorFromHex(String? hex) {
    if (hex == null) return null;
    var h = hex.trim();
    if (h.startsWith('#')) h = h.substring(1);
    if (h.length == 6) h = 'FF$h';
    if (h.length != 8) return null;
    final v = int.tryParse(h, radix: 16);
    if (v == null) return null;
    return Color(v);
  }

  Widget _buildHeader() {
    final colorReady = _currentColor != null;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Colours of Wine', style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 16),
        Text('Weinname (z. B. "Tignanello 2021")',
            style: Theme.of(context).textTheme.bodySmall),
        const SizedBox(height: 6),
        TextField(
          controller: _controller,
          onSubmitted: (_) => _analyze(),
          decoration: InputDecoration(
            hintText: 'z. B. "Riesling Bürklin-Wolf 2021" …',
            filled: true,
            fillColor: Colors.white,
            contentPadding:
            const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
            border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
          ),
        ),
        const SizedBox(height: 16),

        // --- Zwei Buttons nebeneinander ---
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            ElevatedButton.icon(
              onPressed: _loading ? null : _analyze,
              icon: const Icon(Icons.analytics),
              label: Text(_loading ? 'Analysiere…' : 'Analysieren'),
              style: ElevatedButton.styleFrom(
                padding:
                const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(22)),
              ),
            ),
            const SizedBox(width: 10),
            ElevatedButton.icon(
              onPressed: (_loading || !colorReady) ? null : _generateViz,
              icon: const Icon(Icons.bubble_chart),
              label: const Text('Visualisierung generieren'),
              style: ElevatedButton.styleFrom(
                padding:
                const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(22)),
              ),
            ),
          ],
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final color = _currentColor;

    return Scaffold(
      backgroundColor: const Color(0xFFF6EFF7),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 1100),
            child: ListView(
              padding: const EdgeInsets.fromLTRB(16, 18, 16, 32),
              children: [
                _buildHeader(),
                const SizedBox(height: 12),

                // Farbbalken (schneller Überblick)
                if (color != null) ...[
                  const SizedBox(height: 8),
                  _ColorSwatchBar(color: color, hex: _hex, rgb: _rgb),
                ],

                // --- Kreis-Visualisierung nur wenn explizit generiert ---
                if (color != null && _showViz) ...[
                  const SizedBox(height: 20),
                  Card(
                    elevation: 0,
                    color: Colors.white,
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(16)),
                    child: Padding(
                      padding: const EdgeInsets.all(16.0),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Text('Visualisierung',
                              style: Theme.of(context).textTheme.titleMedium),
                          const SizedBox(height: 12),
                          SizedBox(
                            width: 520,
                            height: 520,
                            child: WineViz(
                              profile: WineProfile.fromBaseColor(color),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],

                const SizedBox(height: 16),
                Text('Notizen:', style: Theme.of(context).textTheme.titleSmall),
                const SizedBox(height: 4),
                Text(
                  _note?.trim().isNotEmpty == true
                      ? _note!.trim()
                      : '• (Heuristik oder sichere Defaults, LLM evtl. nicht aktiv)',
                ),

                const SizedBox(height: 18),
                Text('Quellen:', style: Theme.of(context).textTheme.titleSmall),
                const SizedBox(height: 8),
                if (_sources.isEmpty) const Text('– keine –'),
                for (final s in _sources) _SourceTile(source: s),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _ColorSwatchBar extends StatelessWidget {
  final Color color;
  final String? hex;
  final List<int>? rgb;

  const _ColorSwatchBar({required this.color, this.hex, this.rgb});

  @override
  Widget build(BuildContext context) {
    final text = '${_nameFor(color)} (${_hexOf(color)})';
    final rgbText =
    rgb != null ? 'RGB: ${rgb![0]}, ${rgb![1]}, ${rgb![2]}' : '';
    final hexText = 'HEX: ${_hexOf(color)}';

    return Card(
      color: Colors.white,
      elevation: 0,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(12.0),
        child: Column(
          children: [
            Container(
              height: 140,
              decoration: BoxDecoration(
                color: color,
                borderRadius: BorderRadius.circular(12),
              ),
              alignment: Alignment.center,
              child: Text(
                text,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 18,
                  fontWeight: FontWeight.w600,
                  shadows: [Shadow(offset: Offset(0, 1), blurRadius: 4)],
                ),
              ),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                if (rgbText.isNotEmpty) Text(rgbText),
                if (rgbText.isNotEmpty) const SizedBox(width: 12),
                Text(hexText),
              ],
            ),
          ],
        ),
      ),
    );
  }

  static String _hexOf(Color c) =>
      '#${c.value.toRadixString(16).padLeft(8, '0').substring(2).toUpperCase()}';

  // sehr grobe Benamsung ähnlich wie vorher
  static String _nameFor(Color c) {
    final h = HSLColor.fromColor(c);
    final l = h.lightness;
    if (l > 0.78) return 'pale straw';
    if (l < 0.28) return 'ruby';
    if (h.hue >= 10 && h.hue <= 30) return 'amber';
    if (h.hue >= 330 || h.hue <= 15) return 'garnet';
    if (h.hue >= 45 && h.hue <= 80) return 'straw';
    return 'wine tone';
  }
}

class _SourceTile extends StatelessWidget {
  final Map<String, dynamic> source;
  const _SourceTile({required this.source});

  @override
  Widget build(BuildContext context) {
    final title = (source['title'] ?? '').toString();
    final snippet = (source['snippet'] ?? '').toString();
    final url = (source['url'] ?? '').toString();

    return Padding(
      padding: const EdgeInsets.only(bottom: 12.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (title.isNotEmpty)
            Text(title, style: const TextStyle(fontWeight: FontWeight.w600)),
          if (snippet.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 2.0),
              child: Text(
                snippet,
                style: TextStyle(color: Colors.black.withOpacity(0.75)),
              ),
            ),
          if (url.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 2.0),
              child: SelectableText(
                url,
                style: const TextStyle(
                  color: Colors.blueAccent,
                  decoration: TextDecoration.underline,
                ),
              ),
            ),
        ],
      ),
    );
  }
}
