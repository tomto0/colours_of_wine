import 'dart:math';
import 'dart:ui';
import 'package:flutter/material.dart';

/// Ein (optionales) Weinprofil. Werte 0..1.
/// Falls du später echte Werte aus dem Backend bekommst, einfach hier befüllen.
class WineProfile {
  final Color baseColor;      // „Farbe/Intensität“ – möglichst echte Weinfarbe
  final double acidity;       // Säure (0..1) – steuert grünen Rand
  final double body;          // Körper/Volumen (0..1) – verstärkt Sättigung
  final double tannin;        // Tannin (0..1) – Ring-Textur
  final double depth;         // Tiefe/Komplexität (0..1) – Abdunklung zur Mitte
  final double sweetness;     // Süße (0..1) – seitlicher Balken
  final double oak;           // Holzeinsatz (0..1) – warme Ecken
  final bool bubbles;         // Perlage (Schaumwein)
  final List<_AromaHint> nonFruit; // Nicht-Frucht-Komponenten (kleine Marker)
  final List<_AromaHint> fruit;    // Fruchtcharakter (kleine Marker)

  const WineProfile({
    required this.baseColor,
    this.acidity = 0.4,
    this.body = 0.4,
    this.tannin = 0.2,
    this.depth = 0.4,
    this.sweetness = 0.0,
    this.oak = 0.0,
    this.bubbles = false,
    this.nonFruit = const [],
    this.fruit = const [],
  });

  /// Grobe Heuristik aus Basisfarbe:
  /// - hell & gelbgrün => eher Weiß: hohe Säure, wenig Tannin/Body, wenig Oak
  /// - rubin/rot & dunkler => eher Rot: mehr Tannin/Body/Tiefe, weniger Säure
  factory WineProfile.fromBaseColor(Color c) {
    final hsl = HSLColor.fromColor(c);
    final light = hsl.lightness; // 0..1
    final hue = hsl.hue;         // 0..360

    bool isWhite = light > 0.65 && (hue >= 40 && hue <= 120);   // gelbgrün–gelb
    bool isRose  = light > 0.6 && (hue >= 330 || hue <= 30);    // rosa–lachs
    bool isRed   = !isWhite && !isRose;

    double acidity  = isWhite ? 0.75 : (isRose ? 0.55 : 0.35);
    double body     = isRed   ? 0.65 : (isRose ? 0.45 : 0.35);
    double tannin   = isRed   ? 0.55 : (isRose ? 0.25 : 0.05);
    double depth    = isRed   ? 0.60 : (isRose ? 0.40 : 0.35);
    double sweetness= 0.10; // default: trocken bis feinherb
    double oak      = 0.10; // default: wenig Holz

    return WineProfile(
      baseColor: c,
      acidity: acidity,
      body: body,
      tannin: tannin,
      depth: depth,
      sweetness: sweetness,
      oak: oak,
      bubbles: false,
      nonFruit: const [],
      fruit: const [],
    );
  }
}

class _AromaHint {
  final Offset polar; // r in [0..1], phi in rad
  final Color color;
  const _AromaHint(this.polar, this.color);
}

/// Haupt-Widget: zeichnet die Kreisvisualisierung im Quadrat.
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
      aspectRatio: 3 / 1.2, // breite Bühne; kannst du auf 1/1 ändern
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

    // Hintergrund (heller, neutral)
    final bg = Paint()..color = const Color(0xFFF6EEF6);
    canvas.drawRRect(r, bg);

    // Zeichenfläche für den Kreis
    final circleRect = Rect.fromLTWH(
      12, 12, size.height - 24, size.height - 24,
    );
    final cx = circleRect.center.dx;
    final cy = circleRect.center.dy;
    final radius = circleRect.width / 2;

    // 1) Basisfarbe als konzentrischer Verlauf von Rand (heller) nach innen
    //    Körper/Body erhöht Sättigung, Tiefe dunkelt Zentrum ab. (PDF: Farbe/Intensität & Tiefe). :contentReference[oaicite:1]{index=1}
    final base = HSLColor.fromColor(p.baseColor);
    Color ring(int i, int n, double darken) {
      final t = i / (n - 1);
      final satBoost = 0.15 * p.body;
      final l = (base.lightness * (0.95 - 0.20 * t)).clamp(0.0, 1.0);
      final s = (base.saturation + satBoost).clamp(0.0, 1.0);
      final d = (t * p.depth * darken);
      return base.withSaturation(s).withLightness(max(0.0, l - d)).toColor();
    }

    for (int i = 0; i < 14; i++) {
      final paint = Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = radius / 14
        ..color = ring(i, 14, 0.55);
      canvas.drawCircle(Offset(cx, cy), radius - i * (radius / 14), paint);
    }

    // 2) Säure: zartes grün-gelb am äußeren Rand (breiter bei hoher Säure). (PDF: Säure -> gelbgrün/grün Rand). :contentReference[oaicite:2]{index=2}
    if (p.acidity > 0.02) {
      final acidWidth = lerpDouble(4, radius * 0.20, p.acidity)!;
      final acid = Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = acidWidth
        ..shader = RadialGradient(
          colors: [
            const Color(0xFF8BC34A).withOpacity(0.30),
            const Color(0xFFCDDC39).withOpacity(0.18),
            Colors.transparent,
          ],
          stops: const [0.2, 0.6, 1.0],
        ).createShader(circleRect.inflate(acidWidth));
      canvas.drawCircle(Offset(cx, cy), radius, acid);
    }

    // 3) Tannin: feines „Gitter“ als Ring (haptische Textur). (PDF: Tannin -> Ring/Struktur). :contentReference[oaicite:3]{index=3}
    if (p.tannin > 0.02) {
      final ringW = lerpDouble(radius * 0.02, radius * 0.10, p.tannin)!;
      final ringR = radius * (0.55 + 0.25 * p.tannin);
      final grid = Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = ringW
        ..color = Colors.black.withOpacity(0.07 + 0.18 * p.tannin);
      canvas.drawCircle(Offset(cx, cy), ringR, grid);

      // leichte Kreuzschraffur:
      final dash = max(2.0, ringW * 0.35);
      for (double a = 0; a < 2 * pi; a += pi / 24) {
        final sx = cx + ringR * cos(a);
        final sy = cy + ringR * sin(a);
        final ex = cx + (ringR - dash) * cos(a);
        final ey = cy + (ringR - dash) * sin(a);
        canvas.drawLine(Offset(sx, sy), Offset(ex, ey), grid);
      }
    }

    // 4) Holzeinsatz: warme, goldbraune Ecken, von außen sanft einfallend. (PDF: Holzeinsatz über Ecken/Töne). :contentReference[oaicite:4]{index=4}
    if (p.oak > 0.02) {
      final oakPaint = Paint()
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 24);
      final oakColor = const Color(0xFFB07A3E).withOpacity(0.12 + 0.30 * p.oak);
      final s = min(size.height * 0.35, size.width * 0.25);
      for (final corner in [
        Offset(0, 0),
        Offset(size.width - s, 0),
        Offset(0, size.height - s),
        Offset(size.width - s, size.height - s),
      ]) {
        oakPaint.color = oakColor;
        canvas.drawRRect(
          RRect.fromRectAndRadius(Rect.fromLTWH(corner.dx, corner.dy, s, s),
              Radius.circular(s * 0.25)),
          oakPaint,
        );
      }
    }

    // 5) Perlage/Bubbles: kleine Kreise am Rand, steigen leicht nach oben. (PDF: Mousseux/Perlage). :contentReference[oaicite:5]{index=5}
    if (p.bubbles) {
      final rnd = Random(42);
      final bubbles = Paint()..color = Colors.white.withOpacity(0.7);
      for (int i = 0; i < 60; i++) {
        final a = -pi / 2 + rnd.nextDouble() * pi;      // linker/rechter Aufstieg
        final rr = radius * (0.70 + rnd.nextDouble() * 0.28);
        final o = Offset(cx + rr * cos(a), cy + rr * sin(a));
        final rSmall = 1.5 + rnd.nextDouble() * 2.0;
        canvas.drawCircle(o, rSmall, bubbles);
      }
    }

    // 6) Aroma-Marker (Frucht / Nicht-Frucht) – optional farbige Punkte.
    void drawHints(List<_AromaHint> hints) {
      for (final h in hints) {
        final rr = radius * h.polar.dx;
        final a = h.polar.dy;
        final o = Offset(cx + rr * cos(a), cy + rr * sin(a));
        final paint = Paint()
          ..color = h.color.withOpacity(0.85)
          ..style = PaintingStyle.fill;
        canvas.drawCircle(o, 4, paint);
      }
    }
    drawHints(p.fruit);
    drawHints(p.nonFruit);
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
        final w = 10.0;
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
    final bar = Paint()
      ..shader = const LinearGradient(
        begin: Alignment.bottomCenter,
        end: Alignment.topCenter,
        colors: [Color(0xFFE91E63), Color(0xFFFFC0CB)],
      ).createShader(Offset.zero & size);

    final rect = Offset.zero & size;
    canvas.drawRRect(
      RRect.fromRectAndRadius(rect, const Radius.circular(8)),
      bg,
    );

    final fill = Rect.fromLTWH(
      0,
      size.height * (1 - v),
      size.width,
      size.height * v,
    );
    canvas.drawRRect(
      RRect.fromRectAndRadius(fill, const Radius.circular(8)),
      bar,
    );
  }

  @override
  bool shouldRepaint(covariant _SweetnessPainter old) => old.v != v;
}
