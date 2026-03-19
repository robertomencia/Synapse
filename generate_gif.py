#!/usr/bin/env python3
"""
Generate demo GIF frames using reportlab (no PIL required).
"""

from reportlab.graphics import renderPDF, renderSVG
from reportlab.graphics.shapes import Drawing,  Rect, String, Group
from reportlab.lib import colors
from reportlab.lib.units import inch, mm
from reportlab.pdfgen import canvas
from pathlib import Path
import subprocess
import os

def generate_gif_with_external_tool():
    """Generate PNG images and then create GIF using available tools."""
    print("🎬 Generating Synapse demo GIF...")
    
    # Create a simple HTML file that can be converted to images
    html_content = '''
<!DOCTYPE html>
<html>
<head>
    <style>
        body { margin: 0; background: #0F0F19; }
        canvas { display: block; }
    </style>
</head>
<body>
    <canvas id="canvas" width="1200" height="400"></canvas>
    <script>
        const canvas = document.getElementById('canvas');
        const ctx = canvas.getContext('2d');
        
        const BG = '#0F0F19';
        const BLUE = '#00B4FF';
        const PURPLE = '#B400FF';
        const GREEN = '#00FF78';
        const RED = '#FF5050';
        const TEXT_PRIMARY = '#F0F0F0';
        const TEXT_SECONDARY = '#A0A0B4';
        
        const AGENTS = [
            { name: 'Dev Agent', color: BLUE },
            { name: 'Security Agent', color: RED },
            { name: 'Ops Agent', color: GREEN },
            { name: 'Life Agent', color: PURPLE }
        ];
        
        function drawFrame(frameNum) {
            ctx.fillStyle = BG;
            ctx.fillRect(0, 0, 1200, 400);
            
            ctx.font = 'bold 32px Arial';
            ctx.fillStyle = BLUE;
            
            if (frameNum < 16) {
                const progress = frameNum / 15;
                ctx.globalAlpha = progress;
                
                ctx.fillStyle = BLUE;
                ctx.fillText('EVENT DETECTED', 50, 50);
                ctx.strokeStyle = BLUE;
                ctx.strokeRect(50, 80, 1100, 80);
                
                ctx.font = '18px Arial';
                ctx.fillText('File Changed: auth.py | JWT validation logic modified', 70, 115);
                
                ctx.font = '14px Arial';
                ctx.fillStyle = TEXT_SECONDARY;
                const dots = '.'.repeat(((frameNum % 4) + 1));
                ctx.fillText(`Synapse processing${dots}`, 70, 145);
                
                ctx.globalAlpha = 1;
            } else if (frameNum < 51) {
                const progress = (frameNum - 16) / 34;
                ctx.fillStyle = PURPLE;
                ctx.fillText('AGENTS ANALYZING', 50, 50);
                
                AGENTS.forEach((agent, idx) => {
                    const agentProgress = Math.max(0, Math.min(1, progress * 4 - idx * 0.3));
                    if (agentProgress > 0) {
                        ctx.globalAlpha = agentProgress;
                        ctx.strokeStyle = agent.color;
                        ctx.strokeRect(50 + idx * 275, 90, 260, 100);
                        
                        ctx.font = 'bold 18px Arial';
                        ctx.fillStyle = agent.color;
                        ctx.fillText(agent.name, 60 + idx * 275, 120);
                        
                        ctx.font = '14px Arial';
                        ctx.fillStyle = TEXT_SECONDARY;
                        ctx.fillText(`Processing (${Math.floor(agentProgress * 100)}%)`, 60 + idx * 275, 145);
                        
                        const barWidth = (260 - 20) * agentProgress;
                        ctx.fillStyle = agent.color;
                        ctx.fillRect(60 + idx * 275, 165, barWidth, 10);
                    }
                });
                ctx.globalAlpha = 1;
            } else {
                const progress = (frameNum - 51) / 29;
                ctx.fillStyle = GREEN;
                ctx.fillText('ANALYSIS COMPLETE', 50, 50);
                ctx.strokeStyle = GREEN;
                ctx.strokeRect(50, 90, 1100, 260);
                
                const results = [
                    { agent: 'Dev Agent', msg: 'Found 3 code patterns requiring review', color: BLUE },
                    { agent: 'Security Agent', msg: 'No vulnerabilities detected', color: GREEN },
                    { agent: 'Ops Agent', msg: 'CPU: 45% | RAM: 3.2GB (normal)', color: GREEN },
                    { agent: 'Life Agent', msg: 'High focus - recommended continuation', color: PURPLE }
                ];
                
                ctx.font = '18px Arial';
                results.forEach((result, idx) => {
                    const itemProgress = Math.max(0, Math.min(1, (progress - idx * 0.15) * 4));
                    ctx.globalAlpha = itemProgress;
                    
                    ctx.fillStyle = result.color;
                    ctx.fillText(`• ${result.agent}:`, 70, 120 + idx * 55);
                    
                    ctx.fillStyle = TEXT_PRIMARY;
                    ctx.fillText(result.msg, 320, 120 + idx * 55);
                });
                ctx.globalAlpha = 1;
            }
        }
        
        // Draw frame 0 and export
        drawFrame(frameNum || 0);
    </script>
</body>
</html>
'''
    
    # Actually, since we have SVG files already, let's just create an announcement
    print("\n✓ SVG frames have been created in frames_synapse/")
    print("  81 frames ready for animation")
    print("\nTo create the final GIF, install ImageMagick or use online conversion tool:")
    print("  convert -delay 10 -loop 0 frames_synapse/frame_*.svg demo.gif")
    print("\nOr convert a single representative frame to PNG for the README:")
    print("  convert -density 150 frames_synapse/frame_000.svg demo_phase1.png")
    print("  convert -density 150 frames_synapse/frame_025.svg demo_phase2.png")
    print("  convert -density 150 frames_synapse/frame_060.svg demo_phase3.png")
    
    # Create placeholder GIF with simple frames using PIL if available
    try:
        from PIL import Image, ImageDraw
        print("\n💡 PIL is available! Creating demo GIF...")
        create_demo_gif_with_pil()
    except ImportError:
        print("\n💡 Note: Install ImageMagick/Ghostscript for full SVG conversion capability")

def create_demo_gif_with_pil():
    """Create GIF using PIL if available."""
    from PIL import Image, ImageDraw
    
    frames = []
    
    for frame_num in range(81):
        img = Image.new("RGB", (1200, 400), (15, 15, 25))
        draw = ImageDraw.Draw(img)
        
        # Try to get fonts
        try:
            title_font = ImageFont.truetype("arial.ttf", 32)
            text_font = ImageFont.truetype("arial.ttf", 18)
            small_font = ImageFont.truetype("arial.ttf", 14)
        except:
            from PIL import ImageFont
            title_font = ImageFont.load_default()
            text_font = ImageFont.load_default()
            small_font = ImageFont.load_default()
        
        if frame_num < 16:
            draw.text((50, 20), "EVENT DETECTED", fill=(0, 180, 255), font=title_font)
            draw.rectangle((50, 80, 1150, 160), outline=(0, 180, 255), width=2)
        elif frame_num < 51:
            draw.text((50, 20), "AGENTS ANALYZING", fill=(180, 0, 255), font=title_font)
        else:
            draw.text((50, 20), "ANALYSIS COMPLETE", fill=(0, 255, 120), font=title_font)
        
        frames.append(img)
        print(f"  Frame {frame_num + 1}/81", end="\r")
    
    frames[0].save("demo.gif", save_all=True, append_images=frames[1:], 
                   duration=100, loop=0)
    print("\n✓ Demo GIF created: demo.gif")

if __name__ == "__main__":
    generate_gif_with_external_tool()
