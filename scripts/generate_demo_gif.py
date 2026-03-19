#!/usr/bin/env python3
"""
Generate an animated GIF demonstrating Synapse's core workflow using simple SVG->PNG conversion.
Shows: Event detection → Agent analysis → Notification
"""

import subprocess
import os
from pathlib import Path

# Configuration
GIF_OUTPUT = "demo.gif"
FRAMES_DIR = Path("frames_synapse")

# Colors
COLORS = {
    "bg": "#0F0F19",
    "accent_blue": "#00B4FF",
    "accent_purple": "#B400FF",
    "accent_green": "#00FF78",
    "accent_red": "#FF5050",
    "text_primary": "#F0F0F0",
    "text_secondary": "#A0A0B4",
}

AGENTS = [
    ("Dev Agent", COLORS["accent_blue"], "Analyzing code changes"),
    ("Security Agent", COLORS["accent_red"], "Scanning for vulnerabilities"),
    ("Ops Agent", COLORS["accent_green"], "Monitoring resources"),
    ("Life Agent", COLORS["accent_purple"], "Detecting cognitive load"),
]

def create_svg_frame(frame_num: int) -> str:
    """Create an SVG for a single frame."""
    width, height = 1200, 400
    
    svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <style>
      .title {{ font-size: 32px; font-weight: bold; font-family: Arial; }}
      .text-main {{ font-size: 18px; font-family: Arial; }}
      .text-small {{ font-size: 14px; font-family: Arial; }}
    </style>
  </defs>
  <rect width="{width}" height="{height}" fill="{COLORS['bg']}"/>
'''
    
    # Phase 1: Event Detection (frames 0-15)
    if frame_num < 16:
        progress = frame_num / 15
        opacity = min(1.0, progress)
        
        svg += f'  <text x="50" y="50" class="title" fill="{COLORS["accent_blue"]}">EVENT DETECTED</text>\n'
        svg += f'  <rect x="50" y="80" width="1100" height="80" fill="none" stroke="{COLORS["accent_blue"]}" stroke-width="2" opacity="{opacity}"/>\n'
        svg += f'  <text x="70" y="115" class="text-main" fill="{COLORS["accent_blue"]}" opacity="{opacity}">File Changed: auth.py | JWT validation logic modified</text>\n'
        
        dots = "." * ((frame_num % 4) + 1)
        svg += f'  <text x="70" y="145" class="text-small" fill="{COLORS["text_secondary"]}" opacity="{opacity}">Synapse processing{dots}</text>\n'
    
    # Phase 2: Agents Analyzing (frames 16-50)
    elif frame_num < 51:
        progress = (frame_num - 16) / 34
        
        svg += f'  <text x="50" y="50" class="title" fill="{COLORS["accent_purple"]}">AGENTS ANALYZING</text>\n'
        
        box_width, box_height, spacing = 260, 100, 15
        start_x, start_y = 50, 90
        
        for idx, (agent_name, agent_color, _) in enumerate(AGENTS):
            x = start_x + idx * (box_width + spacing)
            y = start_y
            
            agent_progress = max(0, min(1, progress * 4 - idx * 0.3))
            
            if agent_progress > 0:
                svg += f'  <rect x="{x}" y="{y}" width="{box_width}" height="{box_height}" fill="none" stroke="{agent_color}" stroke-width="2" opacity="{agent_progress}"/>\n'
                svg += f'  <text x="{x + 10}" y="{y + 30}" class="text-main" fill="{agent_color}" opacity="{agent_progress}">{agent_name}</text>\n'
                svg += f'  <text x="{x + 10}" y="{y + 55}" class="text-small" fill="{COLORS["text_secondary"]}" opacity="{agent_progress}">Processing ({int(agent_progress * 100)}%)</text>\n'
                
                bar_width = (box_width - 20) * agent_progress
                svg += f'  <rect x="{x + 10}" y="{y + 65}" width="{bar_width}" height="10" fill="{agent_color}" opacity="{agent_progress}"/>\n'
    
    # Phase 3: Results (frames 51-80)
    else:
        progress = (frame_num - 51) / 29
        
        svg += f'  <text x="50" y="50" class="title" fill="{COLORS["accent_green"]}">ANALYSIS COMPLETE</text>\n'
        svg += f'  <rect x="50" y="90" width="1100" height="260" fill="none" stroke="{COLORS["accent_green"]}" stroke-width="3"/>\n'
        
        results = [
            (0.5, 2.8, "Dev Agent", "Found 3 code patterns requiring review", COLORS["accent_blue"]),
            (0.5, 2.3, "Security Agent", "No vulnerabilities detected", COLORS["accent_green"]),
            (0.5, 1.8, "Ops Agent", "CPU: 45% | RAM: 3.2GB (normal)", COLORS["accent_green"]),
            (0.5, 1.3, "Life Agent", "High focus period - recommended continuation", COLORS["accent_purple"]),
        ]
        
        for idx, (x_norm, y_norm, agent, message, color) in enumerate(results):
            item_progress = max(0, min(1, (progress - idx * 0.15) * 4))
            
            y_px = 120 + idx * 55
            svg += f'  <text x="70" y="{y_px}" class="text-main" fill="{color}" opacity="{item_progress}">• {agent}:</text>\n'
            svg += f'  <text x="320" y="{y_px}" class="text-small" fill="{COLORS["text_primary"]}" opacity="{item_progress}">{message}</text>\n'
    
    svg += '</svg>'
    return svg

def generate_gif():
    """Generate the GIF by creating SVG frames."""
    print("🎬 Generating Synapse demo GIF...")
    
    FRAMES_DIR.mkdir(exist_ok=True)
    total_frames = 81
    
    # Check if ImageMagick is available
    try:
        subprocess.run(["convert", "--version"], capture_output=True, check=True)
        use_imagemagick = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        use_imagemagick = False
        print("  Note: ImageMagick not found, will create PNG frames instead")
    
    # Create SVG and convert frames
    for frame_num in range(total_frames):
        svg_content = create_svg_frame(frame_num)
        svg_path = FRAMES_DIR / f"frame_{frame_num:03d}.svg"
        png_path = FRAMES_DIR / f"frame_{frame_num:03d}.png"
        
        # Write SVG
        with open(svg_path, 'w') as f:
            f.write(svg_content)
        
        # Convert SVG to PNG using ImageMagick if available
        if use_imagemagick:
            subprocess.run(
                ["convert", "-density", "96", str(svg_path), str(png_path)],
                capture_output=True, check=False
            )
        
        print(f"  Frame {frame_num + 1}/{total_frames}...", end="\r")
    
    print(f"\n💾 Creating GIF...")
    
    # Try to create GIF using ImageMagick
    if use_imagemagick:
        try:
            png_files = sorted(FRAMES_DIR.glob("frame_*.png"))
            subprocess.run(
                ["convert", "-delay", "10", "-loop", "0"] + [str(p) for p in png_files] + [GIF_OUTPUT],
                capture_output=True, check=True
            )
            print(f"✓ Demo GIF created: {GIF_OUTPUT}")
            print(f"  Total frames: {total_frames}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Error creating GIF: {e}")
    
    print(f"✓ Frames created in: {FRAMES_DIR}/")
    print(f"  Total frames: {total_frames}")
    print(f"  To create GIF: convert -delay 10 -loop 0 {FRAMES_DIR}/frame_*.png {GIF_OUTPUT}")
    return True

if __name__ == "__main__":
    try:
        success = generate_gif()
        exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Error: {e}")
        exit(1)
