const fs = require("fs");
const filePath = "src/server/web-poc/server.ts";
let code = fs.readFileSync(filePath, "utf8");

// 1. Patch isAllowedClient
const target1 = "function isAllowedClient(remoteAddress: string | undefined): boolean {";
const replacement1 = `function isAllowedClient(remoteAddress: string | undefined): boolean {\n  if (process.env.ALLOW_REMOTE === "1" || process.env.ALLOW_ALL === "1") return true;`;

const target2 = "if (first === 100 && second >= 64 && second <= 127) return true;";
const replacement2 = `if (first === 100 && second >= 64 && second <= 127) return true;\n    if (first === 10 || (first === 192 && second === 168) || (first === 172 && second >= 16 && second <= 31)) return true;`;

code = code.replace(target1, replacement1);
code = code.replace(target2, replacement2);

// 2. Patch server creation to support NO_TLS mode and bind to 0.0.0.0
const targetServer = "const server = http2.createSecureServer({ key, cert, allowHTTP1: true }, handler);";
const replacementServer = `const useTls = process.env.NO_TLS !== "1" && process.env.HTTP !== "1";\n  const server = useTls ? http2.createSecureServer({ key, cert, allowHTTP1: true }, handler) : http.createServer(handler as any);`;

const targetListen = "server.listen(PORT, () => {";
const replacementListen = 'server.listen(PORT, "0.0.0.0", () => {';

code = code.replace(targetServer, replacementServer);
code = code.replace(targetListen, replacementListen);

fs.writeFileSync(filePath, code);
console.log("[Patch] Successfully patched server.ts for 0.0.0.0 binding & NO_TLS support");
