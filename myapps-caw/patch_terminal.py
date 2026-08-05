import re
import os

reg_path = 'src/frontend/src/features/terminal/services/terminalRegistry.ts'
panel_path = 'src/frontend/src/features/terminal/components/TerminalPanel.tsx'
css_path = 'src/frontend/src/index.css'
ws_store_path = 'src/frontend/src/features/workspaces/stores/workspaceStore.ts'

# 1. Patch workspaceStore.ts for real-time multi-device tab & pane synchronization
if os.path.exists(ws_store_path):
    ws_code = open(ws_store_path).read()
    old_equal = 'if (aw.layouts[j].id !== bw.layouts[j].id) return false'
    new_equal = 'if (aw.layouts[j].id !== bw.layouts[j].id || JSON.stringify(aw.layouts[j].layout) !== JSON.stringify(bw.layouts[j].layout)) return false'
    ws_code = ws_code.replace(old_equal, new_equal)
    open(ws_store_path, 'w').write(ws_code)
    print("Patched workspaceStore.ts for multi-device real-time sync")

# 2. Patch TerminalPanel.tsx to allow touch scrolling on mobile and direct xterm scrollLines
if os.path.exists(panel_path):
    panel_code = open(panel_path).read()
    # Remove keyboard open check that blocked touch scrolling
    panel_code = panel_code.replace('if (keyboardOpenRef.current) return\n', '// disabled to allow touch scroll when keyboard open\n')
    
    # Enhance dispatchWheel to directly scroll xterm viewport lines on touch drag
    old_dispatch = 'accumDelta += deltaY'
    new_dispatch = '''const inst = getTerminal(terminalId)
      if (inst && inst.term) {
        const lines = Math.trunc(deltaY)
        if (lines !== 0) inst.term.scrollLines(lines)
      }
      accumDelta += deltaY'''
    panel_code = panel_code.replace(old_dispatch, new_dispatch)

    open(panel_path, 'w').write(panel_code)
    print("Patched TerminalPanel.tsx for touch scrolling")

# 3. Patch index.css touch-action
if os.path.exists(css_path):
    css_code = open(css_path).read()
    css_code = css_code.replace('touch-action: auto !important;', 'touch-action: pan-y !important;')
    open(css_path, 'w').write(css_code)
    print("Patched index.css")

# 4. Patch terminalRegistry.ts for soft-keyboard predictive text / IME composition and keybindings
if os.path.exists(reg_path):
    code = open(reg_path).read()

    # Add rightClickSelectsWord and onSelectionChange handler
    old_make = 'theme,\n  })'
    new_make = '''theme, rightClickSelectsWord: true,
  })
  term.onSelectionChange(() => {
    const sel = term.getSelection();
    if (sel) {
      try {
        const el = document.createElement('textarea');
        el.value = sel;
        el.style.position = 'fixed';
        el.style.left = '-9999px';
        document.body.appendChild(el);
        el.select();
        document.execCommand('copy');
        document.body.removeChild(el);
      } catch {}
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(sel).catch(() => {});
      }
    }
  })'''
    code = code.replace(old_make, new_make)

    # Disable autocorrect/autocomplete/IME composition buffer duplication on mobile textarea
    old_wire_start = 'function wireInput(inst: TerminalInstance) {'
    new_wire_start = '''function wireInput(inst: TerminalInstance) {
  if (inst.term.textarea) {
    const ta = inst.term.textarea;
    ta.setAttribute('autocorrect', 'off');
    ta.setAttribute('autocapitalize', 'none');
    ta.setAttribute('autocomplete', 'off');
    ta.setAttribute('spellcheck', 'false');
    ta.addEventListener('compositionend', () => {
      ta.value = '';
    });
  }'''
    code = code.replace(old_wire_start, new_wire_start)

    # Key handler patch for copy/paste
    patch_wire = '''inst.term.attachCustomKeyEventHandler((e) => {
    if (e.type === 'keydown') {
      const isCopyKey = (e.ctrlKey && e.shiftKey && (e.key === 'c' || e.key === 'C')) ||
                        (e.metaKey && (e.key === 'c' || e.key === 'C')) ||
                        (e.ctrlKey && !e.shiftKey && (e.key === 'c' || e.key === 'C') && inst.term.hasSelection());
      if (isCopyKey) {
        const sel = inst.term.getSelection();
        if (sel) {
          try {
            const el = document.createElement('textarea');
            el.value = sel;
            el.style.position = 'fixed';
            el.style.left = '-9999px';
            document.body.appendChild(el);
            el.select();
            document.execCommand('copy');
            document.body.removeChild(el);
          } catch {}
          if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(sel).catch(() => {});
          }
        }
        return false;
      }
      const isPasteKey = (e.ctrlKey && e.shiftKey && (e.key === 'v' || e.key === 'V')) ||
                         (e.metaKey && (e.key === 'v' || e.key === 'V'));
      if (isPasteKey) {
        if (navigator.clipboard && navigator.clipboard.readText) {
          navigator.clipboard.readText().then((text) => {
            if (text && inst.ws?.readyState === WebSocket.OPEN) {
              inst.ws.send(JSON.stringify({ type: 'input', data: text }));
            }
          }).catch(() => {});
        }
        return false;
      }
      if (e.ctrlKey && !e.altKey && !e.metaKey && (e.key === 'Enter' || e.key === 'Return')) {
        if (inst.ws?.readyState === WebSocket.OPEN) {
          inst.ws.send(JSON.stringify({ type: 'input', data: String.fromCharCode(10) }));
        }
        return false;
      }
    }
    return true;
  })'''

    pattern = r'inst\.term\.attachCustomKeyEventHandler\(\(e\) => \{[\s\S]*?return true\s*\}\)'
    code = re.sub(pattern, patch_wire, code)

    open(reg_path, 'w').write(code)
    print("Patched terminalRegistry.ts")
