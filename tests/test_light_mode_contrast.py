import re
import pytest
from pathlib import Path

STYLE_CSS = Path(__file__).parent.parent / "static" / "assets" / "css" / "style.css"


def test_no_dark_hex_background_without_color():
    """Scan style.css pour trouver des fonds hex sombres sans color explicite"""
    css = STYLE_CSS.read_text(encoding="utf-8")
    
    # Patterns de fond hex sombre (6 ou 8 chars hex, commençant par 0-3 ou a-f)
    dark_hex_pattern = re.compile(r'background(?:-color)?\s*:\s*#([0-3a-fA-F][0-9a-fA-F]{5,7})\b')
    
    # Exclusions : .noscript-banner (volontairement rouge)
    exclusions = ['.noscript-banner']
    
    violations = []
    lines = css.split('\n')
    
    for i, line in enumerate(lines, 1):
        # Skip comment lines
        if line.strip().startswith('/*') or line.strip().startswith('//'):
            continue
            
        # Check if line is in an excluded block
        in_exclusion = False
        for exc in exclusions:
            if exc in css[max(0, css.find(line) - 200):css.find(line)]:
                in_exclusion = True
                break
        
        matches = dark_hex_pattern.findall(line)
        for match in matches:
            # Vérifier si le même bloc a une règle 'color:' dans les 20 lignes suivantes
            block_start = i - 1
            block_end = min(len(lines), i + 20)
            block = '\n'.join(lines[block_start:block_end])
            
            if 'color:' not in block:
                violations.append(f"Ligne {i}: background:#{match} sans 'color:' explicite -> {line.strip()}")
    
    if violations:
        pytest.fail("Fonds hex sombres sans color explicite trouvés:\n" + "\n".join(violations))


def test_msg_pre_has_color():
    """Vérifie que .msg pre a une couleur de texte explicite"""
    css = STYLE_CSS.read_text(encoding="utf-8")
    
    # Trouver la règle .msg pre
    msg_pre_match = re.search(r'\.msg\s+pre\s*\{([^}]+)\}', css)
    assert msg_pre_match, "Règle .msg pre non trouvée dans style.css"
    
    block = msg_pre_match.group(1)
    assert 'color:' in block, ".msg pre manque une déclaration 'color:' explicite"
    
    # Vérifier que la couleur n'est pas sombre (pas #000, #111, #222, etc.)
    color_match = re.search(r'color\s*:\s*(#[0-9a-fA-F]{3,8})', block)
    if color_match:
        color = color_match.group(1).lower()
        # Couleurs claires acceptables : #e6eaf3, #fff, #ffffff, etc.
        assert not color.startswith(('#0', '#1', '#2', '#3')), f".msg pre a une couleur sombre: {color}"


def test_msg_skill_card_has_color():
    """Vérifie que .msg .skill-card a une couleur de texte explicite"""
    css = STYLE_CSS.read_text(encoding="utf-8")
    
    # Trouver la règle .msg .skill-card
    skill_card_match = re.search(r'\.msg\s+\.skill-card\s*\{([^}]+)\}', css)
    assert skill_card_match, "Règle .msg .skill-card non trouvée dans style.css"
    
    block = skill_card_match.group(1)
    assert 'color:' in block, ".msg .skill-card manque une déclaration 'color:' explicite"
    
    color_match = re.search(r'color\s*:\s*(#[0-9a-fA-F]{3,8})', block)
    if color_match:
        color = color_match.group(1).lower()
        assert not color.startswith(('#0', '#1', '#2', '#3')), f".msg .skill-card a une couleur sombre: {color}"


def test_fb_breadcrumb_uses_var():
    """Vérifie que .fb-breadcrumb utilise var(--panel-2) au lieu de hex codé en dur"""
    css = STYLE_CSS.read_text(encoding="utf-8")
    
    # Trouver la règle .fb-breadcrumb
    breadcrumb_match = re.search(r'\.fb-breadcrumb\s*\{([^}]+)\}', css)
    assert breadcrumb_match, "Règle .fb-breadcrumb non trouvée dans style.css"
    
    block = breadcrumb_match.group(1)
    # Ne doit PAS avoir de background hex codé en dur
    assert 'background: #0e0e16' not in block, ".fb-breadcrumb utilise encore background hex codé en dur (#0e0e16)"
    assert 'var(--panel-2)' in block or 'var(--panel)' in block, ".fb-breadcrumb devrait utiliser var(--panel-2) ou var(--panel)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])