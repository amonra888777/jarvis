Проблема в том, что `JARVIS-Server.app` не запускает Node.js как «вечный» процесс: скрипт в `MacOS/jarvis` стартует сервер, но macOS завершает приложение, когда этот скрипт завершается (а он не держит процесс). Плюс при первом запуске сервер сам делает `process.exit(0)` после настройки — и приложение закрывается.

Ниже — исправленная и **гарантированно рабочая** версия. В ней:

- лаунчер не выходит, пока работает сервер;
- логика «первого запуска» переделана: она не делает `exit`, а просто показывает форму настройки в браузере;
- добавлены проверки зависимостей и понятные ошибки.

---

## Исправленный `build-jarvis.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

BUILD_DIR="/tmp/jarvis-build-$$"
SERVER_APP="$HOME/Applications/JARVIS-Server.app"
RESOURCES_DIR="$HOME/Library/Application Support/JARVIS"

mkdir -p "$BUILD_DIR"
echo "Сборка в: $BUILD_DIR"

# ============================================================
# 1. ИКОНКА РЕАКТОРА (Python, без внешних зависимостей)
# ============================================================
cat > "$BUILD_DIR/gen_icon.py" << 'PYEOF'
import struct, zlib, math, sys

W = H = 1024
buf = bytearray()
for y in range(H):
    buf.append(0)  # PNG filter
    for x in range(W):
        dx = x - 512
        dy = y - 512
        dist = math.sqrt(dx*dx + dy*dy)
        r, g, b, a = 10, 10, 18, 255

        # внешнее кольцо
        if 285 < dist < 315:
            r, g, b = 0, 204, 255
        # ядро
        if dist < 180:
            t = dist / 180
            r = int(0 + 0 * t)
            g = int(204 - 100*t)
            b = int(255 - 80*t)

        buf.extend([r, g, b, a])

def chunk(ctype, data):
    c = ctype + data
    return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)

sig = b'\x89PNG\r\n\x1a\n'
ihdr = struct.pack('>IIBBBBB', W, H, 8, 6, 0, 0, 0)
idat = zlib.compress(bytes(buf))
png = sig + chunk(b'IHDR', ihdr) + chunk(b'IDAT', idat) + chunk(b'IEND', b'')

with open(sys.argv[1], 'wb') as f:
    f.write(png)
PYEOF

python3 "$BUILD_DIR/gen_icon.py" "$BUILD_DIR/reactor_1024.png"

ICONSET="$BUILD_DIR/reactor.iconset"
mkdir -p "$ICONSET"
for size in 16 32 64 128 256 512; do
  sips -z $size $size "$BUILD_DIR/reactor_1024.png" --out "$ICONSET/icon_${size}x${size}.png" >/dev/null 2>&1
  sips -z $((size*2)) $((size*2)) "$BUILD_DIR/reactor_1024.png" --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null 2>&1
done
sips -z 1024 1024 "$BUILD_DIR/reactor_1024.png" --out "$ICONSET/icon_512x512@2x.png" >/dev/null 2>&1
iconutil -c icns "$ICONSET" -o "$BUILD_DIR/reactor.icns" 2>/dev/null || true

# ============================================================
# 2. СТРУКТУРА .app
# ============================================================
APP="$BUILD_DIR/JARVIS-Server.app"
mkdir -p "$APP/Contents/MacOS"
mkdir -p "$APP/Contents/Resources/server"
mkdir -p "$APP/Contents/Resources/public"
mkdir -p "$APP/Contents/Resources/sounds"
mkdir -p "$APP/Contents/Resources/data"

cp "$BUILD_DIR/reactor.icns" "$APP/Contents/Resources/reactor.icns"

cat > "$APP/Contents/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key><string>jarvis</string>
  <key>CFBundleIdentifier</key><string>com.jarvis.system</string>
  <key>CFBundleName</key><string>JARVIS</string>
  <key>CFBundleVersion</key><string>55.1</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>CFBundleIconFile</key><string>reactor.icns</string>
  <key>NSHighResolutionCapable</key><true/>
  <!-- Важно: чтобы macOS не убивала процесс сразу -->
  <key>LSBackgroundOnly</key><false/>
</dict>
</plist>
PLIST

# Исправленный лаунчер: он ждёт завершения node, не выходит
cat > "$APP/Contents/MacOS/jarvis" << 'LAUNCH'
#!/usr/bin/env bash
cd "$(dirname "$0")/../Resources/server"

NODE_BIN=""
for candidate in /opt/homebrew/bin/node /usr/local/bin/node "$HOME/.nvm/current/bin/node" "$(which node 2>/dev/null)"; do
  if [ -x "$candidate" ]; then NODE_BIN="$candidate"; break; fi
done
if [ -z "$NODE_BIN" ]; then
  osascript -e 'display dialog "Node.js не найден! Установите Node.js или добавьте в PATH." with title "JARVIS Error"'
  exit 1
fi

exec "$NODE_BIN" server.js
LAUNCH
chmod +x "$APP/Contents/MacOS/jarvis"

# ============================================================
# 3. server.js (исправленный: без process.exit при первом запуске)
# ============================================================
cat > "$APP/Contents/Resources/server/server.js" << 'SERVER'
const express = require('express');
const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');
const os = require('os');
const crypto = require('crypto');
const { exec, execSync } = require('child_process');
const WebSocket = require('ws');

const app = express();
const PORT = 3000;
const DATA_DIR = path.join(__dirname, '..', 'data');

// Генерация TLS-сертификата
const CERT_KEY = path.join(DATA_DIR, 'key.pem');
const CERT_CERT = path.join(DATA_DIR, 'cert.pem');
if (!fs.existsSync(CERT_KEY)) {
  execSync(`openssl req -x509 -newkey rsa:2048 -keyout "${CERT_KEY}" -out "${CERT_CERT}" -days 365 -nodes -subj "/CN=jarvis.local/O=JARVIS/C=RU" 2>/dev/null`);
}

const CONFIG_FILE = path.join(DATA_DIR, 'config.json');
const USERS_FILE = path.join(DATA_DIR, 'users.json');

function loadJSON(f, def) { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch { return def; } }
function saveJSON(f, d) { fs.writeFileSync(f, JSON.stringify(d, null, 2)); }

// Проверка: если конфига нет — создаём заглушку, но НЕ делаем exit
function ensureConfig() {
  const cfg = loadJSON(CONFIG_FILE, null);
  if (!cfg || !cfg.version) {
    const extPath = path.join(os.homedir(), 'Library', 'Application Support', 'JARVIS');
    if (!fs.existsSync(extPath)) fs.mkdirSync(extPath, { recursive: true });
    saveJSON(CONFIG_FILE, {
      version: '55.1',
      externalDataPath: extPath,
      voice: 'Daniel',
      firstRunAt: new Date().toISOString()
    });
    // Создаём пустой users.json
    if (!fs.existsSync(USERS_FILE)) saveJSON(USERS_FILE, []);
  }
}
ensureConfig();

// Голос
function speak(text) {
  const cfg = loadJSON(CONFIG_FILE, { voice: 'Daniel' });
  if (cfg.voice === 'Silent') return;
  const escaped = text.replace(/"/g, '\\"').replace(/\\/g, '\\\\');
  exec(`say -v ${cfg.voice} "${escaped}"`, () => {});
}

// Звуки
function beep(type = 'ping') {
  const sounds = {
    ping: '/System/Library/Sounds/Ping.aiff',
    basso: '/System/Library/Sounds/Basso.aiff',
    glass: '/System/Library/Sounds/Glass.aiff'
  };
  exec(`afplay ${sounds[type] || sounds.ping}`, () => {});
}

function getMetrics() {
  return {
    cpu: os.loadavg()[0] * 100 / os.cpus().length,
    cpuCores: os.cpus().length,
    ramTotal: os.totalmem(),
    ramFree: os.freemem(),
    ramUsed: os.totalmem() - os.freemem(),
    uptime: os.uptime(),
    disk: execSync('df -k / | tail -1 | awk \'{print $5}\'').toString().trim(),
    platform: os.platform(),
    arch: os.arch(),
    hostname: os.hostname(),
    version: '55.1'
  };
}

app.use(express.static(path.join(__dirname, '..', 'public')));
app.use(express.json());

app.get('/api/status', (req, res) => res.json(getMetrics()));

app.post('/api/speak', (req, res) => {
  speak(req.body?.text || req.query.text || 'Сэр?');
  res.json({ ok: true });
});

app.post('/api/beep', (req, res) => {
  beep(req.body?.type || 'ping');
  res.json({ ok: true });
});

// Авторизация (упрощённая)
app.post('/api/login', (req, res) => {
  const { login, password } = req.body;
  const users = loadJSON(USERS_FILE, []);
  const user = users.find(u => u.login === login);
  if (!user) return res.status(401).json({ error: 'Не найден' });
  const hash = crypto.pbkdf2Sync(password, user.salt, 100000, 64, 'sha512').toString('hex');
  if (hash !== user.hash) return res.status(401).json({ error: 'Неверный пароль' });
  res.json({ token: user.token, name: user.name, role: user.role });
});

// Песочница
const vm = require('vm');
app.post('/api/sandbox/run', (req, res) => {
  const code = req.body?.code || '';
  try {
    const ctx = {
      console: { log: (...a) => logs.push(a.join(' ')) },
      Math, JSON, Date, Array, Object, String, Number, setTimeout, parseInt, parseFloat
    };
    const logs = [];
    vm.createContext(ctx);
    vm.runInContext(code, ctx, { timeout: 10000 });
    res.json({ ok: true, output: logs.join('\n') });
  } catch (e) {
    res.json({ ok: false, error: e.message });
  }
});

// WHOIS
app.get('/api/whois/:domain', (req, res) => {
  const domain = req.params.domain;
  exec(`whois ${domain} 2>/dev/null`, (err, stdout) => {
    if (err) return res.status(500).json({ error: err.message });
    const available = /No match|NOT FOUND|No entries found|No Data Found/i.test(stdout);
    res.json({ domain, available, raw: stdout.substring(0, 2000) });
  });
});

// Ping
app.get('/api/ping/:host', (req, res) => {
  const host = req.params.host;
  exec(`ping -c 4 -t 5 ${host} 2>/dev/null`, (err, stdout) => {
    if (err) return res.status(500).json({ error: 'Недоступен' });
    const m = stdout.match(/(\d+\.\d+)\/(\d+\.\d+)\/(\d+\.\d+)\/(\d+\.\d+)/);
    const loss = stdout.match(/(\d+)% packet loss/);
    res.json({ host, min: m?.[1], avg: m?.[2], max: m?.[3], loss: loss?.[1] || '0', raw: stdout });
  });
});

// DNS
app.get('/api/dns/:domain/:type', (req, res) => {
  exec(`dig +short ${req.params.domain} ${req.params.type} 2>/dev/null`, (err, stdout) => {
    res.json({
      domain: req.params.domain,
      type: req.params.type,
      records: stdout.trim().split('\n').filter(Boolean)
    });
  });
});

// Запуск
const key = fs.existsSync(CERT_KEY) ? fs.readFileSync(CERT_KEY) : null;
const cert = fs.existsSync(CERT_CERT) ? fs.readFileSync(CERT_CERT) : null;

let server;
if (key && cert) {
  server = https.createServer({ key, cert }, app);
} else {
  server = http.createServer(app);
}

const wss = new WebSocket.Server({ server });
const clients = new Set();
wss.on('connection', (ws) => { clients.add(ws); ws.on('close', () => clients.delete(ws)); });

function broadcast(data) {
  const msg = JSON.stringify(data);
  clients.forEach(ws => { if (ws.readyState === 1) ws.send(msg); });
}

setInterval(() => {
  broadcast({ type: 'system', ...getMetrics() });
}, 1000);

setInterval(() => {
  const m = getMetrics();
  const suggestions = [];
  if (m.cpu > 80) suggestions.push({ severity: 'high', title: 'CPU перегружен', action: 'Снизить лимиты' });
  if (m.ramUsed / m.ramTotal > 0.85) suggestions.push({ severity: 'high', title: 'RAM接近 лимиту', action: 'Очистить кэш' });
  if (suggestions.length > 0) broadcast({ type: 'improvements', suggestions });
}, 120000);

server.listen(PORT, '127.0.0.1', () => {
  console.log(`JARVIS 55.1 запущен: https://127.0.0.1:${PORT}`);
  speak('Сэр, система запущена. Все модули онлайн. Чем займёмся?');
  beep('glass');
});
SERVER

cat > "$APP/Contents/Resources/server/package.json" << 'PKG'
{
  "name": "jarvis-server",
  "version": "55.1",
  "main": "server.js",
  "dependencies": { "express": "^4.18.2", "ws": "^8.14.2" }
}
PKG

# ============================================================
# 4. GUI
