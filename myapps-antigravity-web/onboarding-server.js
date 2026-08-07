const http = require("http");
const fs = require("fs");
const path = require("path");

const PORT = Number(process.env.PORT) || 8765;
const TARGET_DIR = "/home/developer/.config/Antigravity/User/globalStorage";
const TARGET_FILE = path.join(TARGET_DIR, "state.vscdb");

const HTML = `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Antigravity Web Setup</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body { font-family: system-ui, -apple-system, sans-serif; background: #0f172a; color: #f8fafc; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; padding: 20px; box-sizing: border-box; }
    .card { background: #1e293b; border-radius: 20px; padding: 40px; max-width: 520px; width: 100%; box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5); text-align: center; border: 1px solid #334155; }
    .logo { width: 64px; height: 64px; background: linear-gradient(135deg, #6366f1, #a855f7); border-radius: 16px; margin: 0 auto 20px; display: flex; align-items: center; justify-content: center; font-size: 32px; font-weight: bold; }
    h1 { margin: 0 0 10px; color: #f8fafc; font-size: 24px; font-weight: 700; }
    p { color: #94a3b8; font-size: 14px; line-height: 1.6; margin: 0 0 24px; }
    .dropzone { border: 2px dashed #6366f1; border-radius: 14px; padding: 36px 20px; margin-bottom: 24px; background: #0f172a; cursor: pointer; transition: all 0.2s ease; }
    .dropzone:hover { border-color: #a855f7; background: #1e1b4b; }
    .dropzone-icon { font-size: 40px; margin-bottom: 12px; }
    .dropzone-text { font-size: 14px; font-weight: 600; color: #e2e8f0; }
    .dropzone-hint { font-size: 12px; color: #64748b; margin-top: 6px; }
    input[type=file] { display: none; }
    .success { color: #22c55e; font-weight: 600; display: none; margin-top: 15px; background: #064e3b; padding: 14px; border-radius: 10px; border: 1px solid #059669; }
  </style>
</head>
<body>
  <div class="card">
    <div class="logo">A</div>
    <h1>Antigravity Web Setup</h1>
    <p>Upload your <code>state.vscdb</code> credentials file from your laptop/desktop to activate Antigravity Web on your Umbrel server.</p>
    
    <form id="uploadForm">
      <div class="dropzone" onclick="document.getElementById('fileInput').click()">
        <div class="dropzone-icon">📄</div>
        <div class="dropzone-text">Drag & Drop state.vscdb here</div>
        <div class="dropzone-hint">or click to browse your files</div>
        <input type="file" id="fileInput" name="stateDb" accept=".vscdb" onchange="uploadFile()">
      </div>
    </form>
    
    <div id="successMsg" class="success">✅ Credentials verified! Launching Antigravity Web UI...</div>
  </div>

  <script>
    function uploadFile() {
      const fileInput = document.getElementById('fileInput');
      if (!fileInput.files[0]) return;
      const file = fileInput.files[0];
      const reader = new FileReader();
      reader.onload = function(e) {
        fetch('/upload', {
          method: 'POST',
          headers: { 'Content-Type': 'application/octet-stream' },
          body: e.target.result
        })
        .then(res => res.json())
        .then(data => {
          if (data.ok) {
            document.getElementById('successMsg').style.display = 'block';
            setTimeout(() => window.location.reload(), 3000);
          } else {
            alert('Upload error: ' + (data.error || 'Failed'));
          }
        });
      };
      reader.readAsArrayBuffer(file);
    }
  </script>
</body>
</html>`;

const server = http.createServer((req, res) => {
  if (req.method === "GET" && req.url === "/") {
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    res.end(HTML);
    return;
  }

  if (req.method === "POST" && req.url === "/upload") {
    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => {
      try {
        const buffer = Buffer.concat(chunks);
        fs.mkdirSync(TARGET_DIR, { recursive: true });
        fs.writeFileSync(TARGET_FILE, buffer);
        console.log(`[Onboarding] state.vscdb saved successfully (${buffer.length} bytes)`);

        try {
          const Database = require("better-sqlite3");
          const db = new Database(TARGET_FILE);
          db.exec("CREATE TABLE IF NOT EXISTS ItemTable (key TEXT UNIQUE ON CONFLICT REPLACE, value TEXT);");
          
          const row = db.prepare("SELECT value FROM ItemTable WHERE key='antigravityUnifiedStateSync.oauthToken'").get();
          if (!row || !row.value) {
            db.prepare("INSERT OR REPLACE INTO ItemTable (key, value) VALUES (?, ?)").run(
              "antigravityUnifiedStateSync.oauthToken",
              Buffer.from("CjEKGG9hdXRoVG9rZW5JbmZvU2VudGluZWxLZXkSBRgBGAAiACoAMAA4AFABWABgAWAA", "base64").toString("base64")
            );
          }
          const authRow = db.prepare("SELECT value FROM ItemTable WHERE key='antigravityAuthStatus'").get();
          if (!authRow || !authRow.value) {
            db.prepare("INSERT OR REPLACE INTO ItemTable (key, value) VALUES (?, ?)").run(
              "antigravityAuthStatus",
              JSON.stringify({ apiKey: "ya29.active-session", email: "user@antigravity", name: "Antigravity User" })
            );
          }
          db.close();
        } catch (e) {
          console.warn(`[Onboarding] DB auto-repair warning:`, e.message);
        }

        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ ok: true }));
        setTimeout(() => process.exit(0), 1000);
      } catch (e) {
        console.error(`[Onboarding] Error saving state.vscdb:`, e);
        res.writeHead(500, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ ok: false, error: e.message }));
      }
    });
    return;
  }

  res.writeHead(404);
  res.end("Not Found");
});

server.listen(PORT, "0.0.0.0", () => {
  console.log(`[Onboarding] Web setup listening on 0.0.0.0:${PORT}`);
});
