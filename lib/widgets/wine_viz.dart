// lib/widgets/wine_viz.dart
import 'dart:math';
import 'dart:ui';
import 'package:flutter/material.dart';

/// Weinprofil – Werte 0..1.
/// Wird entweder direkt aus LLM-`viz` gebaut, oder heuristisch aus Farbe.
class WineProfile {
  final Color baseColor;      // echte Weinfarbe
  final double acidity;       // Säure
  final double body;          // Körper/Balance/Textureindruck
  final double tannin;        // Tannin
  final double depth;         // Tiefe/Komplexität/Nachhall
  final double sweetness;     // Süße
  final double oak;           // Holzeinsatz
  final bool bubbles;         // Mousseux/Perlage
  final double mineral;       // Mineralik
  final double ripeAromas;    // Reifearomen
  final List<String> fruit;   // Früchte
  final List<String> nonFruit;// Nicht-Frucht-Komponenten

  const WineProfile({
    required this.baseColor,
    this.acidity = 0.4,
    this.body = 0.4,
    this.tannin = 0.2,
    this.depth = 0.4,
    this.sweetness = 0.1,
    this.oak = 0.1,
    this.bubbles = false,
    this.mineral = 0.2,
    this.ripeAromas = 0.2,
    this.fruit = const [],
    this.nonFruit = const [],
  });

  factory WineProfile.fromBaseColor(Color c) {
    final hsl = HSLColor.fromColor(c);
    final light = hsl.lightness;
    final hue = hsl.hue;
    final isWhite = light > 0.65 && (hue >= 40 && hue <= 120);
    final isRose  = light > 0.6 && (hue >= 330 || hue <= 30);
    final isRed   = !isWhite && !isRose;

    double acidity  = isWhite ? 0.75 : (isRose ? 0.55 : 0.35);
    double body     = isRed   ? 0.65 : (isRose ? 0.45 : 0.35);
    double tannin   = isRed   ? 0.55 : (isRose ? 0.25 : 0.05);
    double depth    = isRed   ? 0.60 : (isRose ? 0.40 : 0.35);

    return WineProfile(
      baseColor: c,
      acidity: acidity,
      body: body,
      tannin: tannin,
      depth: depth,
      sweetness: 0.10,
      oak: 0.10,
      mineral: isWhite ? 0.35 : 0.25,
      ripeAromas: isRed ? 0.35 : 0.20,
    );
  }

  static Color _colorFromHex(String hex) {
    var h = hex.trim();
    if (h.startsWith('#')) h = h.substring(1);
    if (h.length == 6) h = 'FF$h';
    return Color(int.parse(h, radix: 16));
  }

  /// Baut ein Profil direkt aus dem Backend-"viz"-Block (LLM-Ausgabe).
  factory WineProfile.fromLLMMap(Map<String, dynamic> m, {String? fallbackHex}) {
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

    return WineProfile(
      baseColor: base,
      acidity: _f('acidity', 0.4),
      body: _f('body', 0.4),
      tannin: _f('tannin', 0.2),
      depth: _f('depth', 0.4),
      sweetness: _f('sweetness', 0.1),
      oak: _f('oak', 0.1),
      mineral: _f('mineral', 0.2),
      ripeAromas: _f('ripe_aromas', 0.2),
      bubbles: (m['bubbles'] == true),
      fruit: (m['fruit'] is List) ? (m['fruit'] as List).map((e) => e.toString()).toList() : const [],
      nonFruit: (m['non_fruit'] is List) ? (m['non_fruit'] as List).map((e) => e.toString()).toList() : const [],
    );
  }
}

/// Haupt-Widget: zeichnet die Kreisvisualisierung als Vollringe.
class WineViz extends StatelessWidget {
  final WineProfile profile;
  final double padding;
  final double cornerRadius;

  const WineViz({
    super.key,
    required this.profile,
    this.padding = 16,
    this.cornerRadius = 28,
  });

  @override
  Widget build(BuildContext context) {
    return AspectRatio(
      aspectRatio: 1, // perfekter Kreis
      child: CustomPaint(
        painter: _WinePainter(profile, cornerRadius: cornerRadius),
        child: Padding(
          padding: EdgeInsets.only(right: max(8, padding / 2)),
          child: Align(
            alignment: Alignment.centerRight,
            child: _SweetnessBar(value: profile.sweetness),
          ),
        ),
      ),
    );
  }
}

class _WinePainter extends CustomPainter {
  final WineProfile p;
  final double cornerRadius;
  _WinePainter(this.p, {required this.cornerRadius});

  @override
  void paint(Canvas canvas, Size size) {
    final rect = Offset.zero & size;
    final r = RRect.fromRectAndRadius(rect, Radius.circular(cornerRadius));
    final bg = Paint()..color = const Color(0xFFF6EEF6);
    canvas.drawRRect(r, bg);

    // runder Zeichenbereich
    final margin = 14.0;
    final d = size.shortestSide - 2 * margin;
    final circleRect = Rect.fromLTWH(
      (size.width - d) / 2, (size.height - d) / 2, d, d,
    );
    final cx = circleRect.center.dx;
    final cy = circleRect.center.dy;
    final radius = circleRect.width / 2;

    // Hilfsfunktionen
    void ring(double outerR, double thickness, Paint paint) {
      canvas.drawCircle(Offset(cx, cy), outerR - thickness / 2, paint..style = PaintingStyle.stroke..strokeWidth = thickness);
    }

    Color _blend(Color c, double satMul, double lightMul) {
      final h = HSLColor.fromColor(c);
      final s = (h.saturation * satMul).clamp(0.0, 1.0);
      final l = (h.lightness * lightMul).clamp(0.0, 1.0);
      return h.withSaturation(s).withLightness(l).toColor();
    }

    // Ringe von außen nach innen (deiner Liste folgend)
    // 1) Farbe/Intensität – breiter äußerer Verlauf
    final base = p.baseColor;
    final ringCount = 12;
    final ringSpacing = radius / (ringCount + 2);
    double currentR = radius;

    {
      final grad = RadialGradient(
        colors: [
          _blend(base, 0.9 + 0.4 * p.body, 1.02),
          _blend(base, 1.05 + 0.6 * p.body, 0.75 - 0.25 * p.depth),
        ],
      ).createShader(circleRect);
      final paint = Paint()..shader = grad..style = PaintingStyle.stroke;
      ring(currentR, ringSpacing * 1.6, paint);
      currentR -= ringSpacing * 1.6;
    }

    // 2) Mousseux/Perlage – dünner heller Ring + feine Bläschen
        {
      final w = ringSpacing * 0.6;
      final paint = Paint()
        ..color = Colors.white.withOpacity(p.bubbles ? 0.45 : 0.15)
        ..style = PaintingStyle.stroke;
      ring(currentR, w, paint);
      if (p.bubbles) {
        final rnd = Random(7);
        final bubPaint = Paint()..color = Colors.white.withOpacity(0.7);
        final rr = currentR - w / 2;
        for (int i = 0; i < 70; i++) {
          final a = rnd.nextDouble() * 2 * pi;
          final rSmall = 1 + rnd.nextDouble() * 2.3;
          final o = Offset(cx + rr * cos(a), cy + rr * sin(a));
          canvas.drawCircle(o, rSmall, bubPaint);
        }
      }
      currentR -= w - 1;
    }

    // 3) Säure – grün/gelblich leuchtender Ring
        {
      final w = ringSpacing * 0.9;
      final paint = Paint()
        ..shader = SweepGradient(
          colors: [
            const Color(0xFF9CCC65).withOpacity(0.18 + 0.5 * p.acidity),
            const Color(0xFFCDDC39).withOpacity(0.10 + 0.35 * p.acidity),
          ],
        ).createShader(circleRect);
      ring(currentR, w, paint);
      currentR -= w - 1;
    }

    // 4) Fruchtcharakter – kleine Marker (hell)
        {
      final w = ringSpacing * 0.8;
      final line = Paint()
        ..color = Colors.white.withOpacity(0.10)
        ..style = PaintingStyle.stroke;
      ring(currentR, w, line);

      final rr = currentR - w / 2;
      final dot = Paint()..color = Colors.white.withOpacity(0.8);
      for (int i = 0; i < max(6, p.fruit.length * 2); i++) {
        final a = (i / max(6, p.fruit.length * 2)) * 2 * pi;
        final o = Offset(cx + rr * cos(a), cy + rr * sin(a));
        canvas.drawCircle(o, 2.2, dot);
      }
      currentR -= w - 1;
    }

    // 5) Nicht-Frucht Komponenten – dunklere Marker
        {
      final w = ringSpacing * 0.8;
      final line = Paint()
        ..color = Colors.black.withOpacity(0.08)
        ..style = PaintingStyle.stroke;
      ring(currentR, w, line);

      final rr = currentR - w / 2;
      final dot = Paint()..color = Colors.black.withOpacity(0.20 + 0.25 * p.body);
      for (int i = 0; i < max(6, p.nonFruit.length * 2); i++) {
        final a = (i / max(6, p.nonFruit.length * 2)) * 2 * pi + 0.07;
        final o = Offset(cx + rr * cos(a), cy + rr * sin(a));
        canvas.drawCircle(o, 2.0, dot);
      }
      currentR -= w - 1;
    }

    // 6) Körper/Balance/Textureindruck – satte Tönung
        {
      final w = ringSpacing * 1.2;
      final paint = Paint()
        ..color = _blend(base, 1.0 + 0.8 * p.body, 0.95 - 0.12 * p.body)
        ..style = PaintingStyle.stroke;
      ring(currentR, w, paint);
      currentR -= w - 1;
    }

    // 7) Tannin – texturierter dunkler Ring
        {
      final w = ringSpacing * 1.0;
      final baseC = _blend(base, 0.9, 0.80 - 0.25 * p.tannin);
      final paint = Paint()
        ..color = baseC.withOpacity(0.9)
        ..style = PaintingStyle.stroke;
      ring(currentR, w, paint);

      // feine Striche für „Grip“
      final rr = currentR - w / 2;
      final grid = Paint()
        ..color = Colors.black.withOpacity(0.05 + 0.15 * p.tannin)
        ..strokeWidth = max(1.0, w * 0.06);
      for (double a = 0; a < 2 * pi; a += pi / 24) {
        final sx = cx + rr * cos(a);
        final sy = cy + rr * sin(a);
        final ex = cx + (rr - w * 0.35) * cos(a);
        final ey = cy + (rr - w * 0.35) * sin(a);
        canvas.drawLine(Offset(sx, sy), Offset(ex, ey), grid);
      }
      currentR -= w - 1;
    }

    // 8) Reifearomen – warmes Leuchten
        {
      final w = ringSpacing * 0.9;
      final warm = const Color(0xFFB07A3E).withOpacity(0.10 + 0.35 * p.ripeAromas);
      final paint = Paint()
        ..style = PaintingStyle.stroke
        ..color = warm;
      ring(currentR, w, paint);
      currentR -= w - 1;
    }

    // 9) Tiefe/Komplexität/Nachhall – Abdunklung
        {
      final w = ringSpacing * 1.2;
      final paint = Paint()
        ..color = _blend(base, 0.95, 0.80 - 0.35 * p.depth)
        ..style = PaintingStyle.stroke;
      ring(currentR, w, paint);
      currentR -= w - 1;
    }

    // 10) Mineralik – silbrige Punkte
        {
      final w = ringSpacing * 0.8;
      final line = Paint()
        ..color = Colors.white.withOpacity(0.07)
        ..style = PaintingStyle.stroke;
      ring(currentR, w, line);

      final rr = currentR - w / 2;
      final dot = Paint()..color = const Color(0xFFCFD8DC).withOpacity(0.55 + 0.3 * p.mineral);
      for (int i = 0; i < 28; i++) {
        final a = (i / 28) * 2 * pi + 0.12;
        final o = Offset(cx + rr * cos(a), cy + rr * sin(a));
        canvas.drawCircle(o, 1.8, dot);
      }
      currentR -= w - 1;
    }

    // 11) Holzeinsatz – weiches warmes Inlay (innen)
        {
      final w = ringSpacing * 1.0;
      final oakC = const Color(0xFFB07A3E).withOpacity(0.08 + 0.35 * p.oak);
      final paint = Paint()..color = oakC..style = PaintingStyle.stroke;
      ring(currentR, w, paint);
      currentR -= w - 1;
    }

    // innerer Kern: sanft abgedunkelt
    final core = Paint()
      ..shader = RadialGradient(
        colors: [
          _blend(base, 1.0, 0.95),
          _blend(base, 0.95, 0.72 - 0.25 * p.depth),
        ],
      ).createShader(Rect.fromCircle(center: Offset(cx, cy), radius: currentR));
    canvas.drawCircle(Offset(cx, cy), currentR, core);
  }

  @override
  bool shouldRepaint(covariant _WinePainter old) => old.p != p;
}

class _SweetnessBar extends StatelessWidget {
  final double value; // 0..1
  const _SweetnessBar({required this.value});

  @override
  Widget build(BuildContext context) {
    final v = value.clamp(0.0, 1.0);
    return LayoutBuilder(
      builder: (context, bc) {
        final h = bc.maxHeight;
        const w = 14.0;
        return CustomPaint(
          size: Size(w, h),
          painter: _SweetnessPainter(v),
        );
      },
    );
  }
}

class _SweetnessPainter extends CustomPainter {
  final double v;
  _SweetnessPainter(this.v);

  @override
  void paint(Canvas canvas, Size size) {
    final bg = Paint()..color = Colors.black.withOpacity(0.06);
    final rect = Offset.zero & size;
    canvas.drawRRect(RRect.fromRectAndRadius(rect, const Radius.circular(9)), bg);

    final grad = const LinearGradient(
      begin: Alignment.bottomCenter,
      end: Alignment.topCenter,
      colors: [Color(0xFFE91E63), Color(0xFFFFC0CB)],
    ).createShader(rect);

    final bar = Paint()..shader = grad;
    final fill = Rect.fromLTWH(
      0, size.height * (1 - v), size.width, size.height * v,
    );
    canvas.drawRRect(RRect.fromRectAndRadius(fill, const Radius.circular(9)), bar);
  }

  @override
  bool shouldRepaint(covariant _SweetnessPainter old) => old.v != v;
}
