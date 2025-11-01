import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

void main() => runApp(const WineVizApp());

class WineVizApp extends StatelessWidget {
  const WineVizApp({super.key});
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Colours of Wine',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.deepPurple),
        useMaterial3: true,
      ),
      home: const WineSearchPage(),
    );
  }
}

class WineSearchPage extends StatefulWidget {
  const WineSearchPage({super.key});
  @override
  State<WineSearchPage> createState() => _WineSearchPageState();
}

class _WineSearchPageState extends State<WineSearchPage> {
  final _name = TextEditingController();
  bool loading = false;
  String? error;
  Map<String, dynamic>? result;

  Future<void> _analyze() async {
    final name = _name.text.trim();
    if (name.isEmpty) {
      setState(() => error = 'Bitte einen Weinnamen eingeben.');
      return;
    }
    setState(() { loading = true; error = null; result = null; });

    final uri = Uri.parse(const String.fromEnvironment(
      'BACKEND_URL', defaultValue: 'http://127.0.0.1:8000/analyze',
    ));

    try {
      final resp = await http.post(
        uri,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({"wine_name": name}),
      );
      if (resp.statusCode == 200) {
        setState(() => result = jsonDecode(resp.body));
      } else {
        setState(() => error = 'Backend-Fehler: ${resp.statusCode}');
      }
    } catch (e) {
      setState(() => error = 'Keine Verbindung zum Backend: $e');
    } finally {
      setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final body = Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          TextField(
            controller: _name,
            decoration: const InputDecoration(
              labelText: 'Weinname (z. B. "Tignanello 2021")',
            ),
            onSubmitted: (_) => _analyze(),
          ),
          const SizedBox(height: 12),
          FilledButton.icon(
            onPressed: loading ? null : _analyze,
            icon: const Icon(Icons.analytics),
            label: const Text('Analysieren'),
          ),
          const SizedBox(height: 12),
          if (loading) const LinearProgressIndicator(),
          if (error != null) Text(error!, style: const TextStyle(color: Colors.red)),
          if (result != null) _ResultCard(result: result!),
        ],
      ),
    );

    return Scaffold(
      appBar: AppBar(title: const Text('Colours of Wine')),
      body: ListView(children: [body]),
    );
  }
}

class _ResultCard extends StatelessWidget {
  final Map<String, dynamic> result;
  const _ResultCard({required this.result});

  @override
  Widget build(BuildContext context) {
    final factors = (result['factors'] as List).cast<Map<String, dynamic>>();
    final labels = factors.map((f) => (f['label'] as String)).toList();
    final values = factors.map((f) => ((f['value'] as num).toDouble())).toList();

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(result['title'] ?? '', style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 4),
          Text(result['summary'] ?? '', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          Text(result['description'] ?? ''),
          const SizedBox(height: 12),
          AspectRatio(
            aspectRatio: 1,
            child: CustomPaint(
              painter: BullseyePainter(
                values: values,
                labels: labels,
                palette: (result['styleHints']?['palette'] as String?) ?? 'warm_red',
              ),
            ),
          ),
          const SizedBox(height: 8),
          if ((result['sources'] as List).isNotEmpty)
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('Quellen:', style: TextStyle(fontWeight: FontWeight.bold)),
                ...((result['sources'] as List).cast<Map<String, dynamic>>()
                    .map((s) => Text('• ${s['title']}${s['url'] != null ? " (${s['url']})" : ""}'))),
              ],
            ),
        ]),
      ),
    );
  }
}

/// Ein Faktor = ein Ring. Intensität ~ Wert [0..1].
class BullseyePainter extends CustomPainter {
  final List<double> values;
  final List<String> labels;
  final String palette;
  BullseyePainter({required this.values, required this.labels, required this.palette});

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = size.shortestSide / 2 * 0.95;
    final ringCount = values.length.clamp(1, 24);
    final ringWidth = radius / ringCount;

    final base = _baseColorForPalette(palette);
    final bg = Paint()..color = Colors.black12;
    canvas.drawRect(Offset.zero & size, bg);

    for (int i = 0; i < ringCount; i++) {
      final rOuter = radius - i * ringWidth;
      final rInner = rOuter - ringWidth * 0.92;
      final v = values[i].clamp(0.0, 1.0);
      final c = base.withOpacity(0.1 + 0.85 * v);
      final paint = Paint()
        ..shader = RadialGradient(
          colors: [c, c.withOpacity((0.4 + 0.5 * v))],
          stops: const [0.3, 1.0],
        ).createShader(Rect.fromCircle(center: center, radius: rOuter));
      final path = Path()
        ..addOval(Rect.fromCircle(center: center, radius: rOuter))
        ..addOval(Rect.fromCircle(center: center, radius: rInner))
        ..fillType = PathFillType.evenOdd;
      canvas.drawPath(path, paint);
    }
  }

  Color _baseColorForPalette(String p) {
    switch (p) {
      case 'warm_red': return Colors.deepOrange;
      case 'cool_green': return Colors.teal;
      case 'gold_white': return Colors.amber;
      default: return Colors.indigo;
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => true;
}
