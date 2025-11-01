// lib/main.dart
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'widgets/wine_viz.dart';

void main() => runApp(const ColoursOfWineApp());

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
  final _controller = TextEditingController(text: 'Riesling Bürklin Otto Paus 2021');
  final String _backend = 'http://127.0.0.1:8000';

  bool _loading = false;

  // Ergebnisfelder
  Map<String, dynamic>? _props;         // strukturierte Eigenschaften (vom Backend)
  List<Map<String, dynamic>> _sources = [];
  String? _note;                        // kurze Note (z. B. “LLM aktiv …”)
  List<String> _notes = [];             // längere Liste aus Backend
  String? _hexForViz;                   // HEX-Farbe für Visualisierung (fallback)
  String? _searchedQuery;               // tatsächlich verwendete Web-Query
  bool _usedLLM = false;

  // ---------------- API Calls ----------------

  Future<void> _callAnalyze({required bool useLLM}) async {
    final name = _controller.text.trim();
    if (name.isEmpty) return;

    setState(() {
      _loading = true;
      _note = null;
      _notes = [];
    });

    try {
      final resp = await http.post(
        Uri.parse('$_backend/analyze'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'wine_name': name,
          // wird vom aktuellen Backend ausgewertet; ältere Backends ignorieren es
          'use_llm': useLLM,
        }),
      );

      if (resp.statusCode == 200) {
        final data = jsonDecode(resp.body) as Map<String, dynamic>;

        // Eigenschaften
        final propsMap = (data['props'] as Map?)?.map((k, v) => MapEntry(k.toString(), v));

        // Quellen
        final src = <Map<String, dynamic>>[];
        if (data['sources'] is List) {
          for (final s in (data['sources'] as List)) {
            if (s is Map) {
              src.add({
                'title': (s['title'] ?? '').toString(),
                'snippet': (s['snippet'] ?? '').toString(),
                'url': (s['url'] ?? '').toString(),
              });
            }
          }
        }

        setState(() {
          _props = propsMap?.cast<String, dynamic>();
          _sources = src;
          _note = (data['note'] ?? '').toString();
          _notes = (data['notes'] is List)
              ? (data['notes'] as List).map((e) => e.toString()).toList()
              : <String>[];
          _hexForViz = (data['hex'] ?? '').toString().isNotEmpty ? data['hex'] : null;
          _searchedQuery = (data['searched_query'] ?? '').toString();
          _usedLLM = (data['used_llm'] == true);
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

  Future<void> _analyzeHeuristic() => _callAnalyze(useLLM: false);
  Future<void> _analyzeWithLLM() => _callAnalyze(useLLM: true);

  // ---------------- Visualisierung ----------------

  void _openViz() {
    // Visualisierung nutzt Props (bevorzugt) + optional fallbackHex
    final prof = WineProfile.fromProps(_props ?? {}, hex: _hexForViz);
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        contentPadding: EdgeInsets.zero,
        content: SizedBox(width: 520, height: 520, child: WineViz(profile: prof)),
      ),
    );


    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        contentPadding: EdgeInsets.zero,
        content: SizedBox(
          width: 520,
          height: 520,
          child: WineViz(profile: prof),
        ),
      ),
    );
  }

  // ---------------- UI ----------------

  @override
  Widget build(BuildContext context) {
    // Visualisierung ist möglich, wenn entweder Props da sind oder zumindest eine HEX-Farbe
    final canViz = (_props != null) || (_hexForViz != null);

    return Scaffold(
      backgroundColor: const Color(0xFFF6EFF7),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 1100),
            child: ListView(
              padding: const EdgeInsets.fromLTRB(16, 18, 16, 32),
              children: [
                Text('Colours of Wine', style: Theme.of(context).textTheme.headlineSmall),
                const SizedBox(height: 16),
                Text('Weinname (z. B. "Tignanello 2021")',
                    style: Theme.of(context).textTheme.bodySmall),
                const SizedBox(height: 6),
                TextField(
                  controller: _controller,
                  onSubmitted: (_) => _analyzeHeuristic(),
                  decoration: InputDecoration(
                    hintText: 'z. B. "Riesling Bürklin-Wolf 2021" …',
                    filled: true,
                    fillColor: Colors.white,
                    contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                ),
                const SizedBox(height: 14),

                // --- Drei Buttons ---
                Wrap(
                  spacing: 12,
                  runSpacing: 8,
                  alignment: WrapAlignment.center,
                  children: [
                    ElevatedButton.icon(
                      onPressed: _loading ? null : _analyzeHeuristic,
                      icon: const Icon(Icons.analytics_outlined),
                      label: Text(_loading ? 'Analysiere…' : 'Analysieren'),
                    ),
                    ElevatedButton.icon(
                      onPressed: _loading ? null : _analyzeWithLLM,
                      icon: const Icon(Icons.psychology_alt_outlined),
                      label: const Text('Daten mittels LLM ergänzen'),
                    ),
                    ElevatedButton.icon(
                      onPressed: canViz && !_loading ? _openViz : null,
                      icon: const Icon(Icons.bubble_chart_outlined),
                      label: const Text('Visualisierung generieren'),
                    ),
                  ],
                ),

                const SizedBox(height: 18),

                if (_props != null)
                  _PropsCard(
                    props: _props!,
                    searchedQuery: _searchedQuery,
                    usedLLM: _usedLLM,
                  ),

                const SizedBox(height: 16),
                Text('Notizen:', style: Theme.of(context).textTheme.titleSmall),
                const SizedBox(height: 4),
                if (_notes.isNotEmpty)
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: _notes.map((n) => Text('• $n')).toList(),
                  )
                else
                  Text(
                    (_note?.trim().isNotEmpty ?? false)
                        ? _note!.trim()
                        : '—',
                  ),

                const SizedBox(height: 18),
                Text('Quellen:', style: Theme.of(context).textTheme.titleSmall),
                const SizedBox(height: 8),
                if (_sources.isEmpty)
                  const Text('– keine –'),
                for (final s in _sources) _SourceTile(source: s),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _PropsCard extends StatelessWidget {
  final Map<String, dynamic> props;
  final String? searchedQuery;
  final bool usedLLM;
  const _PropsCard({
    required this.props,
    this.searchedQuery,
    required this.usedLLM,
  });

  String _fmt(dynamic v) {
    if (v == null) return '—';
    if (v is List) return v.isEmpty ? '—' : v.join(', ');
    return v.toString();
  }

  @override
  Widget build(BuildContext context) {
    final rows = <List<String>>[
      ['Jahrgang', _fmt(props['vintage'])],
      ['Typ', _fmt(props['wine_type'])],
      ['Rebsorte', _fmt(props['variety'])],
      ['Trauben', _fmt(props['grapes'])],
      ['Land', _fmt(props['country'])],
      ['Region', _fmt(props['region'])],
      ['Appellation', _fmt(props['appellation'])],
      ['Produzent', _fmt(props['producer'])],
      ['Stil', _fmt(props['style'])],
      ['Süße', _fmt(props['sweetness'])],
      ['Alkohol %', _fmt(props['alcohol'])],
      ['Eiche', _fmt(props['oak'])],
      ['Aromen', _fmt(props['tasting_notes'])],
    ];

    return Card(
      color: Colors.white,
      elevation: 0,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Eigenschaften', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 6),
          Row(
            children: [
              if (searchedQuery?.isNotEmpty == true)
                Expanded(
                  child: Text('Such-Query: ${searchedQuery!}',
                      style: Theme.of(context).textTheme.bodySmall,
                      overflow: TextOverflow.ellipsis),
                ),
              const SizedBox(width: 12),
              Chip(
                label: Text(usedLLM ? 'LLM aktiv' : 'ohne LLM'),
                visualDensity: VisualDensity.compact,
              ),
            ],
          ),
          const SizedBox(height: 12),
          Table(
            columnWidths: const {0: IntrinsicColumnWidth()},
            defaultVerticalAlignment: TableCellVerticalAlignment.middle,
            children: [
              for (final r in rows)
                TableRow(children: [
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 6),
                    child: Text(r[0], style: const TextStyle(fontWeight: FontWeight.w600)),
                  ),
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 6, horizontal: 8),
                    child: Text(r[1]),
                  ),
                ])
            ],
          ),
        ]),
      ),
    );
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
              child: Text(snippet, style: TextStyle(color: Colors.black.withOpacity(0.75))),
            ),
          if (url.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 2.0),
              child: Text(
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
