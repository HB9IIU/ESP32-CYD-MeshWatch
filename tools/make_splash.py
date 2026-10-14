#!/usr/bin/env python3
"""Generates the MeshWatch boot splash (320x240) as an LVGL RGB565 image.

Usage: python3 tools/make_splash.py [preview.png]
Writes src/splash_image.c; optionally also a PNG preview of the quantized result.
"""
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

WIDTH, HEIGHT = 320, 240
SCALE = 4  # supersampling factor for smooth edges
FONT_PATH = "/System/Library/Fonts/Avenir Next.ttc"

RADAR_CENTER = (160, 84)
RADAR_RINGS = (18, 36, 54, 72)
SWEEP_ANGLE = -40  # leading edge of the sweep, degrees (0 = east, negative = up)
SWEEP_WIDTH = 70

CYAN = (34, 211, 238)
YELLOW = (254, 231, 21)
WHITE = (240, 244, 250)
MUTED = (138, 147, 166)

# Hand-placed so the mesh looks organic but balanced; (x, y) in screen pixels.
NODES = [
    (160, 84),  # the local node, centre of the radar
    (118, 58), (204, 52), (96, 102), (226, 104), (148, 128), (186, 22),
    (130, 20), (62, 66), (258, 70), (52, 128), (268, 138), (206, 140),
    (102, 146), (30, 40), (292, 30), (238, 18), (80, 24),
]
LINKS = [
    (0, 1), (0, 2), (0, 3), (0, 4), (0, 5), (1, 7), (1, 8), (2, 6), (2, 9),
    (3, 10), (3, 13), (4, 11), (4, 12), (5, 12), (5, 13), (6, 7), (6, 16),
    (8, 14), (8, 17), (9, 15), (9, 16), (1, 3), (2, 4), (7, 17),
]


def s(value):
    return value * SCALE


def find_font_index(path, wanted):
    for index in range(32):
        try:
            font = ImageFont.truetype(path, 10, index=index)
        except OSError:
            break
        if font.getname()[1] == wanted:
            return index
    raise SystemExit(f"Face {wanted!r} not found in {path}")


def background():
    y, x = np.mgrid[0:s(HEIGHT), 0:s(WIDTH)].astype(np.float32)
    cx, cy = s(RADAR_CENTER[0]), s(RADAR_CENTER[1])
    distance = np.sqrt((x - cx) ** 2 + ((y - cy) * 1.15) ** 2) / s(230)
    t = np.clip(distance, 0, 1) ** 0.9
    inner = np.array([22, 42, 76], np.float32)
    outer = np.array([6, 9, 18], np.float32)
    rgb = inner * (1 - t[..., None]) + outer * t[..., None]
    return Image.fromarray(rgb.astype(np.uint8), "RGB").convert("RGBA")


def in_sweep(point):
    dx, dy = point[0] - RADAR_CENTER[0], point[1] - RADAR_CENTER[1]
    if math.hypot(dx, dy) > RADAR_RINGS[-1] + 4:
        return False
    angle = math.degrees(math.atan2(dy, dx))
    behind = (SWEEP_ANGLE - angle) % 360
    return behind <= SWEEP_WIDTH


def draw_radar(image):
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    cx, cy = s(RADAR_CENTER[0]), s(RADAR_CENTER[1])
    outer = s(RADAR_RINGS[-1])

    # Sweep: many thin slices fading out behind the leading edge.
    steps = SWEEP_WIDTH * 2
    for step in range(steps):
        start = SWEEP_ANGLE - SWEEP_WIDTH + step * 0.5
        alpha = int(100 * (step / steps) ** 1.6)
        draw.pieslice((cx - outer, cy - outer, cx + outer, cy + outer), start, start + 0.6,
                      fill=CYAN + (alpha,))
    edge = math.radians(SWEEP_ANGLE)
    draw.line((cx, cy, cx + outer * math.cos(edge), cy + outer * math.sin(edge)),
              fill=CYAN + (170,), width=s(1))

    for radius in RADAR_RINGS:
        r = s(radius)
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), outline=CYAN + (48,), width=max(2, s(1) // 2))
    draw.line((cx - outer, cy, cx + outer, cy), fill=CYAN + (26,), width=2)
    draw.line((cx, cy - outer, cx, cy + outer), fill=CYAN + (26,), width=2)
    return Image.alpha_composite(image, layer)


def draw_mesh(image):
    links = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(links)
    for a, b in LINKS:
        lit = in_sweep(NODES[a]) and in_sweep(NODES[b])
        color = CYAN + ((150,) if lit else (70,))
        draw.line((s(NODES[a][0]), s(NODES[a][1]), s(NODES[b][0]), s(NODES[b][1])),
                  fill=color, width=max(3, int(s(1) * 0.9)))
    image = Image.alpha_composite(image, links)

    glow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    dots = Image.new("RGBA", image.size, (0, 0, 0, 0))
    dot_draw = ImageDraw.Draw(dots)
    for index, (x, y) in enumerate(NODES):
        local = index == 0
        lit = in_sweep((x, y))
        color = YELLOW if local or lit else CYAN
        glow_radius = s(9 if local else (7 if lit else 5))
        glow_draw.ellipse((s(x) - glow_radius, s(y) - glow_radius, s(x) + glow_radius, s(y) + glow_radius),
                          fill=color + (150 if local or lit else 90,))
        dot_radius = s(3.2 if local else 2.2)
        dot_draw.ellipse((s(x) - dot_radius, s(y) - dot_radius, s(x) + dot_radius, s(y) + dot_radius),
                         fill=(255, 255, 255, 255) if local else color + (255,))
        if local:
            ring = s(6)
            dot_draw.ellipse((s(x) - ring, s(y) - ring, s(x) + ring, s(y) + ring),
                             outline=YELLOW + (230,), width=s(1))
    glow = glow.filter(ImageFilter.GaussianBlur(s(3)))
    return Image.alpha_composite(Image.alpha_composite(image, glow), dots)


def draw_title(image):
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    bold = ImageFont.truetype(FONT_PATH, s(34), index=find_font_index(FONT_PATH, "Bold"))
    regular = ImageFont.truetype(FONT_PATH, s(11), index=find_font_index(FONT_PATH, "Medium"))

    first, second = "Mesh", "Watch"
    width_first = draw.textlength(first, font=bold)
    width_total = width_first + draw.textlength(second, font=bold)
    x = (s(WIDTH) - width_total) / 2
    baseline = s(192)
    draw.text((x, baseline), first, font=bold, fill=WHITE + (255,), anchor="ls")
    draw.text((x + width_first, baseline), second, font=bold, fill=YELLOW + (255,), anchor="ls")

    subtitle = "M E S H T A S T I C   M O N I T O R"
    draw.text((s(WIDTH) / 2, s(210)), subtitle, font=regular, fill=MUTED + (255,), anchor="ms")

    shadow = layer.filter(ImageFilter.GaussianBlur(s(2)))
    shadow_alpha = shadow.getchannel("A").point(lambda value: value * 0.6)
    shadow = Image.merge("RGBA", (*Image.new("RGB", image.size, (0, 0, 0)).split(), shadow_alpha))
    return Image.alpha_composite(Image.alpha_composite(image, shadow), layer)


def to_rgb565(image):
    """Quantizes to RGB565 with light noise dithering to avoid gradient banding."""
    rgb = np.asarray(image.convert("RGB"), np.float32)
    rng = np.random.default_rng(7)
    noise = rng.uniform(-0.5, 0.5, rgb.shape[:2])[..., None]
    steps = np.array([8, 4, 8], np.float32)
    quantized = np.clip(np.floor(rgb / steps + 0.5 + noise), 0, [31, 63, 31]).astype(np.uint16)
    packed = (quantized[..., 0] << 11) | (quantized[..., 1] << 5) | quantized[..., 2]
    preview = np.stack([quantized[..., 0] * 255 // 31, quantized[..., 1] * 255 // 63,
                        quantized[..., 2] * 255 // 31], axis=-1).astype(np.uint8)
    return packed, Image.fromarray(preview, "RGB")


def write_c_source(packed, path):
    data = packed.astype("<u2").tobytes()  # little-endian, matches LV_COLOR_16_SWAP 0
    lines = []
    for offset in range(0, len(data), 24):
        lines.append("  " + ", ".join(f"0x{byte:02x}" for byte in data[offset:offset + 24]) + ",")
    path.write_text(
        "// Generated by tools/make_splash.py - do not edit by hand.\n"
        "#include <lvgl.h>\n\n"
        f"static const uint8_t splash_image_map[{len(data)}] = {{\n" + "\n".join(lines) + "\n};\n\n"
        "const lv_img_dsc_t splash_image = {\n"
        "    .header = {.cf = LV_IMG_CF_TRUE_COLOR, .always_zero = 0, .reserved = 0,\n"
        f"               .w = {WIDTH}, .h = {HEIGHT}}},\n"
        f"    .data_size = {len(data)},\n"
        "    .data = splash_image_map,\n"
        "};\n"
    )


def main():
    image = background()
    image = draw_radar(image)
    image = draw_mesh(image)
    image = draw_title(image)
    image = image.resize((WIDTH, HEIGHT), Image.LANCZOS)

    packed, preview = to_rgb565(image)
    output = Path(__file__).resolve().parent.parent / "src" / "splash_image.c"
    write_c_source(packed, output)
    print(f"Wrote {output}")
    if len(sys.argv) > 1:
        preview.resize((WIDTH * 2, HEIGHT * 2), Image.NEAREST).save(sys.argv[1])
        print(f"Preview: {sys.argv[1]}")


if __name__ == "__main__":
    main()
