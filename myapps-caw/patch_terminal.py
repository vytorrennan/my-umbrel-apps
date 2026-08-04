import re
import os

path = 'src/frontend/src/features/terminal/services/terminalRegistry.ts'
if not os.path.exists(path):
    print(f"File {path} not found")
    exit(1)

code = open(path).read()

# 1. Add rightClickSelectsWord and onSelectionChange handler
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

# 2. Patch attachCustomKeyEventHandler in wireInput for Ctrl+C / Ctrl+Shift+C / Cmd+C and Ctrl+Shift+V / Cmd+V
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

open(path, 'w').write(code)
print("Successfully patched terminalRegistry.ts")
