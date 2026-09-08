import os

path = os.path.expanduser("~/Projects/JARVIS-SuperServer/Resources/index.html")

# Создай папку Resources, если её нет
os.makedirs(os.path.dirname(path), exist_ok=True)

code = """\
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>JARVIS SuperServer</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; padding: 24px; background: #f5f5f7; }
    .chat { max-width: 720px; margin: 0 auto; background: white; border-radius: 12px; padding: 20px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
    .message { margin: 16px 0; padding: 12px 16px; border-radius: 8px; line-height: 1.5; }
    .user { background: #e3f2fd; color: #0d47a1; }
    .ai { background: #fafafa; color: #212121; }
    textarea { width: 100%; height: 96px; padding: 12px; border: 1px solid #ddd; border-radius: 8px; font-family: inherit; box-sizing: border-box; }
    button { background: #2196F3; color: white; padding: 10px 20px; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; }
    button:hover { background: #1976D2; }
    #status { margin-top: 16px; font-size: 13px; color: #666; }
  </style>
</head>
<body>
  <div class="chat">
    <h2>JARVIS SuperServer</h2>
    <div id="messages"></div>
    <textarea id="input" placeholder="Напиши сообщение…"></textarea>
    <button onclick="send()">Отправить</button>
    <div id="status"></div>
  </div>

  <script>
    const messages = document.getElementById('messages');
    const input = document.getElementById('input');

    async function send() {
      const text = input.value.trim();
      if (!text) return;
      addMessage('user', text);
      input.value = '';
      try {
        const res = await fetch('/chat', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({message: text, provider: 'auto'})
        });
        const data = await res.json();
        addMessage('ai', data.response || 'Ошибка ответа');
      } catch (e) {
        addMessage('ai', 'Ошибка соединения: ' + e.message);
      }
    }

    function addMessage(role, text) {
      const div = document.createElement('div');
      div.className = 'message ' + role;
      div.innerText = text;
      messages.appendChild(div);
      window.scrollTo(0, document.body.scrollHeight);
    }

    // Статус AI
    async function checkStatus() {
      try {
        const r = await fetch('/ai/status');
        const s = await r.json();
        const el = document.getElementById('status');
        const items = [];
        for (const [k, v] of Object.entries(s)) {
          const ok = v.available ? '✅' : '❌';
          items.push(`${ok} ${v.name}`);
        }
        el.innerText = 'AI провайдеры: ' + items.join(', ');
      } catch (e) {
        document.getElementById('status').innerText = 'Не удалось получить статус AI';
      }
    }
    checkStatus();
    setInterval(checkStatus, 10000);
  </script>
</body>
</html>
"""

with open(path, "w", encoding="utf-8") as f:
    f.write(code)

print(f"OK: index.html written to {path}")
print(f"Size: {len(code)} bytes")

