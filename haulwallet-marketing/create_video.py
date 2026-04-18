#!/usr/bin/env python3
"""
HaulWallet Promo Video Generator
30-second animated promotional video for HaulWallet truck driver app
"""

import os
import sys
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy import VideoClip, AudioFileClip, concatenate_videoclips

# ─── CONFIG ───────────────────────────────────────────────────────────────────
OUTPUT_PATH = "/Users/vladimirprihodko/Папка тест/fixcraftvp/haulwallet-marketing/haulwallet-promo.mp4"
AUDIO_PATH  = "/Users/vladimirprihodko/Папка тест/fixcraftvp/haulwallet-marketing/voiceover.mp3"
W, H = 1920, 1080
FPS  = 30

# Palette
C_BG     = (13,  27,  42)   # dark navy
C_GREEN  = (26,  58,  42)   # dark green scene
C_PURPLE = (26,  26,  58)   # dark purple scene
C_BLUE   = (10,  20,  50)   # dark blue scene
C_ORANGE = (255, 107, 53)   # primary orange
C_TEAL   = (0,   212, 170)  # teal/success
C_WHITE  = (255, 255, 255)
C_LGRAY  = (160, 176, 192)  # secondary text
C_RED    = (220, 50,  50)
C_DGREEN = (50,  200, 100)

# ─── FONT HELPERS ─────────────────────────────────────────────────────────────

def get_font(size, bold=False):
    """Load a system font with fallback."""
    candidates = []
    if bold:
        candidates = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/SFNSDisplay.ttf",
            "/Library/Fonts/Arial Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        ]
    else:
        candidates = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/SFNSText.ttf",
            "/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
        ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


def draw_text_centered(draw, text, y, font, color, shadow=True):
    """Draw horizontally centered text with optional shadow."""
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
    except Exception:
        tw = len(text) * (font.size // 2 if hasattr(font, 'size') else 10)
    x = (W - tw) // 2
    if shadow:
        draw.text((x+3, y+3), text, font=font, fill=(0, 0, 0, 180))
    draw.text((x, y), text, font=font, fill=color)


def draw_text_at(draw, text, x, y, font, color, shadow=True, anchor="left"):
    """Draw text at position with optional shadow."""
    if anchor == "center":
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            tw = bbox[2] - bbox[0]
        except Exception:
            tw = len(text) * 10
        x = x - tw // 2
    if shadow:
        draw.text((x+2, y+2), text, font=font, fill=(0, 0, 0, 160))
    draw.text((x, y), text, font=font, fill=color)


# ─── EASING ───────────────────────────────────────────────────────────────────

def ease_in_out(t):
    """Smooth S-curve easing."""
    return t * t * (3 - 2 * t)

def ease_out(t):
    return 1 - (1 - t) ** 3

def clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))

def alpha(t, start, end):
    """Return 0.0–1.0 progress within [start,end] window."""
    return clamp((t - start) / max(end - start, 0.001))


# ─── DRAW PRIMITIVES ──────────────────────────────────────────────────────────

def draw_truck(draw, cx, cy, scale=1.0, color=C_ORANGE):
    """Draw a simple side-view truck outline."""
    s = scale
    # Cab
    cab = [
        (cx - 40*s, cy),
        (cx - 40*s, cy - 60*s),
        (cx - 10*s, cy - 80*s),
        (cx + 40*s, cy - 80*s),
        (cx + 40*s, cy),
    ]
    draw.polygon(cab, fill=color)
    draw.polygon(cab, outline=C_WHITE, width=int(3*s))
    # Windshield
    ws = [
        (cx - 35*s, cy - 10*s),
        (cx - 35*s, cy - 50*s),
        (cx - 12*s, cy - 65*s),
        (cx + 35*s, cy - 65*s),
        (cx + 35*s, cy - 10*s),
    ]
    draw.polygon(ws, fill=(100, 180, 255, 200))
    # Trailer
    tr = [
        (cx + 40*s,  cy),
        (cx + 40*s,  cy - 70*s),
        (cx + 220*s, cy - 70*s),
        (cx + 220*s, cy),
    ]
    draw.polygon(tr, fill=(80, 100, 130))
    draw.polygon(tr, outline=C_WHITE, width=int(2*s))
    # Wheels
    for wx in [cx - 15*s, cx + 180*s]:
        r = 22*s
        draw.ellipse([wx-r, cy-r, wx+r, cy+r], fill=(40,40,40), outline=C_LGRAY, width=int(3*s))
        draw.ellipse([wx-r*0.5, cy-r*0.5, wx+r*0.5, cy+r*0.5], fill=(80,80,80))


def draw_shield(draw, cx, cy, size=80, color=C_TEAL):
    """Draw a shield shape."""
    pts = [
        (cx, cy - size),
        (cx + size*0.8, cy - size*0.5),
        (cx + size*0.8, cy + size*0.2),
        (cx, cy + size),
        (cx - size*0.8, cy + size*0.2),
        (cx - size*0.8, cy - size*0.5),
    ]
    draw.polygon(pts, fill=color)
    draw.polygon(pts, outline=C_WHITE, width=4)
    # Checkmark
    cx2, cy2 = int(cx), int(cy + size*0.1)
    w = int(size * 0.3)
    pts2 = [
        (cx2 - w, cy2),
        (cx2 - w//3, cy2 + w*0.7),
        (cx2 + w, cy2 - w*0.5),
    ]
    draw.line([pts2[0], pts2[1], pts2[2]], fill=C_WHITE, width=int(size*0.12))


def draw_phone_mockup(draw, cx, cy, w=180, h=320, screen_color=(20,30,50)):
    """Draw a simple phone outline."""
    x0, y0 = cx - w//2, cy - h//2
    x1, y1 = cx + w//2, cy + h//2
    r = 20
    draw.rounded_rectangle([x0, y0, x1, y1], radius=r, fill=(40,50,70), outline=C_WHITE, width=3)
    # Screen
    sx0, sy0 = x0+8, y0+20
    sx1, sy1 = x1-8, y1-20
    draw.rounded_rectangle([sx0, sy0, sx1, sy1], radius=10, fill=screen_color)
    # Home button
    draw.ellipse([cx-12, y1-18, cx+12, y1-4], fill=(60,70,90), outline=C_LGRAY, width=2)


def draw_glow(img, cx, cy, radius, color, intensity=0.4):
    """Add a radial glow overlay."""
    glow = Image.new("RGBA", img.size, (0,0,0,0))
    gdraw = ImageDraw.Draw(glow)
    steps = 15
    for i in range(steps, 0, -1):
        r2 = int(radius * i / steps)
        a = int(255 * intensity * (1 - i/steps) * (i/steps))
        c = color + (a,)
        gdraw.ellipse([cx-r2, cy-r2, cx+r2, cy+r2], fill=c)
    return Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")


# ═══════════════════════════════════════════════════════════════════════════════
# SCENE 1: Brand Intro (0–4s)
# ═══════════════════════════════════════════════════════════════════════════════

def make_scene1(t):
    """Black → dark navy, HaulWallet logo + truck + tagline."""
    dur = 4.0
    img = Image.new("RGB", (W, H), C_BG)
    draw = ImageDraw.Draw(img)

    # Background gradient: interpolate black → navy
    bg_p = ease_in_out(clamp(t / 1.5))
    bg_col = tuple(int(c * bg_p) for c in C_BG)
    img = Image.new("RGB", (W, H), bg_col)
    draw = ImageDraw.Draw(img)

    # Subtle grid lines
    grid_a = int(40 * bg_p)
    for gx in range(0, W, 80):
        draw.line([(gx, 0), (gx, H)], fill=(*C_BLUE, grid_a) if False else tuple(int(c*0.4) for c in C_BG), width=1)
    for gy in range(0, H, 80):
        draw.line([(0, gy), (W, gy)], fill=tuple(int(c*0.4) for c in C_BG), width=1)

    # LOGO text
    logo_p = ease_out(alpha(t, 0.5, 2.0))
    f_logo = get_font(120, bold=True)
    logo_y = H//2 - 130
    logo_text = "HaulWallet"
    # Glow effect via multiple passes
    if logo_p > 0.01:
        glow_col = tuple(int(c * logo_p) for c in C_ORANGE)
        for offset in [8, 5, 3]:
            try:
                bbox = draw.textbbox((0,0), logo_text, font=f_logo)
                tw = bbox[2]-bbox[0]
            except Exception:
                tw = 700
            lx = (W - tw) // 2
            draw.text((lx-offset, logo_y-offset), logo_text, font=f_logo, fill=(*C_ORANGE[:3], int(40*logo_p)))
            draw.text((lx+offset, logo_y-offset), logo_text, font=f_logo, fill=(*C_ORANGE[:3], int(40*logo_p)))

        col = tuple(int(c * logo_p) for c in C_WHITE)
        draw_text_centered(draw, logo_text, logo_y, f_logo, col)

    # Truck icon
    truck_p = ease_out(alpha(t, 1.2, 2.5))
    if truck_p > 0.01:
        # Scale + fade
        tr_col = tuple(int(c * truck_p) for c in C_ORANGE)
        draw_truck(draw, W//2 - 90, H//2 + 30, scale=truck_p * 0.9, color=tr_col)

    # Tagline
    tag_p = ease_out(alpha(t, 2.0, 3.5))
    if tag_p > 0.01:
        f_tag = get_font(42)
        tag_col = tuple(int(c * tag_p) for c in C_LGRAY)
        draw_text_centered(draw, "Built for Truckers. Engineered for the Road.", H//2 + 160, f_tag, tag_col)

    # Orange accent line
    line_p = ease_out(alpha(t, 2.2, 3.5))
    if line_p > 0.01:
        lw = int(400 * line_p)
        draw.line([(W//2 - lw//2, H//2 + 150), (W//2 + lw//2, H//2 + 150)], fill=C_ORANGE, width=3)

    return np.array(img)


# ═══════════════════════════════════════════════════════════════════════════════
# SCENE 2: GPS Tracking (4–10s)
# ═══════════════════════════════════════════════════════════════════════════════

def make_scene2(t):
    """Animated route line + phone mockup + GPS text."""
    img = Image.new("RGB", (W, H), C_BLUE)
    draw = ImageDraw.Draw(img)

    # Grid map
    grid_col = (30, 50, 90)
    for gx in range(0, W, 60):
        draw.line([(gx, 0), (gx, H)], fill=grid_col, width=1)
    for gy in range(0, H, 60):
        draw.line([(0, gy), (W, gy)], fill=grid_col, width=1)

    # Route path points (on left/center portion)
    route_pts = [
        (150, 800), (250, 720), (400, 680), (500, 580),
        (600, 500), (650, 420), (720, 350), (800, 300),
        (880, 350), (950, 280), (1050, 240),
    ]
    # Animate: draw up to `progress` of route
    route_p = ease_in_out(clamp(t / 4.0))
    n_pts = len(route_pts) - 1
    n_draw = int(route_p * n_pts)
    frac = (route_p * n_pts) - n_draw

    drawn = route_pts[:n_draw+1]
    if n_draw < n_pts and frac > 0:
        p1 = route_pts[n_draw]
        p2 = route_pts[n_draw+1]
        mid = (int(p1[0] + (p2[0]-p1[0])*frac), int(p1[1] + (p2[1]-p1[1])*frac))
        drawn = drawn + [mid]

    # Draw completed path (white dashed feel)
    if len(drawn) >= 2:
        draw.line(drawn, fill=(100, 120, 160), width=6)
    # Draw active orange segment
    if len(drawn) >= 2:
        seg_len = max(3, len(drawn))
        recent = drawn[max(0, seg_len-5):]
        if len(recent) >= 2:
            draw.line(recent, fill=C_ORANGE, width=8)
        # Moving dot
        last = drawn[-1]
        r = 10
        draw.ellipse([last[0]-r, last[1]-r, last[0]+r, last[1]+r], fill=C_ORANGE, outline=C_WHITE, width=3)

    # Pin at start
    pin_r = 8
    sx, sy = route_pts[0]
    draw.ellipse([sx-pin_r, sy-pin_r, sx+pin_r, sy+pin_r], fill=C_TEAL, outline=C_WHITE, width=3)

    # Phone mockup (right side)
    phone_p = ease_out(alpha(t, 0.5, 2.0))
    ph_x = int(W - 300 + (1-phone_p)*200)
    ph_y = H//2
    draw_phone_mockup(draw, ph_x, ph_y, w=220, h=380, screen_color=(10,25,50))
    # Mini map inside phone
    mini_f = get_font(18)
    draw_text_at(draw, "GPS", ph_x - 20, ph_y - 60, mini_f, C_TEAL)
    draw_text_at(draw, "●  Active", ph_x - 30, ph_y - 30, mini_f, C_DGREEN)

    # LEFT SIDE TEXTS
    txt_p = ease_out(alpha(t, 0.3, 1.5))
    txt_x = int(-400 + txt_p * 500)

    f_main = get_font(64, bold=True)
    f_sub  = get_font(38)
    f_cnt  = get_font(52, bold=True)

    draw_text_at(draw, "Real-Time GPS Tracking", txt_x, 120, f_main, C_WHITE)

    sub_p = ease_out(alpha(t, 0.8, 2.0))
    sub_x = int(-400 + sub_p * 500)
    draw_text_at(draw, "Never lose a mile", sub_x, 210, f_sub, C_LGRAY)

    # Counter animation
    cnt_p = ease_in_out(alpha(t, 1.5, 4.0))
    miles = int(2847 * cnt_p)
    cnt_x = int(-400 + min(1.0, cnt_p*3) * 500)
    draw_text_at(draw, f"{miles:,} miles logged", cnt_x, 310, f_cnt, C_TEAL)

    # Location pin icon (simple)
    px, py = 70, 140
    draw.ellipse([px-18, py-18, px+18, py+18], fill=C_ORANGE, outline=C_WHITE, width=3)
    draw.polygon([(px, py+28), (px-14, py+8), (px+14, py+8)], fill=C_ORANGE)

    return np.array(img)


# ═══════════════════════════════════════════════════════════════════════════════
# SCENE 3: Earnings Dashboard (10–16s)
# ═══════════════════════════════════════════════════════════════════════════════

def make_scene3(t):
    """Bar chart + counting earnings."""
    img = Image.new("RGB", (W, H), C_GREEN)
    draw = ImageDraw.Draw(img)

    # Background subtle lines
    for gy in range(0, H, 80):
        draw.line([(0, gy), (W, gy)], fill=(30,70,50), width=1)

    # HEADLINE
    f_main = get_font(64, bold=True)
    f_sub  = get_font(38)
    f_big  = get_font(100, bold=True)
    f_label= get_font(26)

    head_p = ease_out(alpha(t, 0.0, 1.0))
    head_x = int(-400 + head_p * 500)
    draw_text_at(draw, "Track Every Dollar You Earn", head_x, 80, f_main, C_WHITE)

    # Dollar icon
    draw_text_at(draw, "$", 70, 70, get_font(80, bold=True), C_TEAL, shadow=False)
    draw.ellipse([50, 60, 130, 180], outline=C_TEAL, width=4)

    # Earnings counter (center-right)
    earn_p = ease_in_out(alpha(t, 0.5, 4.5))
    earnings = int(4250 * earn_p)
    earn_col = (int(C_TEAL[0]), int(C_TEAL[1]*earn_p + 255*(1-earn_p)), int(C_TEAL[2]))
    earn_col = C_TEAL
    draw_text_centered(draw, f"${earnings:,}", 180, f_big, C_TEAL)
    draw_text_centered(draw, "This Week's Earnings", 310, f_sub, C_LGRAY)

    # Bar chart
    bar_data = [
        ("Mon", 420), ("Tue", 680), ("Wed", 590), ("Thu", 820),
        ("Fri", 710), ("Sat", 780), ("Sun", 250)
    ]
    chart_x = 300
    chart_y = H - 120
    chart_h = 350
    bar_w   = 100
    bar_gap  = 30
    max_val  = 900

    chart_p = ease_in_out(alpha(t, 0.8, 4.0))

    for i, (label, val) in enumerate(bar_data):
        bx = chart_x + i * (bar_w + bar_gap)
        bar_h_full = int(chart_h * val / max_val)
        bar_h_now  = int(bar_h_full * chart_p)

        # Bar background (ghost)
        draw.rectangle([bx, chart_y - bar_h_full, bx+bar_w, chart_y],
                        fill=(40, 80, 60), outline=None)
        # Actual animated bar
        grad_col = C_TEAL if val >= 700 else C_ORANGE
        draw.rectangle([bx, chart_y - bar_h_now, bx+bar_w, chart_y],
                        fill=grad_col)
        # Top highlight
        draw.rectangle([bx, chart_y - bar_h_now, bx+bar_w, chart_y - bar_h_now + 8],
                        fill=C_WHITE)

        # Label
        draw_text_at(draw, label, bx + bar_w//2, chart_y + 10, f_label, C_LGRAY, anchor="center")

        # Value above bar
        if chart_p > 0.8:
            val_p = alpha(t, 3.0, 4.5)
            if val_p > 0:
                draw_text_at(draw, f"${val}", bx + bar_w//2, chart_y - bar_h_now - 35,
                             f_label, C_WHITE, anchor="center")

    # Horizontal axis
    draw.line([(chart_x - 20, chart_y), (chart_x + len(bar_data)*(bar_w+bar_gap), chart_y)],
              fill=C_LGRAY, width=2)

    return np.array(img)


# ═══════════════════════════════════════════════════════════════════════════════
# SCENE 4: Load Management (16–22s)
# ═══════════════════════════════════════════════════════════════════════════════

def make_scene4(t):
    """Load list sliding in from right."""
    img = Image.new("RGB", (W, H), C_PURPLE)
    draw = ImageDraw.Draw(img)

    # Background lines
    for gx in range(0, W, 80):
        draw.line([(gx, 0), (gx, H)], fill=(35, 35, 70), width=1)

    f_main  = get_font(64, bold=True)
    f_sub   = get_font(34)
    f_label = get_font(26)
    f_badge = get_font(22, bold=True)

    head_p = ease_out(alpha(t, 0.0, 1.0))
    head_x = int(-400 + head_p * 500)
    draw_text_at(draw, "Manage Every Load", head_x, 80, f_main, C_WHITE)

    # Package icon
    pkg_cx, pkg_cy = 80, 100
    draw.rectangle([pkg_cx-30, pkg_cy-25, pkg_cx+30, pkg_cy+25], fill=C_ORANGE, outline=C_WHITE, width=3)
    draw.line([(pkg_cx-30, pkg_cy), (pkg_cx+30, pkg_cy)], fill=C_WHITE, width=3)
    draw.line([(pkg_cx, pkg_cy-25), (pkg_cx, pkg_cy+25)], fill=C_WHITE, width=2)

    # Load items
    loads = [
        {"id": "LD-2847", "from": "Dallas, TX",    "to": "Houston, TX",   "status": "DELIVERED", "rate": "$1,240"},
        {"id": "LD-2848", "from": "Houston, TX",   "to": "Memphis, TN",   "status": "IN TRANSIT","rate": "$980"},
        {"id": "LD-2849", "from": "Memphis, TN",   "to": "Chicago, IL",   "status": "SCHEDULED", "rate": "$1,560"},
        {"id": "LD-2850", "from": "Chicago, IL",   "to": "Detroit, MI",   "status": "PENDING",   "rate": "$720"},
    ]

    status_colors = {
        "DELIVERED":  C_TEAL,
        "IN TRANSIT": C_ORANGE,
        "SCHEDULED":  (100, 150, 255),
        "PENDING":    (160, 120, 0),
    }

    card_x_base = 200
    card_w = 1200
    card_h = 120
    start_y = 220

    for i, load in enumerate(loads):
        appear_p = ease_out(alpha(t, 0.3 + i*0.6, 0.9 + i*0.6))
        if appear_p <= 0:
            continue
        slide_x = int(W + (1-appear_p) * 500)
        cx_now  = card_x_base if appear_p >= 1.0 else min(card_x_base, slide_x)

        cy = start_y + i * (card_h + 20)

        # Card background
        draw.rounded_rectangle([cx_now, cy, cx_now+card_w, cy+card_h],
                                radius=12, fill=(40, 40, 70), outline=(60,60,100), width=2)

        if appear_p < 0.05:
            continue

        # ID
        draw_text_at(draw, load["id"], cx_now+20, cy+15, f_sub, C_ORANGE)

        # Route
        route_str = f"{load['from']}  →  {load['to']}"
        draw_text_at(draw, route_str, cx_now+20, cy+55, f_label, C_WHITE)

        # Rate
        draw_text_at(draw, load["rate"], cx_now + card_w - 200, cy+30, f_sub, C_TEAL)

        # Status badge
        sc = status_colors.get(load["status"], C_LGRAY)
        badge_w = 150
        bx = cx_now + card_w - 370
        by = cy + 25
        draw.rounded_rectangle([bx, by, bx+badge_w, by+40],
                                radius=8, fill=(*sc[:3], 60) if False else tuple(int(c*0.25) for c in sc),
                                outline=sc, width=2)
        draw_text_at(draw, load["status"], bx + badge_w//2, by+8, f_badge, sc, anchor="center")

    return np.array(img)


# ═══════════════════════════════════════════════════════════════════════════════
# SCENE 5: Security / Sign In (22–28s)
# ═══════════════════════════════════════════════════════════════════════════════

def make_scene5(t):
    """Shield, Google/Apple sign-in, security messaging."""
    img = Image.new("RGB", (W, H), C_BG)
    draw = ImageDraw.Draw(img)

    # Subtle radial bg
    for r in range(400, 50, -40):
        alpha_v = int(15 * (400 - r) / 400)
        draw.ellipse([W//2-r, H//2-r, W//2+r, H//2+r], fill=None, outline=(0, 30, 60), width=2)

    f_main  = get_font(64, bold=True)
    f_sub   = get_font(38)
    f_label = get_font(32)
    f_small = get_font(26)

    # HEADLINE
    head_p = ease_out(alpha(t, 0.0, 1.0))
    head_x = int(-400 + head_p * 500)
    draw_text_at(draw, "Secure Sign-In", head_x, 100, f_main, C_WHITE)
    draw_text_at(draw, "Your data. Always protected.", head_x, 190, f_sub, C_LGRAY)

    # Shield (center)
    shield_p = ease_out(alpha(t, 0.5, 2.0))
    sh_size = int(120 * shield_p)
    if sh_size > 5:
        draw_shield(draw, W//2, H//2, size=sh_size, color=C_TEAL)
        # Glow
        img = draw_glow(img, W//2, H//2, sh_size*3, C_TEAL, intensity=0.25*shield_p)
        draw = ImageDraw.Draw(img)

    # "Checkmark" text above shield
    check_p = ease_out(alpha(t, 2.0, 3.0))
    if check_p > 0:
        f_chk = get_font(48, bold=True)
        draw_text_centered(draw, "256-bit Encryption", H//2 - 200, f_small, tuple(int(c*check_p) for c in C_TEAL))

    # Google Sign-In button
    g_p = ease_out(alpha(t, 1.5, 2.5))
    g_x, g_y = W//2 - 400, H//2 + 180
    if g_p > 0.01:
        bw, bh = 340, 70
        g_x_now = int(g_x - (1-g_p)*300)
        draw.rounded_rectangle([g_x_now, g_y, g_x_now+bw, g_y+bh],
                                radius=12, fill=(30, 30, 30), outline=C_WHITE, width=2)
        # Colored G
        colors_g = [(219,68,55),(244,160,0),(15,157,88),(66,133,244)]
        for ci, color in enumerate(colors_g):
            angle = ci * 90
            gx2 = g_x_now + 35 + int(14 * math.cos(math.radians(angle)))
            gy2 = g_y + 35 + int(14 * math.sin(math.radians(angle)))
            draw.ellipse([gx2-8, gy2-8, gx2+8, gy2+8], fill=color)
        draw_text_at(draw, "Sign in with Google", g_x_now+65, g_y+18, f_label, C_WHITE, shadow=False)

    # Apple Sign-In button
    a_p = ease_out(alpha(t, 2.0, 3.0))
    a_x, a_y = W//2 + 60, H//2 + 180
    if a_p > 0.01:
        bw, bh = 320, 70
        a_x_now = int(a_x + (1-a_p)*300)
        draw.rounded_rectangle([a_x_now, a_y, a_x_now+bw, a_y+bh],
                                radius=12, fill=(240,240,240), outline=C_WHITE, width=2)
        # Apple logo (simple)
        ax2, ay2 = a_x_now + 40, a_y + 15
        draw.ellipse([ax2-14, ay2, ax2+14, ay2+38], fill=(30,30,30))
        draw.polygon([(ax2-8, ay2+8), (ax2, ay2-10), (ax2+8, ay2+8)], fill=(30,30,30))
        draw_text_at(draw, "Sign in with Apple", a_x_now+65, a_y+18, f_label, (30,30,30), shadow=False)

    # Security badges
    badges_p = ease_out(alpha(t, 3.0, 4.5))
    if badges_p > 0:
        badges = ["SSL Secured", "GDPR Compliant", "Zero Data Sharing"]
        bx_start = W//2 - 450
        for i, b in enumerate(badges):
            bx = bx_start + i * 310
            by = H - 120
            bx_now = int(bx + (1-badges_p)*200)
            draw.rounded_rectangle([bx_now, by, bx_now+280, by+50],
                                    radius=10, fill=(20,40,30), outline=C_TEAL, width=2)
            draw.ellipse([bx_now+12, by+14, bx_now+36, by+38], fill=C_TEAL)
            draw.polygon([(bx_now+18, by+26), (bx_now+22, by+30), (bx_now+30, by+20)],
                         fill=C_WHITE)
            draw_text_at(draw, b, bx_now+48, by+14, f_small, C_WHITE, shadow=False)

    return np.array(img)


# ═══════════════════════════════════════════════════════════════════════════════
# SCENE 6: CTA (28–30s)
# ═══════════════════════════════════════════════════════════════════════════════

def make_scene6(t):
    """Logo + Download CTA + fade out."""
    dur = 2.0
    fade_out = 1.0 - ease_in_out(clamp((t - 1.2) / 0.8))

    img = Image.new("RGB", (W, H), C_BG)
    draw = ImageDraw.Draw(img)

    f_logo  = get_font(100, bold=True)
    f_dl    = get_font(52, bold=True)
    f_sub   = get_font(34)
    f_badge = get_font(28)

    appear_p = ease_out(clamp(t / 0.8)) * fade_out

    # Logo
    col = tuple(int(c * appear_p) for c in C_WHITE)
    draw_text_centered(draw, "HaulWallet", H//2 - 180, f_logo, col)

    # Orange underline
    lw = int(300 * appear_p)
    draw.line([(W//2-lw, H//2-90), (W//2+lw, H//2-90)], fill=C_ORANGE, width=4)

    # Tagline
    tag_p = ease_out(alpha(t, 0.3, 1.0)) * fade_out
    tag_col = tuple(int(c * tag_p) for c in C_LGRAY)
    draw_text_centered(draw, "Built for Truckers. Engineered for the Road.", H//2 - 30, f_sub, tag_col)

    # Download button
    dl_p = ease_out(alpha(t, 0.5, 1.0)) * fade_out
    if dl_p > 0.01:
        btn_w, btn_h = 560, 90
        bx = W//2 - btn_w//2
        by = H//2 + 80
        draw.rounded_rectangle([bx, by, bx+btn_w, by+btn_h],
                                radius=16, fill=tuple(int(c*dl_p) for c in C_ORANGE))
        draw_text_centered(draw, "Download Free on Google Play", by+20, f_dl,
                           tuple(int(c*dl_p) for c in C_WHITE))

        # Google Play "badge" text
        badge_p = ease_out(alpha(t, 0.7, 1.2)) * fade_out
        if badge_p > 0.01:
            draw_text_centered(draw, "Available on Google Play · Free Download",
                               H//2 + 200, f_badge, tuple(int(c*badge_p) for c in C_TEAL))

    # Truck silhouette bottom
    truck_p = ease_out(alpha(t, 0.4, 1.0)) * fade_out
    if truck_p > 0.01:
        tc = tuple(int(c * truck_p * 0.5) for c in C_ORANGE)
        draw_truck(draw, W//2 - 100, H - 80, scale=0.7, color=tc)

    return np.array(img)


# ═══════════════════════════════════════════════════════════════════════════════
# TRANSITIONS
# ═══════════════════════════════════════════════════════════════════════════════

def make_transition(frame_a, frame_b, t):
    """Smooth cross-fade blend between two frames."""
    p = ease_in_out(t)
    a = np.array(frame_a, dtype=float)
    b = np.array(frame_b, dtype=float)
    return (a * (1-p) + b * p).astype(np.uint8)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN FRAME GENERATOR
# ═══════════════════════════════════════════════════════════════════════════════

# Scene boundaries (absolute time in seconds)
SCENE_BOUNDS = [
    (0.0,  4.0,  make_scene1),
    (4.0,  10.0, make_scene2),
    (10.0, 16.0, make_scene3),
    (16.0, 22.0, make_scene4),
    (22.0, 28.0, make_scene5),
    (28.0, 30.0, make_scene6),
]
TOTAL_DUR = 30.0
TRANS_DUR = 0.5  # seconds for cross-fade

def make_frame(t):
    """Return H×W×3 numpy array for time t."""
    # Find current scene
    curr_scene = SCENE_BOUNDS[0]
    for sb in SCENE_BOUNDS:
        if sb[0] <= t < sb[1]:
            curr_scene = sb
            break
    else:
        # Past end
        curr_scene = SCENE_BOUNDS[-1]

    sc_start, sc_end, sc_fn = curr_scene
    local_t = t - sc_start

    # Check if we're in a transition at scene boundary
    for i, (s, e, fn) in enumerate(SCENE_BOUNDS[:-1]):
        t_end = e
        t_start_trans = t_end - TRANS_DUR
        if t_start_trans <= t <= t_end + TRANS_DUR:
            # We're in a transition window
            next_s, next_e, next_fn = SCENE_BOUNDS[i+1]
            frac = (t - t_start_trans) / (TRANS_DUR * 2)
            frac = clamp(frac)
            frame_a = sc_fn(t - s)
            frame_b = next_fn(t - next_s)
            return make_transition(frame_a, frame_b, frac)

    frame = sc_fn(local_t)
    return frame


# ═══════════════════════════════════════════════════════════════════════════════
# BUILD & EXPORT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("HaulWallet Promo Video Generator")
    print(f"Output: {OUTPUT_PATH}")
    print(f"Resolution: {W}x{H}, FPS: {FPS}, Duration: {TOTAL_DUR}s")

    # Ensure output directory
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    # Build video clip
    print("Generating frames...")
    clip = VideoClip(make_frame, duration=TOTAL_DUR)
    clip = clip.with_fps(FPS)

    # Add audio if available
    if os.path.exists(AUDIO_PATH):
        print(f"Adding audio: {AUDIO_PATH}")
        audio = AudioFileClip(AUDIO_PATH)
        # Trim or loop to match video length
        if audio.duration < TOTAL_DUR:
            print(f"Audio ({audio.duration:.1f}s) shorter than video, trimming video to match...")
            clip = clip.subclipped(0, audio.duration)
        else:
            audio = audio.subclipped(0, TOTAL_DUR)
        clip = clip.with_audio(audio)
    else:
        print("No audio file found, creating silent video.")

    # Export
    print("Encoding MP4 (this may take a minute)...")
    clip.write_videofile(
        OUTPUT_PATH,
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        ffmpeg_params=["-crf", "22", "-pix_fmt", "yuv420p"],
        logger="bar",
    )

    # Verify
    if os.path.exists(OUTPUT_PATH):
        size = os.path.getsize(OUTPUT_PATH)
        print(f"\nSuccess! Video created: {OUTPUT_PATH}")
        print(f"File size: {size / 1024 / 1024:.1f} MB")
    else:
        print("ERROR: Output file was not created!")
        sys.exit(1)


if __name__ == "__main__":
    main()
