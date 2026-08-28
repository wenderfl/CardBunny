import os
import re

with open("app_mockup.html", "r", encoding="utf-8") as f:
    html = f.read()

concepts = [
    {
        "name": "app_mockup_1_neo_brutalism.html",
        "css": """
    :root {
        --bg-main: #FFFFFF;
        --bg-panel: #F0F0F0;
        --bg-input: #FFFFFF;
        --bg-input-alt: #E0E0E0;
        --bg-log: #F8F8F8;
        --accent: #FF3366;
        --accent-hover: #E02255;
        --text-primary: #111111;
        --text-secondary: #333333;
        --text-muted: #555555;
        --text-dark: #888888;
        --border-color: #000000;
    }
    .window {
        border: 4px solid black;
        border-radius: 0;
        box-shadow: 10px 10px 0px black;
    }
    .ctk-entry, .ctk-combo, .btn-small, .btn-play, .btn-footer, .local-files-panel, .tab-content, .field-list {
        border: 2px solid black;
        border-radius: 0;
        box-shadow: 3px 3px 0px black;
    }
    body { background-color: #E5E5E5; }
        """
    },
    {
        "name": "app_mockup_2_glassmorphism.html",
        "css": """
    :root {
        --bg-main: rgba(255, 255, 255, 0.1);
        --bg-panel: rgba(255, 255, 255, 0.05);
        --bg-input: rgba(255, 255, 255, 0.15);
        --bg-input-alt: rgba(255, 255, 255, 0.1);
        --bg-log: rgba(0, 0, 0, 0.2);
        --accent: rgba(229, 9, 20, 0.8);
        --accent-hover: rgba(229, 9, 20, 1);
        --text-primary: #FFFFFF;
        --text-secondary: #E0E0E0;
        --text-muted: #CCCCCC;
        --text-dark: #999999;
        --border-color: rgba(255, 255, 255, 0.2);
    }
    body { 
        background: linear-gradient(135deg, #1a1a2e, #16213e, #0f3460); 
    }
    .window {
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(255,255,255,0.2);
        box-shadow: 0 8px 32px rgba(0,0,0,0.5);
    }
        """
    },
    {
        "name": "app_mockup_3_cyberpunk.html",
        "css": """
    :root {
        --bg-main: #0B0C10;
        --bg-panel: #1F2833;
        --bg-input: #121A21;
        --bg-input-alt: #1A2229;
        --bg-log: #000000;
        --accent: #66FCF1;
        --accent-hover: #45A29E;
        --text-primary: #C5C6C7;
        --text-secondary: #66FCF1;
        --text-muted: #8A8F94;
        --text-dark: #4F555A;
        --border-color: #66FCF1;
    }
    body { background-color: #000; }
    .window {
        border: 1px solid var(--accent);
        box-shadow: 0 0 15px rgba(102, 252, 241, 0.3);
        border-radius: 4px;
    }
    .ctk-entry, .ctk-combo, .btn-small, .btn-play, .btn-footer {
        border-radius: 2px;
        border: 1px solid #45A29E;
    }
    .btn-play { background-color: transparent; border: 2px solid var(--accent); color: var(--accent); }
    .btn-play svg { fill: var(--accent); }
    .btn-play:hover { background-color: rgba(102, 252, 241, 0.2); }
        """
    },
    {
        "name": "app_mockup_4_light_minimal.html",
        "css": """
    :root {
        --bg-main: #FAFAFA;
        --bg-panel: #FFFFFF;
        --bg-input: #F0F0F0;
        --bg-input-alt: #E8E8E8;
        --bg-log: #FFFFFF;
        --accent: #0066FF;
        --accent-hover: #0052CC;
        --text-primary: #1A1A1A;
        --text-secondary: #4A4A4A;
        --text-muted: #7A7A7A;
        --text-dark: #A0A0A0;
        --border-color: #E0E0E0;
    }
    body { background-color: #E9ECEF; }
    .window {
        box-shadow: 0 4px 20px rgba(0,0,0,0.05);
        border: 1px solid #EAEAEA;
    }
    .ctk-entry, .ctk-combo {
        box-shadow: inset 0 1px 3px rgba(0,0,0,0.02);
    }
    .btn-play svg { fill: #FFF; }
        """
    },
    {
        "name": "app_mockup_5_monochrome_elegant.html",
        "css": """
    :root {
        --bg-main: #1C1C1E;
        --bg-panel: #2C2C2E;
        --bg-input: #3A3A3C;
        --bg-input-alt: #323234;
        --bg-log: #121214;
        --accent: #FFFFFF;
        --accent-hover: #E0E0E0;
        --text-primary: #FFFFFF;
        --text-secondary: #EBEBF5;
        --text-muted: #8E8E93;
        --text-dark: #636366;
        --border-color: #38383A;
    }
    body { background-color: #000000; }
    .btn-play {
        background-color: var(--accent);
    }
    .btn-play svg { fill: #000; }
    .step.active { color: #000; }
    .btn-save, .btn-confirm { color: #000; }
        """
    }
]

for concept in concepts:
    root_pattern = r":root\s*\{[^}]+\}"
    new_html = re.sub(root_pattern, "", html) 
    
    style_tag = "<style>"
    new_html = new_html.replace(style_tag, style_tag + "\n" + concept["css"])
    
    # Additional cleanup for light themes to make inline colors look good
    if "concept_1" in concept["name"] or "concept_4" in concept["name"]:
        # Change the combo box drop-down icon to dark grey
        new_html = new_html.replace('fill%3D%22%23B3B3B3%22', 'fill%3D%22%234A4A4A%22')
    
    with open(concept["name"], "w", encoding="utf-8") as f:
        f.write(new_html)

print("Generated 5 concepts.")
