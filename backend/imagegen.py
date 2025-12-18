from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter, ImageDraw, ImageFont


def hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    h = hex_str.strip().lstrip("#")
    if len(h) == 6:
        h = "FF" + h
    value = int(h, 16)
    return ((value >> 16) & 255, (value >> 8) & 255, value & 255)


def draw_residual_sugar_bar(img: Image.Image, residual_sugar: float, bar_width: int = None) -> Image.Image:
    """
    Zeichnet einen Restzucker-Balken am rechten Rand des Bildes.
    
    Args:
        img: Das Eingabebild (PIL Image)
        residual_sugar: Restzucker in g/L (typisch 0-500, kann aber höher sein)
        bar_width: Breite des Balkens (default: 5% der Bildbreite)
    
    Returns:
        Neues Bild mit Balken
    """
    if residual_sugar is None or residual_sugar < 0:
        return img
    
    w, h = img.size
    if bar_width is None:
        bar_width = max(int(w * 0.05), 30)  # 5% der Breite, mindestens 30px
    
    # Neues breiteres Bild erstellen
    new_w = w + bar_width
    new_img = Image.new("RGB", (new_w, h), (252, 252, 254))  # Hintergrundfarbe
    new_img.paste(img, (0, 0))
    
    draw = ImageDraw.Draw(new_img)
    
    # Balkenhöhe berechnen (logarithmische Skala für bessere Verteilung)
    # Skala: 0g → 0%, 9g → ~10%, 50g → ~50%, 500g → 100%
    # Formel: log-basiert mit Minimum bei 1g
    if residual_sugar <= 0:
        bar_height_ratio = 0.0
    else:
        # Log-Skala: log(1) = 0, log(500) ≈ 2.7
        import math
        max_sugar = 500.0  # Obergrenze für 100%
        min_sugar = 1.0    # Untergrenze
        clamped = max(min_sugar, min(residual_sugar, max_sugar))
        bar_height_ratio = math.log10(clamped) / math.log10(max_sugar)
        bar_height_ratio = min(1.0, max(0.0, bar_height_ratio))
    
    # Balken von unten nach oben
    bar_height = int(h * bar_height_ratio)
    bar_x1 = w
    bar_x2 = new_w
    bar_y1 = h - bar_height  # Oberkante
    bar_y2 = h               # Unterkante
    
    # Pinke/Magenta Farbe (wie im Beispielbild)
    bar_color = (240, 62, 107)  # Pink/Magenta
    
    # Balken zeichnen
    if bar_height > 0:
        draw.rectangle([bar_x1, bar_y1, bar_x2, bar_y2], fill=bar_color)
    
    # Hintergrund über dem Balken (grau)
    if bar_y1 > 0:
        gray_color = (200, 200, 200)
        draw.rectangle([bar_x1, 0, bar_x2, bar_y1], fill=gray_color)
    
    # Text mit Restzucker-Wert (vertikal, von unten nach oben)
    # Wert als ganze Zahl anzeigen
    sugar_text = f"{int(residual_sugar)} gr RZ"
    
    # Font laden (versuche System-Font, sonst Default)
    font_size = max(int(bar_width * 0.5), 12)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
    except:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
        except:
            font = ImageFont.load_default()
    
    # Text vertikal zeichnen (rotiert)
    # Erstelle temporäres Bild für rotierten Text
    text_bbox = draw.textbbox((0, 0), sugar_text, font=font)
    text_w = text_bbox[2] - text_bbox[0]
    text_h = text_bbox[3] - text_bbox[1]
    
    text_img = Image.new("RGBA", (text_w + 10, text_h + 10), (0, 0, 0, 0))
    text_draw = ImageDraw.Draw(text_img)
    text_draw.text((5, 5), sugar_text, font=font, fill=(255, 255, 255, 255))
    
    # 90° gegen Uhrzeigersinn drehen (Text von unten nach oben lesbar)
    text_img = text_img.rotate(90, expand=True)
    
    # Text in der Mitte des Balkens positionieren
    text_x = w + (bar_width - text_img.width) // 2
    text_y = h - bar_height + (bar_height - text_img.height) // 2
    
    # Nur zeichnen wenn genug Platz
    if bar_height > text_img.height + 10:
        new_img.paste(text_img, (text_x, max(0, text_y)), text_img)
    
    return new_img


def generate_wine_png(
    viz: dict,
    size: int = 1024,
    out_path: str = "wine_test.png",
):
    """Weinvisualisierung mit 3-Schicht-System:
    
    Layer 1: Weinfarben-Basis mit radialem Gradient (wie bisher)
    Layer 2: Charakteristische farbige Ringe (neu - zeigen Ausprägung)
    Layer 3: Textur-Elemente wie Sterne für Spritzigkeit (neu)
    """

    # zentrale Weinfarbe
    base_hex = viz.get("base_color_hex") or "#F6F2AF"
    base_rgb = np.array(hex_to_rgb(base_hex), dtype=np.float32)

    w = h = size
    cx, cy = w / 2.0, h / 2.0
    max_r = min(cx, cy) * 0.95

    # Hintergrund
    bg_color = np.array([252.0, 252.0, 254.0], dtype=np.float32)

    yy, xx = np.mgrid[0:h, 0:w]
    dx = xx - cx
    dy = yy - cy
    r = np.sqrt(dx * dx + dy * dy)
    t = r / max_r  # 0=Zentrum, 1=Außenkante
    angles = np.arctan2(dy, dx)

    rng = np.random.default_rng(42)

    # === Intensitäten aus Profil (0..1) ===
    def _f(name: str, default: float = 0.0) -> float:
        v = viz.get(name)
        try:
            return float(v) if v is not None else default
        except (TypeError, ValueError):
            return default

    oak = _f("oak_intensity")
    mineral = _f("mineral_intensity")
    acidity = _f("acidity", 0.5)
    herbs = _f("herbal_intensity")
    spice = _f("spice_intensity")
    fruit_citrus = _f("fruit_citrus")
    fruit_stone = _f("fruit_stone")
    fruit_tropical = _f("fruit_tropical")
    fruit_red = _f("fruit_red")
    fruit_dark = _f("fruit_dark")
    body = _f("body", 0.5)
    depth = _f("depth", 0.5)
    
    # Spritzigkeit für Layer 3
    effervescence = _f("effervescence", 0.0)
    
    # Restzucker (g/L) für den Balken am rechten Rand
    residual_sugar = _f("residual_sugar", 0.0)
    
    # Weintyp aus Profil (optional)
    wine_type = viz.get("wine_type", "auto")  # "red", "white", "rose", "auto"

    # ============================================================
    # LAYER 1: Weinfarben-Basis mit radialem Gradient
    # ============================================================
    
    base_brightness = np.mean(base_rgb) / 255.0
    
    # Weintyp bestimmen
    if wine_type == "red":
        is_red_wine = True
        is_rose = False
    elif wine_type == "rose":
        is_red_wine = False
        is_rose = True
    elif wine_type == "white":
        is_red_wine = False
        is_rose = False
    else:  # auto
        is_red_wine = base_brightness < 0.5
        # Rosé: Mittlere Helligkeit mit Rot-Dominanz UND wenig Grün
        is_rose = (0.5 <= base_brightness < 0.7) and (base_rgb[0] > base_rgb[1] + 30) and (base_rgb[1] < 160)
    
    wine = np.ones((h, w, 3), dtype=np.float32) * base_rgb[None, None, :]

    if is_red_wine:
        brightness = 0.5 + 0.6 * (t ** 0.7)  # Weniger Aufhellung außen
        warmth = t ** 0.8
        wine[..., 0] = wine[..., 0] + warmth * 25
        wine[..., 1] = wine[..., 1] + warmth * 15
    elif is_rose:
        # Rosé: Außen heller, Kern DEUTLICH dunkler
        brightness = 0.6 + 0.5 * (t ** 0.5) - 0.3 * (np.clip(1-t, 0, 1) ** 1.2)
        # Leichte Wärme außen
        warmth = t ** 0.9
        wine[..., 0] = wine[..., 0] + warmth * 15
    else:
        # Weißwein: Außen hell, Kern dunkler mit weniger Grün
        brightness = 1.05 + 0.02 * (np.clip(t, 0, 1) ** 0.5) - 0.10 * (np.clip(1-t, 0, 1) ** 1.2)
        # Kern: weniger Grün, mehr Gelb (goldener)
        center_weight = (1 - t) ** 1.8
        wine[..., 1] = wine[..., 1] - center_weight * 20  # Weniger Grün im Kern
        wine[..., 2] = wine[..., 2] - center_weight * 35  # Deutlich weniger Blau im Kern
    
    wine = wine * np.clip(brightness, 0.3, 1.5)[..., None]

    # Feine Textur auf Layer 1
    radial_lines = np.sin(angles * 80 + t * 20) * 0.5 + 0.5
    texture_strength = 0.03 * (1 - t * 0.5)
    wine = wine * (1 + (radial_lines - 0.5)[..., None] * texture_strength[..., None])

    noise = rng.normal(0, 1, (h, w)).astype(np.float32)
    noise = noise / (np.abs(noise).max() + 1e-6)
    wine = wine * (1 + noise[..., None] * 0.015)

    # ============================================================
    # LAYER 2: Charakteristische farbige Ringe
    # ============================================================
    # Ringe zeigen Ausprägungen von Eigenschaften/Geschmack/Fass etc.
    # Reihenfolge: Außen (1) → Innen (12)
    
    RING_DEFINITIONS = [
        # (name, center, width, color_rgb, intensity_key)
        ("Holz/Fass",    0.78, 0.06, (140, 90, 50),   oak),           # Braun/Eiche
        ("Mineralität",  0.72, 0.06, (130, 140, 150), mineral),       # Grau/Stein
        ("Säure",        0.66, 0.06, (160, 200, 120), acidity),       # Hellgrün
        ("Kräuter",      0.60, 0.06, (70, 120, 70),   herbs),         # Dunkelgrün
        ("Würze",        0.54, 0.06, (170, 100, 45),  spice),         # Zimt/Orange
        ("Zitrus",       0.48, 0.05, (240, 220, 70),  fruit_citrus),  # Gelb
        ("Steinobst",    0.42, 0.05, (240, 170, 90),  fruit_stone),   # Aprikose
        ("Tropisch",     0.36, 0.05, (240, 200, 55),  fruit_tropical),# Mango
        ("Rotfrucht",    0.30, 0.05, (200, 60, 60),   fruit_red),     # Rot
        ("Dunkelfrucht", 0.24, 0.05, (80, 35, 80),    fruit_dark),    # Dunkel-Lila
        ("Körper",       0.18, 0.06, (140, 70, 45),   body),          # Sienna
        ("Tiefe",        0.12, 0.08, None,            depth),         # Weinfarbe dunkler
    ]
    
    for name, center, width, ring_color, intensity in RING_DEFINITIONS:
        if intensity < 0.2:  # Nur Ringe mit merkbarer Intensität zeigen
            continue
        
        # Ring-Maske mit weichen Kanten (Gauss)
        sigma = width * 0.5
        dist = np.abs(t - center)
        ring_weight = np.exp(-0.5 * (dist / sigma) ** 2)
        
        # Ringe früh ausfaden (vor t=0.85) damit Blur nicht nach außen blutet
        ring_weight = ring_weight * np.clip((0.82 - t) / 0.10, 0, 1)
        
        # Intensität bestimmt Sichtbarkeit: 0.2-1.0 → 0.08-0.35 Deckkraft (dezenter)
        ring_opacity = ring_weight * (0.08 + intensity * 0.27)
        
        if ring_color is None:
            # "Tiefe" Ring: Weinfarbe dunkler machen
            wine = wine * (1 - ring_opacity[..., None] * 0.4)
        else:
            # Farbiger Ring - sanft mit Weinfarbe mischen
            color = np.array(ring_color, dtype=np.float32)
            
            # Bei Rotwein: Farben aufhellen damit sichtbar
            if is_red_wine:
                color = np.clip(color * 1.3 + 30, 0, 255)
            else:
                # Bei Weißwein: Farben etwas satter
                color = np.clip(color * 0.9, 0, 255)
            
            wine = wine * (1 - ring_opacity[..., None]) + color[None, None, :] * ring_opacity[..., None]

    # ============================================================
    # LAYER 3: Textur-Elemente (Sterne/Bläschen für Spritzigkeit)
    # ============================================================
    
    # Kleine helle Punkte für allgemeine Textur
    n_dots = int(size * size * 0.0003)
    for _ in range(n_dots):
        angle = rng.uniform(0, 2 * np.pi)
        radius = rng.uniform(0.2, 0.85) * max_r
        x = int(cx + radius * np.cos(angle))
        y = int(cy + radius * np.sin(angle))
        
        if 0 <= x < w and 0 <= y < h:
            current = wine[y, x]
            if is_red_wine:
                dot_color = current * 1.2
            else:
                dot_color = np.array([160, 195, 210], dtype=np.float32)
            
            dot_size = rng.integers(1, 2)
            opacity = rng.uniform(0.1, 0.25)
            
            for ddx in range(-dot_size, dot_size + 1):
                for ddy in range(-dot_size, dot_size + 1):
                    if ddx*ddx + ddy*ddy <= dot_size*dot_size:
                        px, py = x + ddx, y + ddy
                        if 0 <= px < w and 0 <= py < h:
                            wine[py, px] = wine[py, px] * (1 - opacity) + dot_color * opacity

    # === Sterne/Sparkles/Bläschen für Spritzigkeit ===
    if effervescence > 0.1:
        # VIEL mehr Bläschen für sichtbaren Effekt
        n_bubbles = int(effervescence * 400 * (size / 512))  # Skaliert mit Bildgröße
        
        for _ in range(n_bubbles):
            angle = rng.uniform(0, 2 * np.pi)
            radius = rng.beta(2, 1.5) * 0.85 * max_r
            bx = int(cx + radius * np.cos(angle))
            by = int(cy + radius * np.sin(angle))
            
            if not (0 <= bx < w and 0 <= by < h):
                continue
            
            # Größere Bläschen/Sterne
            base_size = int(3 + effervescence * 4)  # 3-7 Pixel
            bubble_size = rng.integers(base_size - 2, base_size + 3)
            
            # 50% sind Sterne (funkelnde Perlen)
            if rng.random() < 0.5:
                n_arms = 4 if rng.random() < 0.6 else 6
                arm_length = bubble_size + rng.integers(2, 6)
                
                for arm_i in range(n_arms):
                    arm_angle = (2 * np.pi * arm_i / n_arms) + rng.uniform(-0.15, 0.15)
                    for d in range(arm_length):
                        px = int(bx + d * np.cos(arm_angle))
                        py = int(by + d * np.sin(arm_angle))
                        if 0 <= px < w and 0 <= py < h:
                            falloff = 1.0 - (d / arm_length) * 0.6
                            opacity = 0.8 * falloff * effervescence
                            star_color = np.array([255, 255, 250], dtype=np.float32)
                            wine[py, px] = wine[py, px] * (1 - opacity) + star_color * opacity
                
                # Helles Zentrum - größer
                for ddx in range(-2, 3):
                    for ddy in range(-2, 3):
                        if ddx*ddx + ddy*ddy <= 4:
                            px, py = bx + ddx, by + ddy
                            if 0 <= px < w and 0 <= py < h:
                                wine[py, px] = wine[py, px] * 0.2 + np.array([255, 255, 252]) * 0.8
            else:
                # Runde Bläschen - größer und heller
                for ddx in range(-bubble_size-2, bubble_size+3):
                    for ddy in range(-bubble_size-2, bubble_size+3):
                        dist_sq = ddx*ddx + ddy*ddy
                        if dist_sq <= (bubble_size+2)**2:
                            px, py = bx + ddx, by + ddy
                            if 0 <= px < w and 0 <= py < h:
                                # Lichtreflex oben-links
                                is_highlight = (ddx < 0 and ddy < 0 and dist_sq > (bubble_size-2)**2)
                                if is_highlight:
                                    opacity = 0.85 * effervescence
                                    bubble_color = np.array([255, 255, 255], dtype=np.float32)
                                elif dist_sq <= bubble_size**2:
                                    opacity = 0.4 * effervescence
                                    bubble_color = np.clip(wine[py, px] * 1.3 + 30, 0, 255)
                                else:
                                    continue
                                wine[py, px] = wine[py, px] * (1 - opacity) + bubble_color * opacity

    # === Blur - WENIGER bei Spritzigkeit damit Sterne sichtbar bleiben ===
    blur_radius = size * 0.008 if effervescence < 0.3 else size * 0.004
    wine = np.clip(wine, 0, 255)
    wine_img = Image.fromarray(wine.astype(np.uint8), mode="RGB")
    wine_img = wine_img.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    wine = np.asarray(wine_img, dtype=np.float32)

    # === Äußeren Ring reparieren (Blur blutet Ringfarben nach außen) ===
    # Bei t > 0.85 mit sauberer Basis-Farbe ersetzen, sanft überblenden
    if not is_red_wine and not is_rose:
        # Berechne saubere Außenfarbe (Layer 1 ohne Ringe)
        outer_brightness = 1.05 + 0.02 * (np.clip(t, 0, 1) ** 0.5)
        clean_outer = base_rgb[None, None, :] * outer_brightness[..., None]
        clean_outer = np.clip(clean_outer, 0, 255)
        
        # Überblendung: ab t=0.85 sanft zur sauberen Farbe
        outer_blend = np.clip((t - 0.85) / 0.08, 0, 1)[..., None]
        wine = wine * (1 - outer_blend) + clean_outer * outer_blend

    # === Kreismaske ===
    edge_start = 0.90
    edge_end = 1.08
    circle_alpha = np.clip((edge_end - t) / (edge_end - edge_start), 0, 1)
    circle_alpha = circle_alpha ** 0.6
    
    img = bg_color[None, None, :] * (1 - circle_alpha[..., None]) + wine * circle_alpha[..., None]

    # Speichern
    pil = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), mode="RGB")
    
    # Restzucker-Balken hinzufügen (rechter Rand)
    if residual_sugar > 0:
        pil = draw_residual_sugar_bar(pil, residual_sugar)
    
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    pil.save(out_path, format="PNG")
    print(f"saved {out_path}")


def generate_wine_png_bytes(
    viz: dict,
    size: int = 512,
) -> bytes:
    """Generiert ein PNG als Bytes (für API-Response)."""
    import io
    
    # Temporärer Pfad nicht nötig - wir generieren direkt in Memory
    # Kopiere die Logik von generate_wine_png, aber speichere in BytesIO
    
    # zentrale Weinfarbe
    base_hex = viz.get("base_color_hex") or "#F6F2AF"
    base_rgb = np.array(hex_to_rgb(base_hex), dtype=np.float32)

    w = h = size
    cx, cy = w / 2.0, h / 2.0
    max_r = min(cx, cy) * 0.95

    bg_color = np.array([252.0, 252.0, 254.0], dtype=np.float32)

    yy, xx = np.mgrid[0:h, 0:w]
    dx = xx - cx
    dy = yy - cy
    r = np.sqrt(dx * dx + dy * dy)
    t = r / max_r
    angles = np.arctan2(dy, dx)

    rng = np.random.default_rng(42)

    def _f(name: str, default: float = 0.0) -> float:
        v = viz.get(name)
        try:
            return float(v) if v is not None else default
        except (TypeError, ValueError):
            return default

    oak = _f("oak_intensity")
    mineral = _f("mineral_intensity")
    acidity = _f("acidity", 0.5)
    herbs = _f("herbal_intensity")
    spice = _f("spice_intensity")
    fruit_citrus = _f("fruit_citrus")
    fruit_stone = _f("fruit_stone")
    fruit_tropical = _f("fruit_tropical")
    fruit_red = _f("fruit_red")
    fruit_dark = _f("fruit_dark")
    body = _f("body", 0.5)
    depth = _f("depth", 0.5)
    effervescence = _f("effervescence", 0.0)
    residual_sugar = _f("residual_sugar", 0.0)
    wine_type = viz.get("wine_type", "auto")

    # LAYER 1
    base_brightness = np.mean(base_rgb) / 255.0
    
    if wine_type == "red":
        is_red_wine = True
        is_rose = False
    elif wine_type == "rose":
        is_red_wine = False
        is_rose = True
    elif wine_type == "white":
        is_red_wine = False
        is_rose = False
    else:
        is_red_wine = base_brightness < 0.5
        is_rose = (0.5 <= base_brightness < 0.7) and (base_rgb[0] > base_rgb[1] + 30) and (base_rgb[1] < 160)
    
    wine = np.ones((h, w, 3), dtype=np.float32) * base_rgb[None, None, :]

    if is_red_wine:
        brightness = 0.5 + 0.6 * (t ** 0.7)
        warmth = t ** 0.8
        wine[..., 0] = wine[..., 0] + warmth * 25
        wine[..., 1] = wine[..., 1] + warmth * 15
    elif is_rose:
        brightness = 0.6 + 0.5 * (t ** 0.5) - 0.3 * (np.clip(1-t, 0, 1) ** 1.2)
        warmth = t ** 0.9
        wine[..., 0] = wine[..., 0] + warmth * 15
    else:
        brightness = 1.05 + 0.02 * (np.clip(t, 0, 1) ** 0.5) - 0.10 * (np.clip(1-t, 0, 1) ** 1.2)
        center_weight = (1 - t) ** 1.8
        wine[..., 1] = wine[..., 1] - center_weight * 20
        wine[..., 2] = wine[..., 2] - center_weight * 35
    
    wine = wine * np.clip(brightness, 0.3, 1.5)[..., None]

    radial_lines = np.sin(angles * 80 + t * 20) * 0.5 + 0.5
    texture_strength = 0.03 * (1 - t * 0.5)
    wine = wine * (1 + (radial_lines - 0.5)[..., None] * texture_strength[..., None])

    noise = rng.normal(0, 1, (h, w)).astype(np.float32)
    noise = noise / (np.abs(noise).max() + 1e-6)
    wine = wine * (1 + noise[..., None] * 0.015)

    # LAYER 2: Ringe
    RING_DEFINITIONS = [
        ("Holz/Fass",    0.78, 0.06, (140, 90, 50),   oak),
        ("Mineralität",  0.72, 0.06, (130, 140, 150), mineral),
        ("Säure",        0.66, 0.06, (160, 200, 120), acidity),
        ("Kräuter",      0.60, 0.06, (70, 120, 70),   herbs),
        ("Würze",        0.54, 0.06, (170, 100, 45),  spice),
        ("Zitrus",       0.48, 0.05, (240, 220, 70),  fruit_citrus),
        ("Steinobst",    0.42, 0.05, (240, 170, 90),  fruit_stone),
        ("Tropisch",     0.36, 0.05, (240, 200, 55),  fruit_tropical),
        ("Rotfrucht",    0.30, 0.05, (200, 60, 60),   fruit_red),
        ("Dunkelfrucht", 0.24, 0.05, (80, 35, 80),    fruit_dark),
        ("Körper",       0.18, 0.06, (140, 70, 45),   body),
        ("Tiefe",        0.12, 0.08, None,            depth),
    ]
    
    for name, center, width, ring_color, intensity in RING_DEFINITIONS:
        if intensity < 0.2:
            continue
        sigma = width * 0.5
        dist = np.abs(t - center)
        ring_weight = np.exp(-0.5 * (dist / sigma) ** 2)
        ring_weight = ring_weight * np.clip((0.82 - t) / 0.10, 0, 1)
        ring_opacity = ring_weight * (0.08 + intensity * 0.27)
        
        if ring_color is None:
            wine = wine * (1 - ring_opacity[..., None] * 0.4)
        else:
            color = np.array(ring_color, dtype=np.float32)
            if is_red_wine:
                color = np.clip(color * 1.3 + 30, 0, 255)
            else:
                color = np.clip(color * 0.9, 0, 255)
            wine = wine * (1 - ring_opacity[..., None]) + color[None, None, :] * ring_opacity[..., None]

    # LAYER 3: Textur-Elemente
    n_dots = int(size * size * 0.0003)
    for _ in range(n_dots):
        angle = rng.uniform(0, 2 * np.pi)
        radius = rng.uniform(0.2, 0.85) * max_r
        x = int(cx + radius * np.cos(angle))
        y = int(cy + radius * np.sin(angle))
        if 0 <= x < w and 0 <= y < h:
            current = wine[y, x]
            if is_red_wine:
                dot_color = current * 1.2
            else:
                dot_color = np.array([160, 195, 210], dtype=np.float32)
            dot_size = rng.integers(1, 2)
            opacity = rng.uniform(0.1, 0.25)
            for ddx in range(-dot_size, dot_size + 1):
                for ddy in range(-dot_size, dot_size + 1):
                    if ddx*ddx + ddy*ddy <= dot_size*dot_size:
                        px, py = x + ddx, y + ddy
                        if 0 <= px < w and 0 <= py < h:
                            wine[py, px] = wine[py, px] * (1 - opacity) + dot_color * opacity

    # Sparkles für Spritzigkeit
    if effervescence > 0.1:
        n_bubbles = int(effervescence * 400 * (size / 512))
        for _ in range(n_bubbles):
            angle = rng.uniform(0, 2 * np.pi)
            radius = rng.beta(2, 1.5) * 0.85 * max_r
            bx = int(cx + radius * np.cos(angle))
            by = int(cy + radius * np.sin(angle))
            if not (0 <= bx < w and 0 <= by < h):
                continue
            base_size = int(3 + effervescence * 4)
            bubble_size = rng.integers(base_size - 2, base_size + 3)
            if rng.random() < 0.5:
                n_arms = 4 if rng.random() < 0.6 else 6
                arm_length = bubble_size + rng.integers(2, 6)
                for arm_i in range(n_arms):
                    arm_angle = (2 * np.pi * arm_i / n_arms) + rng.uniform(-0.15, 0.15)
                    for d in range(arm_length):
                        px = int(bx + d * np.cos(arm_angle))
                        py = int(by + d * np.sin(arm_angle))
                        if 0 <= px < w and 0 <= py < h:
                            falloff = 1.0 - (d / arm_length) * 0.6
                            opacity = 0.8 * falloff * effervescence
                            star_color = np.array([255, 255, 250], dtype=np.float32)
                            wine[py, px] = wine[py, px] * (1 - opacity) + star_color * opacity
                for ddx in range(-2, 3):
                    for ddy in range(-2, 3):
                        if ddx*ddx + ddy*ddy <= 4:
                            px, py = bx + ddx, by + ddy
                            if 0 <= px < w and 0 <= py < h:
                                wine[py, px] = wine[py, px] * 0.2 + np.array([255, 255, 252]) * 0.8
            else:
                for ddx in range(-bubble_size-2, bubble_size+3):
                    for ddy in range(-bubble_size-2, bubble_size+3):
                        dist_sq = ddx*ddx + ddy*ddy
                        if dist_sq <= (bubble_size+2)**2:
                            px, py = bx + ddx, by + ddy
                            if 0 <= px < w and 0 <= py < h:
                                is_highlight = (ddx < 0 and ddy < 0 and dist_sq > (bubble_size-2)**2)
                                if is_highlight:
                                    opacity = 0.85 * effervescence
                                    bubble_color = np.array([255, 255, 255], dtype=np.float32)
                                elif dist_sq <= bubble_size**2:
                                    opacity = 0.4 * effervescence
                                    bubble_color = np.clip(wine[py, px] * 1.3 + 30, 0, 255)
                                else:
                                    continue
                                wine[py, px] = wine[py, px] * (1 - opacity) + bubble_color * opacity

    # Blur
    blur_radius = size * 0.008 if effervescence < 0.3 else size * 0.004
    wine = np.clip(wine, 0, 255)
    wine_img = Image.fromarray(wine.astype(np.uint8), mode="RGB")
    wine_img = wine_img.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    wine = np.asarray(wine_img, dtype=np.float32)

    # Äußeren Ring bei Weißwein reparieren
    if not is_red_wine and not is_rose:
        outer_brightness = 1.05 + 0.02 * (np.clip(t, 0, 1) ** 0.5)
        clean_outer = base_rgb[None, None, :] * outer_brightness[..., None]
        clean_outer = np.clip(clean_outer, 0, 255)
        outer_blend = np.clip((t - 0.85) / 0.08, 0, 1)[..., None]
        wine = wine * (1 - outer_blend) + clean_outer * outer_blend

    # Kreismaske
    edge_start = 0.90
    edge_end = 1.08
    circle_alpha = np.clip((edge_end - t) / (edge_end - edge_start), 0, 1)
    circle_alpha = circle_alpha ** 0.6
    
    img = bg_color[None, None, :] * (1 - circle_alpha[..., None]) + wine * circle_alpha[..., None]

    # In Bytes speichern
    pil = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), mode="RGB")
    
    # Restzucker-Balken hinzufügen (rechter Rand)
    if residual_sugar > 0:
        pil = draw_residual_sugar_bar(pil, residual_sugar)
    
    buffer = io.BytesIO()
    pil.save(buffer, format="PNG")
    return buffer.getvalue()


def main():
    print("[imagegen] starting generation...")
    example_viz = {
        "base_color_hex": "#F6F2AF",
        "acidity": 0.7,
        "body": 0.4,
        "depth": 0.6,
        "oak_intensity": 0.3,
        "mineral_intensity": 0.4,
        "herbal_intensity": 0.3,
        "spice_intensity": 0.2,
        "fruit_citrus": 0.5,
        "fruit_stone": 0.4,
        "fruit_tropical": 0.6,
        "fruit_red": 0.0,
        "fruit_dark": 0.0,
    }

    generate_wine_png(example_viz, out_path="generated_wine_white.png")


if __name__ == "__main__":
    main()
