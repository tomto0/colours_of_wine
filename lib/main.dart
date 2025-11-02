import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'widgets/wine_viz.dart';

void main() => runApp(const ColoursOfWineApp());

class ColoursOfWineApp extends StatelessWidget {
  const ColoursOfWineApp({super.key});

  @override
  Widget build(BuildContext context) {
    const seed = Color(0xFF6D5E9E); // eleganter, leicht violetter Akzent
    return MaterialApp(
      title: 'Colours of Wine',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        fontFamily: 'Roboto',
        colorScheme: ColorScheme.fromSeed(
          seedColor: seed,
          brightness: Brightness.light,
          background: const Color(0xFFF3EFE6), // „paper“-ton passend zum Logo
        ),
        textTheme: const TextTheme(
          headlineMedium: TextStyle(fontWeight: FontWeight.w600, letterSpacing: -0.3),
          titleMedium: TextStyle(fontWeight: FontWeight.w600),
          labelLarge: TextStyle(fontWeight: FontWeight.w500),
        ),
        inputDecorationTheme: InputDecorationTheme(
          filled: true,
          fillColor: Colors.white,
          hintStyle: TextStyle(color: Colors.black.withOpacity(0.45)),
          contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(14),
            borderSide: BorderSide(color: Colors.black.withOpacity(0.08)),
          ),
          enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(14),
            borderSide: BorderSide(color: Colors.black.withOpacity(0.08)),
          ),
          focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(14),
            borderSide: BorderSide(color: seed, width: 1.4),
          ),
        ),
        cardTheme: CardThemeData(
          elevation: 0,
          color: Colors.white.withOpacity(0.75),
          surfaceTintColor: Colors.transparent,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(22)),
        ),
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
  final TextEditingController _controller =
  TextEditingController(text: 'LES MOUGEOTTES PINOT NOIR 2024');

  // 👉 Backend-Adresse ggf. anpassen
  final String _backend = 'http://127.0.0.1:8000';

  bool _loading = false;

  // Ergebnisfelder
  Map<String, dynamic>? _props; // strukturierte Eigenschaften
  Map<String, dynamic>? _viz; // LLM-Viz-Profil
  List<Map<String, dynamic>> _sources = [];
  String? _note;
  List<String> _notes = [];
  String? _hexForViz;
  String? _searchedQuery;
  bool _usedLLM = false;

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
        body: jsonEncode({'wine_name': name, 'use_llm': useLLM}),
      );

      if (!mounted) return;

      if (resp.statusCode == 200) {
        final data = jsonDecode(resp.body) as Map<String, dynamic>;
        final props =
        (data['props'] as Map?)?.map((k, v) => MapEntry(k.toString(), v));
        final viz =
        (data['viz'] as Map?)?.map((k, v) => MapEntry(k.toString(), v));

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
          _props = props ?? {};
          _viz = viz ?? {};
          _sources = src;
          _hexForViz = (data['hex'] ?? '').toString();
          _note = (data['note'] ?? '').toString();
          _notes = (data['notes'] is List)
              ? (data['notes'] as List).map((e) => e.toString()).toList()
              : [];
          _searchedQuery = (data['searched_query'] ?? '').toString();
          _usedLLM = (data['used_llm'] == true);
        });
      } else {
        setState(() {
          _note = 'Fehler: ${resp.statusCode}';
        });
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _note = 'Fehler: $e';
      });
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _analyzeHeuristic() => _callAnalyze(useLLM: false);
  Future<void> _analyzeWithLLM() => _callAnalyze(useLLM: true);

  void _openViz() {
    WineProfile profile;
    if (_viz != null) {
      profile = WineProfile.fromLLMMap(_viz!, fallbackHex: _hexForViz);
    } else if (_hexForViz != null) {
      profile = WineProfile.fromBaseColor(_colorFromHex(_hexForViz!));
    } else {
      profile = const WineProfile(baseColor: Color(0xFFF6F2AF));
    }

    showDialog(
      context: context,
      builder: (ctx) => Dialog(
        elevation: 0,
        backgroundColor: Colors.white,
        insetPadding: const EdgeInsets.all(24),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
        child: SizedBox(
          width: 620,
          height: 620,
          child: ClipRRect(
            borderRadius: BorderRadius.circular(24),
            child: WineViz(profile: profile),
          ),
        ),
      ),
    );
  }

  Color _colorFromHex(String hex) {
    var h = hex.trim();
    if (h.startsWith('#')) h = h.substring(1);
    if (h.length == 6) h = 'FF$h';
    return Color(int.parse(h, radix: 16));
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      backgroundColor: theme.colorScheme.background,
      body: SafeArea(
        child: Stack(
          children: [
            // zarter Hintergrund-Gradient
            Positioned.fill(
              child: IgnorePointer(
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: [
                        Colors.white.withOpacity(0.6),
                        theme.colorScheme.background,
                        Colors.white.withOpacity(0.5),
                      ],
                    ),
                  ),
                ),
              ),
            ),

            // Inhalt
            Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 980),
                child: ListView(
                  padding:
                  const EdgeInsets.symmetric(horizontal: 20, vertical: 18),
                  children: [
                    // Header mit Logo
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.center,
                      children: [
                        ClipRRect(
                          borderRadius: BorderRadius.circular(12),
                          child: Image.asset(
                            'assets/logo.png', // <— hier dein Logo
                            key: UniqueKey(),
                            width: 56,
                            height: 56,
                          ),
                        ),
                        const SizedBox(width: 14),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text('Colours of Wine',
                                  style: theme.textTheme.headlineMedium!
                                      .copyWith(
                                      letterSpacing: 0.2,
                                      fontWeight: FontWeight.w700)),
                            ],
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 18),

                    // Eingabekarte
                    Card(
                      margin: EdgeInsets.zero,
                      child: Padding(
                        padding: const EdgeInsets.all(18.0),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text('Weinname (z. B. „Tignanello 2021“)',
                                style: theme.textTheme.labelLarge),
                            const SizedBox(height: 8),
                            Row(
                              children: [
                                Expanded(
                                  child: TextField(
                                    controller: _controller,
                                    textInputAction: TextInputAction.search,
                                    onSubmitted: (_) => _analyzeHeuristic(),
                                    decoration: const InputDecoration(
                                      hintText:
                                      'LES MOUGEOTTES PINOT NOIR 2024',
                                    ),
                                  ),
                                ),
                                const SizedBox(width: 12),
                                FilledButton.icon(
                                  onPressed: _loading ? null : _analyzeHeuristic,
                                  icon: const Icon(Icons.analytics_outlined),
                                  label: const Text('Analysieren'),
                                ),
                                const SizedBox(width: 8),
                                FilledButton.tonalIcon(
                                  onPressed: _loading ? null : _analyzeWithLLM,
                                  icon: const Icon(Icons.auto_fix_high_outlined),
                                  label: const Text('Daten mittels LLM ergänzen'),
                                ),
                                const SizedBox(width: 8),
                                OutlinedButton.icon(
                                  onPressed:
                                  (_viz != null || _hexForViz != null)
                                      ? _openViz
                                      : null,
                                  icon:
                                  const Icon(Icons.auto_graph_outlined),
                                  label:
                                  const Text('Visualisierung generieren'),
                                ),
                              ],
                            ),
                            if (_loading) ...[
                              const SizedBox(height: 12),
                              const LinearProgressIndicator(minHeight: 3),
                            ],
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 16),

                    // Ergebnisse
                    if (_props != null || _note != null)
                      _ResultCard(
                        props: _props,
                        sources: _sources,
                        hex: _hexForViz,
                        note: _note,
                        notes: _notes,
                        usedLLM: _usedLLM,
                        searchedQuery: _searchedQuery,
                      ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ResultCard extends StatelessWidget {
  final Map<String, dynamic>? props;
  final List<Map<String, dynamic>> sources;
  final String? hex;
  final String? note;
  final List<String> notes;
  final String? searchedQuery;
  final bool usedLLM;

  const _ResultCard({
    required this.props,
    required this.sources,
    required this.hex,
    required this.note,
    required this.notes,
    required this.usedLLM,
    required this.searchedQuery,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final hasProps = props != null && props!.isNotEmpty;

    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(18, 16, 18, 18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Titelzeile
            Row(
              children: [
                Text('Eigenschaften', style: theme.textTheme.titleMedium),
                const SizedBox(width: 10),
                Container(
                  padding:
                  const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(
                    color: usedLLM
                        ? Colors.green.withOpacity(0.10)
                        : Colors.black.withOpacity(0.06),
                    borderRadius: BorderRadius.circular(999),
                    border: Border.all(
                      color: usedLLM
                          ? Colors.green.withOpacity(0.35)
                          : Colors.black.withOpacity(0.12),
                    ),
                  ),
                  child: Text(
                    usedLLM ? 'LLM aktiv' : 'ohne LLM',
                    style: TextStyle(
                      color: usedLLM ? Colors.green.shade800 : Colors.black87,
                      fontSize: 12.5,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
                const Spacer(),
                if ((searchedQuery ?? '').isNotEmpty)
                  Opacity(
                    opacity: 0.7,
                    child: Text(
                      'Such-Query: "${searchedQuery!}"',
                      style: theme.textTheme.labelSmall,
                    ),
                  ),
              ],
            ),
            const SizedBox(height: 14),

            // Tabelle
            DecoratedBox(
              decoration: BoxDecoration(
                border: Border.all(color: Colors.black.withOpacity(0.06)),
                borderRadius: BorderRadius.circular(16),
              ),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(16),
                child: Column(
                  children: [
                    _row('Jahrgang', _fmt(props?['vintage'])),
                    _row('Typ', _fmt(props?['wine_type'])),
                    _row('Rebsorte', _fmt(props?['variety'])),
                    _row('Trauben', _list(props?['grapes'])),
                    _row('Land', _fmt(props?['country'])),
                    _row('Region', _fmt(props?['region'])),
                    _row('Appellation', _fmt(props?['appellation'])),
                    _row('Produzent', _fmt(props?['producer'])),
                    _row('Stil', _fmt(props?['style'])),
                    _row('Süße', _fmt(props?['sweetness'])),
                    _row('Alkohol %', _fmt(props?['alcohol'])),
                    _row('Eiche', _fmt(props?['oak'])),
                    _row('Aromen', _list(props?['tasting_notes'])),
                  ],
                ),
              ),
            ),

            const SizedBox(height: 18),
            Text('Hinweise', style: theme.textTheme.titleSmall),
            const SizedBox(height: 6),
            if (notes.isNotEmpty)
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: notes.map((n) => Text('• $n')).toList(),
              )
            else
              Text((note?.trim().isNotEmpty ?? false) ? note!.trim() : '—'),

            const SizedBox(height: 18),
            Text('Quellen', style: theme.textTheme.titleSmall),
            const SizedBox(height: 6),
            if (sources.isEmpty)
              const Text('– keine –'),
            for (final s in sources)
              _SourceTile(
                title: (s['title'] ?? '').toString(),
                snippet: (s['snippet'] ?? '').toString(),
                url: (s['url'] ?? '').toString(),
              ),
          ],
        ),
      ),
    );
  }

  Widget _row(String left, String right) {
    final isEmpty = right.isEmpty;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: Colors.black.withOpacity(0.02),
        border: Border(
          bottom: BorderSide(color: Colors.black.withOpacity(0.06)),
        ),
      ),
      child: Row(
        children: [
          SizedBox(
            width: 140,
            child: Text(left,
                style:
                const TextStyle(fontWeight: FontWeight.w600, height: 1.2)),
          ),
          const SizedBox(width: 8),
          Expanded(child: Text(isEmpty ? '—' : right)),
        ],
      ),
    );
  }

  String _fmt(dynamic v) => v == null ? '' : v.toString();
  String _list(dynamic v) {
    if (v is List && v.isNotEmpty) return v.join(', ');
    return _fmt(v);
  }
}

class _SourceTile extends StatelessWidget {
  final String title;
  final String snippet;
  final String url;
  const _SourceTile({
    required this.title,
    required this.snippet,
    required this.url,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white,
        border: Border.all(color: Colors.black.withOpacity(0.06)),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (title.isNotEmpty)
            Text(title, style: theme.textTheme.titleSmall),
          if (snippet.isNotEmpty) ...[
            const SizedBox(height: 4),
            Text(snippet, style: TextStyle(color: Colors.black.withOpacity(0.75))),
          ],
          if (url.isNotEmpty) ...[
            const SizedBox(height: 4),
            SelectableText(
              url,
              style: const TextStyle(
                color: Colors.blueAccent,
                decoration: TextDecoration.underline,
              ),
            ),
          ],
        ],
      ),
    );
  }
}
