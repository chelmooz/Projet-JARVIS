
---

## 2️⃣ Design System "ctOS par rubrique" — Maquette CSS

Voici le CSS pour le thème "ctOS" appliqué **uniquement** à l'onglet Outils (🔧) :

```css
/* ============================================================================
   Thème ctOS — Onglet Outils uniquement (scope #tab-tools)
   Inspiration Watch Dogs : scan de nœuds, terminal vert, topologie réseau
   ========================================================================= */

/* Variables locales au thème ctOS */
#tab-tools {
  --ctos-cyan: #00f0ff;
  --ctos-green: #00ff41;
  --ctos-dark: #0a0f14;
  --ctos-panel: rgba(10, 15, 20, 0.95);
  --ctos-border: rgba(0, 240, 255, 0.3);
  --ctos-scanline: rgba(0, 240, 255, 0.03);
}

/* Fond avec grille hexagonale subtile */
#tab-tools .tools-area {
  background:
    radial-gradient(circle at 50% 50%, rgba(0, 240, 255, 0.05) 0%, transparent 50%),
    repeating-linear-gradient(
      0deg,
      transparent,
      transparent 2px,
      var(--ctos-scanline) 2px,
      var(--ctos-scanline) 4px
    ),
    var(--ctos-dark);
  position: relative;
  overflow: hidden;
}

/* Effet de scanline animé */
#tab-tools .tools-area::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 100px;
  background: linear-gradient(
    180deg,
    transparent 0%,
    rgba(0, 240, 255, 0.1) 50%,
    transparent 100%
  );
  animation: scanline 8s linear infinite;
  pointer-events: none;
}

@keyframes scanline {
  0% { transform: translateY(-100%); }
  100% { transform: translateY(100vh); }
}

/* Cartes de diagnostic — style "panneau de contrôle" */
#tab-tools .tools-section {
  background: var(--ctos-panel);
  border: 1px solid var(--ctos-border);
  border-left: 3px solid var(--ctos-cyan);
  border-radius: 4px;
  padding: 16px;
  position: relative;
  backdrop-filter: blur(10px);
  box-shadow: 0 0 20px rgba(0, 240, 255, 0.1);
  transition: all 0.3s ease;
}

#tab-tools .tools-section:hover {
  border-left-color: var(--ctos-green);
  box-shadow: 0 0 30px rgba(0, 255, 65, 0.2);
  transform: translateX(4px);
}

/* Titres de section — style terminal */
#tab-tools .tools-section h4 {
  color: var(--ctos-cyan);
  font-family: 'Courier New', monospace;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 2px;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(0, 240, 255, 0.3);
  position: relative;
}

#tab-tools .tools-section h4::before {
  content: '>';
  color: var(--ctos-green);
  margin-right: 8px;
  animation: blink 1s infinite;
}

@keyframes blink {
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
}

/* Items de diagnostic — style "ligne de log" */
#tab-tools .tools-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
  font-family: 'Courier New', monospace;
  font-size: 11px;
  border-bottom: 1px solid rgba(0, 240, 255, 0.1);
}

#tab-tools .tools-item:last-child {
  border-bottom: none;
}

#tab-tools .tools-key {
  color: var(--ctos-cyan);
  text-transform: uppercase;
  letter-spacing: 1px;
}

#tab-tools .tools-val {
  color: var(--ctos-green);
  font-weight: 600;
}

/* Statuts OK/HS — style "LED" */
#tab-tools .tools-val::before {
  content: '';
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 8px;
  box-shadow: 0 0 10px currentColor;
  animation: pulse-led 2s infinite;
}

#tab-tools .tools-val:not(:contains('HS'))::before {
  background: var(--ctos-green);
  color: var(--ctos-green);
}

#tab-tools .tools-val:contains('HS')::before {
  background: #ff0040;
  color: #ff0040;
}

@keyframes pulse-led {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* Responsive */
@media (max-width: 768px) {
  #tab-tools .tools-section {
    margin-bottom: 12px;
  }
}