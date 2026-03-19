#!/usr/bin/env python3
"""
Generate an animated GIF using Python's tkinter (no external dependencies)+
Shows: Event detection → Agent analysis → Notification
"""

import tkinter as tk
from PIL import Image, ImageTk, ImageDraw, ImageFont
import os
import time

# Configuration
WIDTH, HEIGHT = 1200, 400
GIF_OUTPUT = "demo.gif"

# Colors (RGB tuples)
BG_DARK = (15, 15, 25)
ACCENT_BLUE = (0, 180, 255)
ACCENT_PURPLE = (180, 0, 255)
ACCENT_GREEN = (0, 255, 120)
ACCENT_RED = (255, 80, 80)
TEXT_PRIMARY = (240, 240, 240)
TEXT_SECONDARY = (160, 160, 180)

AGENTS = [
    ("Dev Agent", ACCENT_BLUE),
    ("Security Agent", ACCENT_RED),
    ("Ops Agent", ACCENT_GREEN),
    ("Life Agent", ACCENT_PURPLE),
]

def create_frame(frame_num):
    """Create a single frame of the animation."""
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_DARK)
    draw = ImageDraw.Draw(img)
    
    # Load fonts
    try:
        title_font = ImageFont.truetype("arial.ttf", 32)
        text_font = ImageFont.truetype("arial.ttf", 18)
        small_font = ImageFont.truetype("arial.ttf", 14)
    except:
        title_font = ImageFont.load_default()
        text_font = ImageFont.load_default()
        small_font = ImageFont.load_default()
    
    # Phase 1: Event Detection (frames 0-15)
    if frame_num < 16:
        progress = frame_num / 15
        
        draw.text((50, 20), "EVENT DETECTED", fill=ACCENT_BLUE, font=title_font)
        
        box_y = 80
        draw.rectangle((50, box_y, 1150, box_y + 80), outline=ACCENT_BLUE, width=2)
        draw.text((70, box_y + 20), "File Changed: auth.py | JWT validation logic modified", 
                  fill=ACCENT_BLUE, font=text_font)
        
        loading = "." * ((frame_num % 4) + 1)
        draw.text((70, box_y + 50), f"Synapse processing{loading}", 
                  fill=TEXT_SECONDARY, font=small_font)
    
    # Phase 2: Agents Analyzing (frames 16-50)
    elif frame_num < 51:
        progress = (frame_num - 16) / 34
        
        draw.text((50, 20), "AGENTS ANALYZING", fill=ACCENT_PURPLE, font=title_font)
        
        box_width, box_height, spacing = 260, 100, 15
        start_x, start_y = 50, 90
        
        for idx, (agent_name, agent_color) in enumerate(AGENTS):
            x = start_x + idx * (box_width + spacing)
            y = start_y
            
            agent_progress = max(0, min(1, progress * 4 - idx * 0.3))
            
            if agent_progress > 0:
                draw.rectangle((x, y, x + box_width, y + box_height), 
                              outline=agent_color, width=2)
                draw.text((x + 10, y + 10), agent_name, fill=agent_color, font=text_font)
                
                status = f"Processing ({int(agent_progress * 100)}%)"
                draw.text((x + 10, y + 40), status, fill=TEXT_SECONDARY, font=small_font)
                
                bar_width = int((box_width - 20) * agent_progress)
                draw.rectangle((x + 10, y + 65, x + 10 + bar_width, y + 75), 
                              fill=agent_color)
    
    # Phase 3: Results (frames 51-80)
    else:
        progress = (frame_num - 51) / 29
        
        draw.text((50, 20), "ANALYSIS COMPLETE", fill=ACCENT_GREEN, font=title_font)
        
        box_y = 90
        draw.rectangle((50, box_y, 1150, box_y + 250), outline=ACCENT_GREEN, width=3)
        
        results = [
            ("Dev Agent", "Found 3 code patterns requiring review", ACCENT_BLUE),
            ("Security Agent", "No vulnerabilities detected", ACCENT_GREEN),
            ("Ops Agent", "CPU: 45% | RAM: 3.2GB (normal)", ACCENT_GREEN),
            ("Life Agent", "High focus period - recommended continuation", ACCENT_PURPLE),
        ]
        
        for idx, (agent, message, color) in enumerate(results):
            item_progress = max(0, min(1, (progress - idx * 0.15) * 4))
            if item_progress > 0:
                y_offset = box_y + 20 + idx * 55
                draw.text((70, y_offset), f"- {agent}:", fill=color, font=text_font)
                draw.text((290, y_offset), message, fill=TEXT_PRIMARY, font=small_font)
    
    return img

def generate_gif():
    """Generate the complete demo GIF without PIL (using only fallback)."""
    print("🎬 Generating Synapse demo GIF...")
    
    frames = []
    total_frames = 81
    
    for frame_num in range(total_frames):
        try:
            print(f"  Creating frame {frame_num + 1}/{total_frames}...", end="\r")
            frame = create_frame(frame_num)
            frames.append(frame)
        except Exception as e:
            print(f"\n❌ Error on frame {frame_num}: {e}")
            return False
    
    print(f"\n💾 Saving GIF to {GIF_OUTPUT}...")
    
    try:
        # Save as animated GIF
        frames[0].save(
            GIF_OUTPUT,
            save_all=True,
            append_images=frames[1:],
            duration=100,  # 100ms per frame
            loop=0,  # infinite loop
            optimize=False
        )
        
        file_size = os.path.getsize(GIF_OUTPUT) / 1024
        print(f"✓ Demo GIF created: {GIF_OUTPUT}")
        print(f"  Size: {file_size:.1f} KB")
        print(f"  Duration: ~{total_frames * 100 / 1000:.1f}s")
        print(f"  Frames: {total_frames}")
        return True
    except Exception as e:
        print(f"❌ Error saving GIF: {e}")
        return False

if __name__ == "__main__":
    generate_gif()
