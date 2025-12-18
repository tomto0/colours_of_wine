// lib/widgets/wine_viz.dart
import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

/// Weinprofil – Werte 0..1.
/// Wird entweder direkt aus LLM-`viz` gebaut, oder heuristisch aus Farbe.
class WineProfile {
  final Color baseColor; // echte Weinfarbe
  final double acidity; // Säure
  final double body; // Körper/Balance/Textureindruck
  final double depth; // Tiefe/Komplexität/Nachhall
  final double oak; // Holzeinsatz
  final double mineral; // Mineralik
  
  // Aromatik-Felder für imagegen
  final double spice;
  final double herbs;
  final double fruitCitrus;
  final double fruitStone;
  final double fruitTropical;
  final double fruitRed;
  final double fruitDark;
  final double effervescence;
  final double residualSugar; // Restzucker in g/L
  final String wineType; // "red", "white", "rose", "auto"
  
  // Die Zusammenfassung für die Visualisierung
  final String? summary;

  const WineProfile({
    required this.baseColor,
    this.acidity = 0.4,
    this.body = 0.4,
    this.depth = 0.4,
    this.oak = 0.1,
    this.mineral = 0.2,
    this.spice = 0.0,
    this.herbs = 0.0,
    this.fruitCitrus = 0.0,
    this.fruitStone = 0.0,
    this.fruitTropical = 0.0,
    this.fruitRed = 0.0,
    this.fruitDark = 0.0,
    this.effervescence = 0.0,
    this.residualSugar = 0.0,
    this.wineType = "auto",
    this.summary,
  });

  /// Hex-String für die Basis-Farbe
  String get baseColorHex {
    final c = baseColor;
    return '#${c.red.toRadixString(16).padLeft(2, '0')}'
           '${c.green.toRadixString(16).padLeft(2, '0')}'
           '${c.blue.toRadixString(16).padLeft(2, '0')}';
  }

  factory WineProfile.fromBaseColor(Color c) {
    final hsl = HSLColor.fromColor(c);
    final light = hsl.lightness;
    final hue = hsl.hue;
    final isWhite = light > 0.65 && (hue >= 40 && hue <= 120);
    final isRose = light > 0.6 && (hue >= 330 || hue <= 30);
    final isRed = !isWhite && !isRose;

    double acidity = isWhite ? 0.75 : (isRose ? 0.55 : 0.35);
    double body = isRed ? 0.65 : (isRose ? 0.45 : 0.35);
    double depth = isRed ? 0.60 : (isRose ? 0.40 : 0.35);
    
    String wineType = isRed ? "red" : (isRose ? "rose" : "white");

    return WineProfile(
      baseColor: c,
      acidity: acidity,
      body: body,
      depth: depth,
      oak: 0.10,
      mineral: isWhite ? 0.35 : 0.25,
      wineType: wineType,
      fruitRed: isRed ? 0.5 : 0.0,
      fruitDark: isRed ? 0.4 : 0.0,
      fruitCitrus: isWhite ? 0.5 : 0.0,
      fruitStone: isWhite ? 0.4 : (isRose ? 0.3 : 0.0),
    );
  }

  static Color _colorFromHex(String hex) {
    var h = hex.trim();
    if (h.startsWith('#')) h = h.substring(1);
    if (h.length == 6) h = 'FF$h';
    return Color(int.parse(h, radix: 16));
  }

  /// Baut ein Profil direkt aus dem Backend-"viz"-Block (LLM-Ausgabe).
  factory WineProfile.fromLLMMap(Map<String, dynamic> m, {String? fallbackHex, String? summary}) {
    Color base = const Color(0xFFF6F2AF);
    final hx = (m['base_color_hex'] ?? fallbackHex)?.toString();
    if (hx != null && hx.isNotEmpty) {
      base = _colorFromHex(hx);
    }

    double _f(String k, double d) {
      final v = m[k];
      if (v is num) return v.clamp(0.0, 1.0).toDouble();
      return d;
    }
    
    // Für Werte die nicht 0-1 begrenzt sind (z.B. residual_sugar in g/L)
    double _fRaw(String k, double d) {
      final v = m[k];
      if (v is num) return v.toDouble();
      return d;
    }
    
    // Weintyp bestimmen
    String wineType = (m['wine_type'] ?? 'auto').toString();
    if (wineType.isEmpty) wineType = 'auto';

    // effervescence aus bubbles ableiten falls nicht explizit gesetzt
    double effervescence = _f('effervescence', 0.0);
    if (effervescence == 0.0 && m['bubbles'] == true) {
      effervescence = 0.7;
    }

    return WineProfile(
      baseColor: base,
      acidity: _f('acidity', 0.4),
      body: _f('body', 0.4),
      depth: _f('depth', 0.4),
      oak: _f('oak_intensity', _f('oak', 0.1)),
      mineral: _f('mineral_intensity', _f('mineral', 0.2)),
      spice: _f('spice_intensity', 0.0),
      herbs: _f('herbal_intensity', 0.0),
      fruitCitrus: _f('fruit_citrus', 0.0),
      fruitStone: _f('fruit_stone', 0.0),
      fruitTropical: _f('fruit_tropical', 0.0),
      fruitRed: _f('fruit_red', 0.0),
      fruitDark: _f('fruit_dark', 0.0),
      effervescence: effervescence,
      residualSugar: _fRaw('residual_sugar', 0.0), // g/L, nicht 0-1!
      wineType: wineType,
      summary: summary,
    );
  }
}

/// Haupt-Widget: lädt die Visualisierung vom Backend.
class WineViz extends StatefulWidget {
  final WineProfile profile;
  final double cornerRadius;

  const WineViz({
    super.key,
    required this.profile,
    this.cornerRadius = 28,
  });

  @override
  State<WineViz> createState() => _WineVizState();
}

class _WineVizState extends State<WineViz> {
  Uint8List? _imageBytes;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadImage();
  }

  @override
  void didUpdateWidget(WineViz oldWidget) {
    super.didUpdateWidget(oldWidget);
    // Wenn sich das Profil ändert, neu laden
    if (oldWidget.profile != widget.profile) {
      _loadImage();
    }
  }

  Future<void> _loadImage() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final p = widget.profile;
      final payload = {
        'base_color_hex': p.baseColorHex,
        'acidity': p.acidity,
        'body': p.body,
        'depth': p.depth,
        'oak_intensity': p.oak,
        'mineral_intensity': p.mineral,
        'herbal_intensity': p.herbs,
        'spice_intensity': p.spice,
        'fruit_citrus': p.fruitCitrus,
        'fruit_stone': p.fruitStone,
        'fruit_tropical': p.fruitTropical,
        'fruit_red': p.fruitRed,
        'fruit_dark': p.fruitDark,
        'effervescence': p.effervescence,
        'residual_sugar': p.residualSugar,
        'wine_type': p.wineType,
        'size': 512,
      };
      
      // Die Zusammenfassung hinzufügen, wenn vorhanden
      if (p.summary != null && p.summary!.isNotEmpty) {
        payload['summary'] = p.summary!;
      }
      
      final response = await http.post(
        Uri.parse('http://127.0.0.1:8000/generate-viz'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(payload),
      );

      if (response.statusCode == 200) {
        setState(() {
          _imageBytes = response.bodyBytes;
          _loading = false;
        });
      } else {
        setState(() {
          _error = 'Server-Fehler: ${response.statusCode}';
          _loading = false;
        });
      }
    } catch (e) {
      setState(() {
        _error = 'Verbindungsfehler: $e';
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return AspectRatio(
      aspectRatio: 1,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(widget.cornerRadius),
        child: Container(
          color: const Color(0xFFFCFCFE),
          child: _buildContent(),
        ),
      ),
    );
  }

  Widget _buildContent() {
    if (_loading) {
      return const Center(
        child: CircularProgressIndicator(),
      );
    }

    if (_error != null) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.error_outline, size: 48, color: Colors.red),
            const SizedBox(height: 12),
            Text(_error!, textAlign: TextAlign.center),
            const SizedBox(height: 12),
            ElevatedButton(
              onPressed: _loadImage,
              child: const Text('Erneut versuchen'),
            ),
          ],
        ),
      );
    }

    if (_imageBytes != null) {
      return Image.memory(
        _imageBytes!,
        fit: BoxFit.cover,
      );
    }

    return const SizedBox.shrink();
  }
}
