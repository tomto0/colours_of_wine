// lib/widgets/wine_viz.dart
import 'dart:math';
import 'dart:ui';
import 'package:flutter/material.dart';

/// Weinprofil (alle Werte 0..1, außer baseColor).
/// Reihenfolge der Ringe von außen nach innen:
/// 0 Holzeinsatz/Ausbaustil
/// 1 Farbe/Intensität
/// 2 Mousseux/Perlage/Bubbles
/// 3 Säure
/// 4 Fruchtcharakter
/// 5 Nicht-Frucht Komponenten
/// 6 Körper/Balance/Textur/Struktur
/// 7 Tannin
/// 8 Reifearomen
/// 9 Tiefe/Komplexität/Nachhall
/// 10 Mineralik
/// (Süße als separater Balken)
class WineProfile {
  final Color baseColor;

  final double oak;            // 0..1
  final double colorIntensity; // 0..1
  final bool   bubbles;        // Mousseux
  final double acidity;        // 0..1
  final double fruit;          // 0..1
  final double nonFruit;       // 0..1
  final double body;           // 0..1
  final double tannin;         // 0..1
  final double maturity;       // 0..1
  final double depth;          // 0..1
  final double minerality;     // 0..1
  final double sweetness;      // 0..1 (separat)

  const WineProfile({
    required this.baseColor,
    this.oak = 0.0,
    this.colorIntensity = 0.5,
    this.bubbles = false,
    this.acidity = 0.4,
    this.fruit = 0.4,
    this.nonFruit = 0.3,
    this.body = 0.45,
    this.tannin = 0.25,
    this.maturity = 0.2,
    this.depth = 0.4,
    this.minerality = 0.2,
    this.sweetness = 0.1,
  });

  /// Einfache Heuristik aus der Basisfarbe.
  factory WineProfile.fromBaseColor(Color c) {
    final hsl = HSLColor.fromColor(c);
    final light = hsl.lightness;
    final hue = hsl.hue;

    final isWhite = light > .65 && (hue >= 40 && hue <= 120);
    final isRose  = light > .60 && (hue >= 330 || hue <= 30);
    final isRed   = !isWhite && !isRose;

    return WineProfile(
      baseColor: c,
      acidity: isWhite ? .75 : (isRose ? .55 : .35),
      body:    isRed   ? .65 : (isRose ? .45 : .35),
      tannin:  isRed   ? .55 : (isRose ? .25 : .05),
      depth:   isRed   ? .60 : (isRose ? .40 : .35),
      colorIntensity: isRed ? .70 : .55,
      fruit: isWhite ? .55 : .50,
      nonFruit: isRed ? .40 : .25,
      maturity: isRed ? .35 : .20,
      minerality: isWhite ? .35 : .20,
      sweetness: .10,
      oak: .10,
      bubbles: false,
    );
  }

  /// NEU: aus Backend-`props` + optionalem HEX (Basisfarbe) ableiten.
  /// Erwartete Keys (optional): wine_type, grapes(List), tasting_notes(List),
  /// sweetness(String), oak(bool/num), acidity/fruit/nonFruit/body/tannin/
  /// maturity/depth/minerality (num 0..1 oder 0..100), style(String), hex(String)
  factory WineProfile.fromProps(Map<String, dynamic> props, {String? hex}) {
    Color _colorFromHex(String h) {
      var s = h.trim();
      if (s.startsWith('#')) s = s.substring(1);
      if (s.length == 6) s = 'FF$s';
      return Color(int.parse(s, radix: 16));
    }

    double _norm(dynamic v, {double def = 0.0}) {
      if (v == null) return def;
      if (v is bool) return v ? 0.7 : 0.0;
      if (v is num) {
        var d = v.toDouble();
        if (d > 1.0) d /= 100.0;
        return d.clamp(0.0, 1.0);
      }
      return def;
    }

    // Basisfarbe
    final Color base =
    (hex != null && hex.isNotEmpty) ? _colorFromHex(hex) : const Color(0xFFF6F2AF);

    final wineType = (props['wine_type'] ?? '').toString().toLowerCase();
    final styleStr = (props['style'] ?? '').toString().toLowerCase();

    final List<String> notes = (props['tasting_notes'] is List)
        ? (props['tasting_notes'] as List).map((e) => e.toString().toLowerCase()).toList()
        : const [];

    final List<String> grapes = (props['grapes'] is List)
        ? (props['grapes'] as List).map((e) => e.toString().toLowerCase()).toList()
        : const [];

    // Süße aus String-Kategorie
    double sweetness = (() {
      final s = (props['sweetness'] ?? '').toString().toLowerCase();
      if (s.isEmpty) return 0.1;
      if (s.contains('dry') || s.contains('trocken')) return 0.05;
      if (s.contains('off')) return 0.20; // off-dry, halbtrocken
      if (s.contains('medium')) return 0.45;
      if (s.contains('semi')) return 0.60;
      if (s.contains('sweet') || s.contains('süß')) return 0.90;
      return 0.1;
    })();

    // Bubbles
    final bubbles = styleStr.contains('spark');

    // Oak direkt oder aus Noten ableiten
    double oak = _norm(props['oak'], def: 0.0);
    if (oak == 0.0 && notes.any((n) => n.contains('vanilla') || n.contains('toast') || n.contains('oak'))) {
      oak = 0.6;
    }

    // Acidity ggf. aus Typ ableiten
    double acidity = _norm(props['acidity'], def: 0.0);
    if (acidity == 0.0) {
      acidity = wineType == 'white' ? 0.70 : (wineType == 'rosé' ? 0.55 : 0.40);
    }

    // Körper, Tannin, Tiefe – einfache Heuristiken nach Typ/Rebsorte
    double body   = _norm(props['body'], def: 0.0);
    double tannin = _norm(props['tannin'], def: 0.0);
    double depth  = _norm(props['depth'], def: 0.0);

    if (body == 0.0)  body  = (wineType == 'red') ? 0.60 : (wineType == 'rosé' ? 0.45 : 0.35);
    if (tannin == 0.0) {
      final highTanGrapes = ['nebbiolo', 'sangiovese', 'cabernet', 'syrah'];
      tannin = grapes.any((g) => highTanGrapes.any((h) => g.contains(h))) ? 0.65
          : (wineType == 'red' ? 0.45 : (wineType == 'rosé' ? 0.20 : 0.05));
    }
    if (depth == 0.0) depth = (wineType == 'red') ? 0.55 : (wineType == 'rosé' ? 0.40 : 0.35);

    // Frucht/Nicht-Frucht grob aus Noten
    double fruit = _norm(props['fruit'], def: 0.0);
    double nonFruit = _norm(props['nonFruit'], def: 0.0);
    if (fruit == 0.0) {
      final fruitWords = ['apple','pear','peach','citrus','lemon','lime','apricot',
        'pineapple','cherry','raspberry','strawberry','plum','berry','tropical'];
      fruit = notes.any((n) => fruitWords.any((w) => n.contains(w))) ? 0.6 : 0.4;
    }
    if (nonFruit == 0.0) {
      final nfWords = ['spice','herb','pepper','smoke','earth','leather','tea','graphite'];
      nonFruit = notes.any((n) => nfWords.any((w) => n.contains(w))) ? 0.45 : 0.25;
    }

    // Reife & Mineralik grob aus Noten
    double maturity   = _norm(props['maturity'], def: 0.0);
    double minerality = _norm(props['minerality'], def: 0.0);
    if (maturity == 0.0 && notes.any((n) => n.contains('honey') || n.contains('nut') || n.contains('oxid'))) {
      maturity = 0.5;
    }
    if (minerality == 0.0 && notes.any((n) => n.contains('mineral') || n.contains('slate') || n.contains('stone'))) {
      minerality = 0.45;
    }

    // Farbintensität (Band 1)
    double colorIntensity = _norm(props['color_intensity'], def: 0.0);
    if (colorIntensity == 0.0) {
      colorIntensity = (wineType == 'red') ? 0.70 : 0.55;
    }

    return WineProfile(
      baseColor: base,
      oak: oak,
      colorIntensity: colorIntensity,
      bubbles: bubbles,
      acidity: acidity,
      fruit: fruit,
      nonFruit: nonFruit,
      body: body,
      tannin: tannin,
      maturity: maturity,
      depth: depth,
      minerality: minerality,
      sweetness: sweetness,
    );
  }
}

/// Haupt-Widget (Quadrat-Anmutung; Breite > Höhe erlaubt).
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
      aspectRatio: 3 / 1.2, // breite Bühne (kannst du auf 1/1 ändern)
      child: CustomPaint(
        painter: _RingsPainter(profile, cornerRadius: cornerRadius),
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

/// Zeichnet die 11 Vollringe + Zentrum.
class _RingsPainter extends CustomPainter {
  final WineProfile p;
  final double cornerRadius;
  _RingsPainter(this.p, {required this.cornerRadius});

  @override
  void paint(Canvas canvas, Size size) {
    // Hintergrund
    final rect = Offset.zero & size;
    canvas.drawRRect(
      RRect.fromRectAndRadius(rect, Radius.circular(cornerRadius)),
      Paint()..color = const Color(0xFFF6EEF6),
    );

    // Kreisfläche (etwas Rand lassen)
    final inset = 14.0;
    final circle = Rect.fromLTWH(
      inset, inset, size.height - 2 * inset, size.height - 2 * inset,
    );
    final center = circle.center;
    final outerR = circle.width / 2;

    // Gleich dicke Bänder
    const ringCount = 11; // ohne Süße
    final ringGap = max(outerR * 0.005, 1.0); // dezente Gaps
    final ringThickness = (outerR - ringGap * (ringCount - 1)) / ringCount;

    // Hilfsfunktion: ein kompletter Kreisring
    void ringStroke({
      required double idx, // 0 = äußerster Ring
      required Color color,
      double opacity = 1.0,
      double extraWidth = 0.0,
      StrokeCap cap = StrokeCap.butt,
      BlendMode? blend,
      Shader? shader,
    }) {
      final r = outerR - idx * (ringThickness + ringGap) - ringThickness / 2;
      final paint = Paint()
        ..style = PaintingStyle.stroke
        ..strokeCap = cap
        ..strokeWidth = ringThickness + extraWidth
        ..color = color.withOpacity((color.opacity * opacity).clamp(0, 1));
      if (blend != null) paint.blendMode = blend;
      if (shader != null) paint.shader = shader;
      canvas.drawCircle(center, r, paint);
    }

    // 0) Holz außen
    ringStroke(
      idx: 0,
      color: const Color(0xFFB07A3E),
      opacity: 0.10 + 0.55 * p.oak,
      blend: BlendMode.plus,
    );

    // 1) Farbe/Intensität
    final base = HSLColor.fromColor(p.baseColor);
    final col1 = base
        .withLightness((base.lightness - 0.10 * p.colorIntensity).clamp(0.0, 1))
        .withSaturation((base.saturation + 0.18 * p.colorIntensity).clamp(0.0, 1))
        .toColor();
    ringStroke(idx: 1, color: col1, opacity: 0.95);

    // 2) Bubbles
    if (p.bubbles) {
      final r = outerR - 2 * (ringThickness + ringGap) - ringThickness / 2;
      final paint = Paint()..color = Colors.white.withOpacity(.85);
      final count = 48;
      final rnd = Random(3);
      for (var i = 0; i < count; i++) {
        final a = -pi / 2 + i * (2 * pi / count) + (rnd.nextDouble() - .5) * 0.05;
        final cx = center.dx + r * cos(a);
        final cy = center.dy + r * sin(a);
        final rr = lerpDouble(1.2, 2.6, rnd.nextDouble())!;
        canvas.drawCircle(Offset(cx, cy), rr, paint);
      }
    } else {
      ringStroke(idx: 2, color: Colors.white, opacity: .06, blend: BlendMode.screen);
    }

    // 3) Säure
    final acidShader = SweepGradient(
      colors: [
        const Color(0xFF9CCC65).withOpacity(.22 + .25 * p.acidity),
        const Color(0xFFDCE775).withOpacity(.18 + .20 * p.acidity),
        const Color(0xFF9CCC65).withOpacity(.22 + .25 * p.acidity),
      ],
    ).createShader(circle);
    ringStroke(idx: 3, color: const Color(0xFF9CCC65), opacity: 0.0, shader: acidShader);

    // 4) Frucht
    ringStroke(
      idx: 4,
      color: const Color(0xFFF6A623),
      opacity: .12 + .55 * p.fruit,
      blend: BlendMode.plus,
    );

    // 5) Nicht-Frucht
    ringStroke(
      idx: 5,
      color: const Color(0xFF6D8E72),
      opacity: .10 + .45 * p.nonFruit,
      blend: BlendMode.plus,
    );

    // 6) Körper/Struktur
    final bodyCol = base
        .withSaturation((base.saturation + 0.25 * p.body).clamp(0.0, 1))
        .withLightness((base.lightness - 0.05 * p.body).clamp(0.0, 1))
        .toColor();
    ringStroke(idx: 6, color: bodyCol, opacity: 0.9);

    // 7) Tannin mit Schraffur
    final tanCol = const Color(0xFF55433A).withOpacity(.12 + .45 * p.tannin);
    ringStroke(idx: 7, color: tanCol, opacity: 1.0);
    if (p.tannin > 0.02) {
      final r = outerR - 7 * (ringThickness + ringGap) - ringThickness / 2;
      final w = max(1.0, ringThickness * .08);
      final hatch = Paint()
        ..color = Colors.black.withOpacity(.06 + .18 * p.tannin)
        ..strokeWidth = w;
      for (double a = 0; a < 2 * pi; a += pi / 18) {
        final sx = center.dx + (r + ringThickness * .48) * cos(a);
        final sy = center.dy + (r + ringThickness * .48) * sin(a);
        final ex = center.dx + (r - ringThickness * .48) * cos(a);
        final ey = center.dy + (r - ringThickness * .48) * sin(a);
        canvas.drawLine(Offset(sx, sy), Offset(ex, ey), hatch);
      }
    }

    // 8) Reife
    ringStroke(
      idx: 8,
      color: const Color(0xFFBF8F5E),
      opacity: .10 + .50 * p.maturity,
      blend: BlendMode.plus,
    );

    // 9) Tiefe/Komplexität
    ringStroke(
      idx: 9,
      color: Colors.black,
      opacity: .08 + .30 * p.depth,
      blend: BlendMode.multiply,
    );

    // 10) Mineralik
    final minR = outerR - 10 * (ringThickness + ringGap) - ringThickness / 2;
    final minPaint = Paint()
      ..color = const Color(0xFF82B1FF).withOpacity(.20 + .40 * p.minerality);
    final count = 28;
    for (var i = 0; i < count; i++) {
      final a = i * (2 * pi / count);
      final rr = minR;
      final o = Offset(center.dx + rr * cos(a), center.dy + rr * sin(a));
      canvas.drawCircle(o, 1.8, minPaint);
    }

    // Zentrum
    final core = Paint()
      ..shader = RadialGradient(
        colors: [
          base
              .withLightness((base.lightness - .20 * p.depth).clamp(0.0, 1))
              .withSaturation((base.saturation + .10 * p.body).clamp(0.0, 1))
              .toColor(),
          base.withLightness((base.lightness + .05).clamp(0.0, 1)).toColor(),
        ],
        stops: const [0.0, 1.0],
      ).createShader(Rect.fromCircle(center: center, radius: ringThickness * 2.2));
    canvas.drawCircle(center, ringThickness * 2.2, core);
  }

  @override
  bool shouldRepaint(covariant _RingsPainter old) => old.p != p;
}

/// Süßebalken (separat).
class _SweetnessBar extends StatelessWidget {
  final double value; // 0..1
  const _SweetnessBar({required this.value});

  @override
  Widget build(BuildContext context) {
    final v = value.clamp(0.0, 1.0);
    return LayoutBuilder(
      builder: (context, bc) {
        final h = bc.maxHeight;
        return CustomPaint(
          size: Size(12, h),
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
    final bg = Paint()..color = Colors.black.withOpacity(0.08);
    final rect = Offset.zero & size;
    canvas.drawRRect(
      RRect.fromRectAndRadius(rect, const Radius.circular(8)),
      bg,
    );

    final fill = Rect.fromLTWH(0, size.height * (1 - v), size.width, size.height * v);
    final bar = Paint()
      ..shader = const LinearGradient(
        begin: Alignment.bottomCenter,
        end: Alignment.topCenter,
        colors: [Color(0xFFE91E63), Color(0xFFFFC0CB)],
      ).createShader(fill);
    canvas.drawRRect(
      RRect.fromRectAndRadius(fill, const Radius.circular(8)),
      bar,
    );
  }

  @override
  bool shouldRepaint(covariant _SweetnessPainter old) => old.v != v;
}
