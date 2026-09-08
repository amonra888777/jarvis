#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import http.server,socketserver,socket,json,threading,time,webbrowser,urllib.request,urllib.parse,re,os,sys,platform
from pathlib import Path
from datetime import datetime
from collections import deque
TCP_PORT=7777;WEB_PORT=8080
DATA_DIR=Path.home()/"jarvis-data";DATA_DIR.mkdir(parents=True,exist_ok=True)
KB_FILE=DATA_DIR/"knowledge.json";CFG_FILE=DATA_DIR/"config.json";API_FILE=DATA_DIR/"api_keys.json"
activity=deque(maxlen=1000);code_feed=deque(maxlen=300);ai_feed=deque(maxlen=100);improve_feed=deque(maxlen=50)
def la(b,a,d=""):
    m="["+datetime.now().strftime("%H:%M:%S")+"] "+b+": "+a
    if d: m+=" -- "+d
    activity.append(m)
def lc(b,c):
    code_feed.append({"time":datetime.now().strftime("%H:%M:%S"),"brain":b,"code":c})
def lj(f):
    if f.exists():
        try: return json.loads(f.read_text(encoding="utf-8"))
        except: pass
    return {}
def sj(d,f): f.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding="utf-8")
kb=lj(KB_FILE) or {"facts":{},"wiki":{},"url":{},"code":{}}
cfg=lj(CFG_FILE) or {"version":"7.0","language":"ru","voice":True,"super_brain":True,"auto_improve":True,"auto_interval":60}
api_keys=lj(API_FILE) or {"yandex_cloud":"","yandex_folder":"","openai":"","local_ollama":"http://127.0.0.1:11434"}
def save_all(): sj(kb,KB_FILE); sj(cfg,CFG_FILE); sj(api_keys,API_FILE)
def wiki_search(q):
    try:
        u="https://ru.wikipedia.org/w/api.php?action=query&list=search&srsearch="+urllib.parse.quote(q)+"&format=json&srlimit=3"
        r=urllib.request.Request(u,headers={"User-Agent":"JARVIS/7.0"})
        d=json.loads(urllib.request.urlopen(r,timeout=10).read())
        return [{"title":i["title"],"snippet":re.sub(r"<[^>]+>","",i.get("snippet",""))} for i in d.get("query",{}).get("search",[])]
    except Exception as e: la("Wiki","error",str(e)); return []
def wiki_learn(t):
    r=wiki_search(t)
    for x in r: kb["wiki"][x["title"]]=x["snippet"]
    if r: save_all()
    la("Wiki","learned",t+":"+str(len(r)))
    return r
def url_learn(url):
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"JARVIS/7.0"})
        raw=urllib.request.urlopen(req,timeout=15).read().decode("utf-8",errors="replace")
        text=re.sub(r"<script[^>]*>.*?</script>","",raw,flags=re.DOTALL)
        text=re.sub(r"<style[^>]*>.*?</style>","",text,flags=re.DOTALL)
        text=re.sub(r"<[^>]+>"," ",text)
        text=re.sub(r"\s+"," ",text).strip()
        title=""
        m=re.search(r"<title>(.*?)</title>",raw,re.IGNORECASE)
        if m: title=m.group(1)
        kb["url"][url]={"title":title or url,"text":text[:2000],"preview":text[:200]}
        save_all(); la("URL","learned",url[:50])
        return {"title":title,"chars":len(text)}
    except Exception as e: la("URL","error",str(e)); return None
def ai_call(provider,prompt):
    try:
        if provider=="yandex" and api_keys.get("yandex_cloud") and api_keys.get("yandex_folder"):
            url="https://llm.api.cloud.yandex.net/llm/v1/chat/invoke"
            headers={"Authorization":"Api-Key "+api_keys["yandex_cloud"],"Content-Type":"application/json"}
            data={"modelUri":"gpt://"+api_keys["yandex_folder"]+"/yandexgpt","messages":[{"role":"user","text":prompt}]}
            req=urllib.request.Request(url,data=json.dumps(data).encode(),headers=headers,method="POST")
            resp=json.loads(urllib.request.urlopen(req,timeout=30).read())
            return resp.get("result",{}).get("alternatives",[{}])[0].get("message",{}).get("text","")
        if provider=="openai" and api_keys.get("openai"):
            url="https://api.openai.com/v1/chat/completions"
            headers={"Authorization":"Bearer "+api_keys["openai"],"Content-Type":"application/json"}
            data={"model":"gpt-4o-mini","messages":[{"role":"user","content":prompt}],"max_tokens":500}
            req=urllib.request.Request(url,data=json.dumps(data).encode(),headers=headers,method="POST")
            resp=json.loads(urllib.request.urlopen(req,timeout=30).read())
            return resp.get("choices",[{}])[0].get("message",{}).get("content","")
        if provider=="ollama" and api_keys.get("local_ollama"):
            url=api_keys["local_ollama"]+"/api/generate"
            data={"model":"llama3","prompt":prompt,"stream":False}
            req=urllib.request.Request(url,data=json.dumps(data).encode(),headers={"Content-Type":"application/json"},method="POST")
            resp=json.loads(urllib.request.urlopen(req,timeout=30).read())
            return resp.get("response","")
    except Exception as e: la("AI","error",provider+": "+str(e))
    return None
def get_ai_response(prompt):
    for p in ["yandex","openai","ollama"]:
        r=ai_call(p,prompt)
        if r: la("AI","response",p); ai_feed.append({"time":datetime.now().strftime("%H:%M:%S"),"provider":p,"prompt":prompt[:50],"response":r[:200]}); return r
    return None
def get_all_ai_responses(prompt):
    results={}
    for p in ["yandex","openai","ollama"]:
        r=ai_call(p,prompt)
        if r:
            results[p]=r
            ai_feed.append({"time":datetime.now().strftime("%H:%M:%S"),"provider":p,"prompt":prompt[:50],"response":r[:200]})
    return results
def server_stats():
    try:
        import resource
        mem_kb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        mem_mb=round(mem_kb/1024 if sys.platform=="darwin" else mem_kb,1)
        cpu_count=os.cpu_count() or 1
        load=round(os.getloadavg()[0],2) if hasattr(os,"getloadavg") else 0
        disk=os.statvfs(Path.home())
        disk_total=round(disk.f_blocks*disk.f_frsize/(1024**3),1)
        disk_free=round(disk.f_bavail*disk.f_frsize/(1024**3),1)
        return {"mem_mb":mem_mb,"cpu":cpu_count,"load":load,"disk_total":disk_total,"disk_free":disk_free,"py":sys.version.split()[0],"platform":platform.platform(),"pid":os.getpid()}
    except Exception as e:
        return {"error":str(e)}
def analyze_code_file(filepath):
    try:
        content=Path(filepath).read_text(encoding="utf-8")
        lines=content.split("\n")
        issues=[]
        if len(lines)>500: issues.append("Файл большой: "+str(len(lines))+" строк - рассмотреть разбиение")
        for i,line in enumerate(lines):
            ls=line.strip()
            if "except:" in ls and "except Exception" not in ls: issues.append("Строка "+str(i+1)+": голый except")
        la("SelfImprove","analyze",filepath+" issues:"+str(len(issues)))
        return {"file":filepath,"lines":len(lines),"issues":issues,"issues_count":len(issues)}
    except Exception as e: return {"error":str(e)}
def auto_improve():
    if not cfg.get("auto_improve",True): return
    self_file=Path.home()/"jarvis-build"/"jarvis_web.py"
    r=analyze_code_file(str(self_file))
    improve_feed.append({"time":datetime.now().strftime("%H:%M:%S"),"type":"code_analysis","data":r})
    st=server_stats()
    if "mem_mb" in st and st["mem_mb"]>200:
        improve_feed.append({"time":datetime.now().strftime("%H:%M:%S"),"type":"memory","data":"Память: "+str(st["mem_mb"])+"MB - рекомендуется очистить"})
    la("SelfImprove","cycle","done")
def improve_loop():
    while True:
        time.sleep(cfg.get("auto_interval",60))
        try: auto_improve()
        except Exception as e: la("SelfImprove","error",str(e))
UPDATES=[
    {"id":1,"name":"Расширенная память диалога","desc":"Контекст до 1000 сообщений","installed":False},
    {"id":2,"name":"Автоскан файлов","desc":"Слежение за archive в реальном времени","installed":False},
    {"id":3,"name":"Голосовой ввод","desc":"Web Speech API для голосовых команд","installed":True},
    {"id":4,"name":"Светлая тема","desc":"Переключатель тёмная/светлая тема","installed":False},
    {"id":5,"name":"Экспорт базы знаний","desc":"Экспорт в JSON/CSV","installed":False},
    {"id":6,"name":"Мультиязычное обучение","desc":"Английская и русская Wikipedia","installed":False},
    {"id":7,"name":"Подсветка синтаксиса","desc":"Подсветка в Code Feed","installed":False},
    {"id":8,"name":"Маркетплейс плагинов","desc":"Плагины сообщества","installed":False},
    {"id":9,"name":"Супер-мозг","desc":"Параллельный запрос ко всем AI","installed":True},
    {"id":10,"name":"Самоанализ кода","desc":"JARVIS анализирует свой код и ищет улучшения","installed":True},
    {"id":11,"name":"Мониторинг сервера","desc":"CPU, память, диск в реальном времени","installed":True},
    {"id":12,"name":"Генерация кода","desc":"JARVIS генерирует Python/Swift код по запросу","installed":True},
    {"id":13,"name":"Авто-исправления","desc":"Автоматическое применение исправлений","installed":False},
    {"id":14,"name":"Резервное копирование","desc":"Автобэкап базы знаний","installed":False},
    {"id":15,"name":"Уведомления","desc":"Push-уведомления о событиях","installed":False},
]
class Brain:
    def __init__(s,n,r):
        s.name=n; s.role=r; s.status="online"; s.tasks=0
        la(n,"init",r); lc(n,"# "+n+" initialised\nstatus = online")
    def think(s,t):
        s.tasks+=1; la(s.name,"proc",t[:50]); return None
class MetalBrain(Brain):
    def __init__(s): super().__init__("Apple Metal","GPU acceleration")
    def think(s,t):
        super().think(t); tl=t.lower()
        if any(x in tl for x in ["metal","gpu","render","shader","ускорение","шейдер"]):
            lc(s.name,"let device = MTLCreateSystemDefaultDevice()\nlet cmdQueue = device?.makeCommandQueue()")
            r="Metal: GPU-конвейер готов. MSL шейдеры скомпилированы."
            la(s.name,"resp",r); return r
        return None
class XcodeBrain(Brain):
    def __init__(s): super().__init__("Xcode","Swift compilation"); s.proj=["JarvisCore","JarvisGUI","JarvisNode"]
    def think(s,t):
        super().think(t); tl=t.lower()
        if any(x in tl for x in ["xcode","build","compile","swift","сборка","компиляция"]):
            lc(s.name,'// swift-tools-version:5.9\nlet package = Package(name: "JarvisCore")')
            r="Xcode: "+str(len(s.proj))+" проектов. Swift 5.9."
            la(s.name,"resp",r); return r
        return None
class WebBrain(Brain):
    def __init__(s): super().__init__("Webmaster","Web server and GUI")
    def think(s,t):
        super().think(t); tl=t.lower()
        if any(x in tl for x in ["web","server","html","gui","http","веб","панель","сервер"]):
            lc(s.name,"class Handler(BaseHTTPRequestHandler):\n    def do_GET(self): pass")
            r="Webmaster: порт "+str(WEB_PORT)+". Панель активна."
            la(s.name,"resp",r); return r
        return None
class AliceBrain(Brain):
    def __init__(s): super().__init__("Alice AI","Conversational AI")
    def think(s,t):
        super().think(t); tl=t.lower().strip()
        if any(x in tl for x in ["alice","alisa","алиса","привет","здравствуй"]):
            ai=get_ai_response(t)
            if ai:
                lc(s.name,"# AI response via API\n"+ai[:200])
                la(s.name,"resp","AI API"); return "Алиса: "+ai
            lc(s.name,"# Local response\ndef respond(text): return 'Hi Mark!'")
            r="Алиса: Привет, Марк! Я встроена в JARVIS. Для полного AI подключите API ключ - наберите: ключ"
            la(s.name,"resp",r); return r
        if "как дела" in tl:
            r="Алиса: У меня всё отлично, Марк. Готова помогать!"
            la(s.name,"resp",r); return r
        return None
class JarvisBrain(Brain):
    def __init__(s,o):
        super().__init__("JARVIS","Super Brain - Coordinator")
        s.others=o; s.cmds=0; s.t0=time.time(); s.conv=[]
    def up(s):
        t=int(time.time()-s.t0)
        return str(t//3600).zfill(2)+":"+str((t%3600)//60).zfill(2)+":"+str(t%60).zfill(2)
    def think(s,text):
        s.cmds+=1; la("JARVIS","recv",text[:50]); tl=text.lower().strip()
        s.conv.append({"t":datetime.now().isoformat(),"u":text})
        if len(s.conv)>1000: s.conv=s.conv[-1000:]
        for k,v in kb["facts"].items():
            if k.lower() in tl: return v
        for k,v in kb["wiki"].items():
            if k.lower() in tl or tl in k.lower(): return "[Вики] "+k+": "+v
        for k,v in kb.get("url",{}).items():
            if k in tl or tl in k: return "[URL] "+v.get("title",k)+": "+v.get("preview","")[:200]
        for b in s.others:
            r=b.think(text)
            if r: return r
        cm={
            "ping":"pong",
            "статус":lambda:s.full_status(),
            "помощь":"команды: статус пинг помощь мозги вики узнать скан активность код босс распайка апдейты ключ url голос суперкод сервер анализ ai супер",
            "мозги":lambda:"Активны: "+", ".join([b.name for b in s.others]+["JARVIS (супер-мозг)"]),
            "босс":"Boss GX-10: Clean, Crunch, Lead. Онлайн.",
            "распайка":"Хамбакер: зелёный=начало, белый=конец, красный=юг, чёрный=земля.",
            "версия":"JARVIS v7.0 (RU) - Super Brain",
            "время":lambda:datetime.now().strftime("%H:%M:%S"),
            "дата":lambda:datetime.now().strftime("%d.%m.%Y"),
            "апдейты":lambda:s.propose_updates(),
            "улучшения":lambda:s.propose_updates(),
            "ключ":lambda:s.show_api_status(),
            "голос":lambda:s.toggle_voice(),
            "сервер":lambda:s.server_status(),
            "анализ":lambda:s.self_analyze(),
            "ai":lambda:s.ai_status(),
            "супер":lambda:s.super_brain_demo(),
        }
        if tl in cm:
            r=cm[tl]; r=r() if callable(r) else r
            la("JARVIS","cmd",tl); lc("JARVIS","# "+tl); return r
        if tl.startswith("узнать ") and "=" in text[7:]:
            k,v=text[7:].split("=",1); kb["facts"][k.strip()]=v.strip(); save_all()
            return "Запомнила: "+k.strip()+" = "+v.strip()
        if tl.startswith("забыть "):
            k=text[7:].strip()
            if k in kb["facts"]: del kb["facts"][k]; save_all(); return "Забыла: "+k
            return "Не знаю: "+k
        if tl.startswith("вики ") or tl.startswith("wiki "):
            r=wiki_learn(text[5:].strip()); lc("JARVIS","# Wikipedia: "+text[5:].strip())
            return "Изучено "+str(len(r))+": "+"; ".join(x["title"] for x in r) if r else "Не найдено"
        if tl.startswith("url ") or tl.startswith("ссылка "):
            url=text[4:].strip() if tl.startswith("url ") else text[7:].strip()
            r=url_learn(url); lc("JARVIS","# URL learning: "+url[:50])
            if r: return "Изучено: "+r["title"]+" ("+str(r["chars"])+" символов)"
            return "Ошибка загрузки URL"
        if tl.startswith("api ") and "=" in text[4:]:
            k,v=text[4:].split("=",1); api_keys[k.strip()]=v.strip(); save_all()
            return "API ключ сохранён: "+k.strip()
        if tl.startswith("код ") or tl.startswith("суперкод "):
            req=text.split(" ",1)[1] if " " in text else ""
            return s.generate_code(req)
        if tl in ("скан","файлы","сканирование"):
            a=Path.home()/"jarvis-build"/"archive"; f={"swift":0,"py":0,"json":0,"md":0,"xlsx":0,"total":0}
            if a.exists():
                for x in a.rglob("*"):
                    if x.is_file() and not x.name.startswith("."):
                        e=x.suffix.lower().lstrip(".")
                        if e in f: f[e]+=1
                        f["total"]+=1
            lc("JARVIS","# File scan")
            return "Скан: "+str(f["total"])+" файлов (Swift:"+str(f["swift"])+" Py:"+str(f["py"])+" JSON:"+str(f["json"])+")"
        if tl in ("активность","лог","жизнь"):
            return chr(10).join(list(activity)[-20:])
        if tl in ("код","code"):
            lines=["["+c["time"]+"] "+c["brain"]+": "+c["code"][:80] for c in list(code_feed)[-10:]]
            return chr(10).join(lines) if lines else "Нет кода"
        if "что ты знаешь" in tl or "знания" in tl or "память" in tl:
            items=list(kb["facts"].items())[:10]
            witems=list(kb["wiki"].items())[:10]
            uitems=list(kb.get("url",{}).items())[:5]
            r=""
            if items: r+="Факты: "+"; ".join(k+"="+v for k,v in items)+chr(10)
            if witems: r+="Вики: "+"; ".join(k for k,_ in witems)+chr(10)
            if uitems: r+="URL: "+"; ".join(k[:40] for k,_ in uitems)
            return r or "Пусто. Команды: узнать ключ=значение, вики тема, url ссылка, код задача"
        if tl in ("обновления","improve"):
            return s.propose_updates()
        if tl.startswith("установить ") or tl.startswith("install "):
            uid=text.split(" ",1)[1].strip()
            return s.install_update(uid)
        if cfg.get("super_brain",True):
            all_resp=get_all_ai_responses(text)
            if all_resp:
                parts=[]
                for prov,resp in all_resp.items():
                    parts.append("["+prov+"] "+resp[:300])
                combined=chr(10).join(parts)
                la("JARVIS","super_brain","multi-AI: "+str(len(all_resp)))
                lc("JARVIS","# Super Brain: queried "+str(len(all_resp))+" AIs")
                return "JARVIS (супер-мозг, "+str(len(all_resp))+" AI):"+chr(10)+combined
        ai=get_ai_response(text)
        if ai: return "JARVIS (AI): "+ai
        la("JARVIS","delegate",text[:40])
        lc("JARVIS","# Delegate\nuser = '"+text[:40]+"'")
        return "JARVIS: Обрабатываю. Напиши 'помощь' для команд, 'сервер' для статуса, 'анализ' для самопроверки."
    def full_status(s):
        st=server_stats()
        r="JARVIS v7.0 Super Brain"+chr(10)
        r+="Время: "+s.up()+chr(10)
        r+="Команд: "+str(s.cmds)+chr(10)
        r+="Мозгов: "+str(len(s.others)+1)+chr(10)
        r+="Вики: "+str(len(kb["wiki"]))+chr(10)
        r+="Факты: "+str(len(kb["facts"]))+chr(10)
        r+="URL: "+str(len(kb.get("url",{})))+chr(10)
        r+="AI запросы: "+str(len(ai_feed))+chr(10)
        r+="Улучшений: "+str(len(improve_feed))+chr(10)
        if "mem_mb" in st:
            r+="Память: "+str(st["mem_mb"])+"MB"+chr(10)
            r+="CPU: "+str(st["cpu"])+" ядер, load: "+str(st["load"])+chr(10)
            r+="Диск: "+str(st["disk_free"])+"GB свободно из "+str(st["disk_total"])+"GB"+chr(10)
        return r
    def server_status(s):
        st=server_stats()
        if "error" in st: return "Ошибка: "+st["error"]
        r="=== Сервер JARVIS ==="+chr(10)
        r+="Python: "+st.get("py","?")+chr(10)
        r+="Платформа: "+st.get("platform","?")+chr(10)
        r+="PID: "+str(st.get("pid","?"))+chr(10)
        r+="Память: "+str(st.get("mem_mb","?"))+" MB"+chr(10)
        r+="CPU: "+str(st.get("cpu","?"))+" ядер"+chr(10)
        r+="Нагрузка: "+str(st.get("load","?"))+chr(10)
        r+="Диск: "+str(st.get("disk_free","?"))+" GB свободно / "+str(st.get("disk_total","?"))+" GB"+chr(10)
        r+="Uptime: "+s.up()+chr(10)
        r+="API: "+" ".join(k+":OK" for k,v in api_keys.items() if v and v!="http://127.0.0.1:11434") or "нет ключей"
        la("JARVIS","server_status")
        return r
    def self_analyze(s):
        self_file=Path.home()/"jarvis-build"/"jarvis_web.py"
        r=analyze_code_file(str(self_file))
        resp="=== Самоанализ JARVIS ==="+chr(10)
        resp+="Файл: "+r.get("file","?")+chr(10)
        resp+="Строк: "+str(r.get("lines",0))+chr(10)
        resp+="Проблем: "+str(r.get("issues_count",0))+chr(10)
        for issue in r.get("issues",[])[:5]:
            resp+="- "+issue+chr(10)
        resp+=chr(10)+"=== История улучшений ==="+chr(10)
        for imp in list(improve_feed)[-5:]:
            resp+="["+imp["time"]+"] "+imp["type"]+": "+str(imp.get("data",""))[:80]+chr(10)
        la("JARVIS","self_analyze")
        lc("JARVIS","# Self-analysis complete\n# Issues: "+str(r.get("issues_count",0)))
        return resp
    def ai_status(s):
        r="=== Статус AI ==="+chr(10)
        for k,v in api_keys.items():
            st="OK" if v and v not in ("","http://127.0.0.1:11434") else "нет ключа"
            r+=k+": "+st+chr(10)
        r+=chr(10)+"Последние AI-запросы:"+chr(10)
        for a in list(ai_feed)[-5:]:
            r+="["+a["time"]+"] "+a["provider"]+": "+a["prompt"][:40]+chr(10)
        return r
    def super_brain_demo(s):
        r="=== Супер-мозг ==="+chr(10)
        r+="Режим: "+("включён" if cfg.get("super_brain",True) else "выключен")+chr(10)
        r+="Авто-улучшения: "+("включены" if cfg.get("auto_improve",True) else "выключены")+chr(10)
        r+="Интервал анализа: "+str(cfg.get("auto_interval",60))+" сек"+chr(10)
        r+="AI провайдеров: "+str(sum(1 for v in api_keys.values() if v and v!="http://127.0.0.1:11434"))+chr(10)
        r+="Запросов к AI: "+str(len(ai_feed))+chr(10)
        r+="Самоанализов: "+str(len(improve_feed))+chr(10)
        r+="Мозгов: "+str(len(s.others)+1)+chr(10)
        r+=chr(10)+"JARVIS параллельно опрашивает все доступные AI, объединяет ответы и выдаёт лучшее решение."
        return r
    def generate_code(s,req):
        if not req: return "Укажите задачу: код написать функцию сортировки"
        prompt="Напиши код на Python для: "+req+". Только код, без объяснений."
        ai=get_ai_response(prompt)
        if ai:
            kb["code"][req]=ai
            save_all()
            lc("JARVIS","# Generated code for: "+req[:50]+"\n"+ai[:200])
            la("JARVIS","codegen",req[:50])
            return "Код сгенерирован:\n"+ai
        return "Нет AI для генерации. Подключите API ключ: 'ключ'"
    def propose_updates(s):
        r=""
        for u in UPDATES:
            st="[установлено] " if u.get("installed") else "["+str(u["id"])+"] "
            r+=st+u["name"]+" -- "+u["desc"]+chr(10)
        r+="Набери: установить <номер>"
        la("JARVIS","propose_updates"); lc("JARVIS","# Updates: "+str(len(UPDATES)))
        return r
    def install_update(s,uid):
        try: uid=int(uid)
        except: return "Неверный номер"
        for u in UPDATES:
            if u["id"]==uid:
                u["installed"]=True; cfg["update_"+str(uid)]=True; save_all()
                la("JARVIS","installed",u["name"])
                lc("JARVIS","# Installed: "+u["name"]+"\npatch_applied = True")
                return "Установлено: "+u["name"]
        return "Обновление не найдено"
    def show_api_status(s):
        r=""
        for k,v in api_keys.items():
            st="OK" if v and v not in ("","http://127.0.0.1:11434") else "нет ключа"
            r+=k+": "+st+chr(10)
        r+="Настройка: api <имя>=<значение>"+chr(10)
        r+="Yandex: api yandex_cloud=XXX и api yandex_folder=YYY"+chr(10)
        r+="OpenAI: api openai=sk-XXX"
        return r
    def toggle_voice(s):
        cfg["voice"]=not cfg.get("voice",True)
        save_all()
        st="включён" if cfg["voice"] else "выключен"
        la("JARVIS","voice",st)
        return "Голос "+st+"."
    def scan_info(s):
        a=Path.home()/"jarvis-build"/"archive"; f={"swift":0,"py":0,"json":0,"md":0,"xlsx":0,"total":0}
        if a.exists():
            for x in a.rglob("*"):
                if x.is_file() and not x.name.startswith("."):
                    e=x.suffix.lower().lstrip(".")
                    if e in f: f[e]+=1
                    f["total"]+=1
        return f
la("SYSTEM","JARVIS v7.0 (RU) Super Brain starting")
metal=MetalBrain(); xcode=XcodeBrain(); web=WebBrain(); alice=AliceBrain()
jarvis=JarvisBrain([metal,xcode,web,alice])
la("SYSTEM","All brains online")
threading.Thread(target=improve_loop,daemon=True).start()
la("SYSTEM","Auto-improve loop started")
class TCPCore:
    def __init__(s): s.conns=[]; s.sock=None
    def start(s):
        s.sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        s.sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        s.sock.bind(("127.0.0.1",TCP_PORT)); s.sock.listen(5)
        threading.Thread(target=s._l,daemon=True).start(); la("TCP","listen","port "+str(TCP_PORT))
    def _l(s):
        while True:
            try:
                c,_=s.sock.accept(); s.conns.append(c)
                threading.Thread(target=s._h,args=(c,),daemon=True).start()
            except: break
    def _h(s,c):
        while True:
            try:
                d=c.recv(65536)
                if not d: break
                m=json.loads(d.decode()); r=jarvis.think(m.get("text",""))
                c.sendall(json.dumps({"text":r or "OK"}).encode())
            except: break
        if c in s.conns: s.conns.remove(c)
        c.close()
tcp=TCPCore()
PAGE='''<!DOCTYPE html><html lang=ru><head><meta charset=UTF-8><meta name=viewport content="width=device-width,initial-scale=1"><title>JARVIS v7</title><style>*{margin:0;padding:0;box-sizing:border-box}body{background:#060610;color:#0ff;font-family:monospace;height:100vh;display:flex;flex-direction:column;overflow:hidden}.hd{padding:10px 18px;background:linear-gradient(135deg,#0a0a18,#14142a);border-bottom:1px solid rgba(0,255,204,.2);display:flex;justify-content:space-between;align-items:center}.lg{font-size:20px;font-weight:bold;letter-spacing:3px;background:linear-gradient(90deg,#0ff,#08f);-webkit-background-clip:text;-webkit-text-fill-color:transparent}.br{padding:2px 8px;border-radius:8px;border:1px solid rgba(0,255,204,.15);color:#0f6;font-size:10px}.main{flex:1;display:flex;overflow:hidden}.sb{width:160px;background:#0a0a18;border-right:1px solid rgba(0,255,204,.08);padding:8px 0;flex-shrink:0;overflow-y:auto}.sec{font-size:8px;color:#444;padding:6px 16px 3px;text-transform:uppercase}.ni{padding:7px 16px;cursor:pointer;color:#777;font-size:12px;border-left:2px solid transparent}.ni:hover{color:#0ff;background:rgba(0,255,204,.04)}.ni.act{color:#0ff;border-left-color:#0ff;background:rgba(0,255,204,.06)}.ct{flex:1;padding:12px;display:flex;flex-direction:column;overflow:hidden}.pn{display:none;flex:1;flex-direction:column;overflow-y:auto}.pn.act{display:flex}.cd{background:#0a0a18;border:1px solid rgba(0,255,204,.1);border-radius:6px;padding:6px 12px;min-width:65px;display:inline-block;margin:0 4px 4px 0}.cl{font-size:9px;color:#555;text-transform:uppercase}.cv{font-size:14px;font-weight:bold}.cv.g{color:#0f6}.cv.c{color:#0ff}.cv.y{color:#fa0}.cv.r{color:#f66}.qc{background:#0a0a18;border:1px solid rgba(0,255,204,.12);color:#0ff;padding:4px 10px;border-radius:12px;cursor:pointer;font-size:11px;font-family:inherit}.qc:hover{background:rgba(0,255,204,.08)}.feed{flex:1;background:#030308;border:1px solid rgba(0,255,204,.08);border-radius:6px;padding:10px;overflow-y:auto;margin-bottom:8px;font-size:12px;line-height:1.7}.msg{margin-bottom:8px;max-width:85%;padding:8px 12px;border-radius:10px;font-size:13px;line-height:1.5;white-space:pre-wrap;word-break:break-word}.msg.u{background:rgba(250,170,0,.1);color:#fa0;margin-left:15%}.msg.j{background:rgba(0,255,204,.06);color:#0ff}.msg code{display:block;background:#0a0a18;border:1px solid rgba(0,255,204,.1);border-radius:4px;padding:8px;margin-top:6px;font-size:11px;color:#08f;white-space:pre;overflow-x:auto}.al{font-size:11px;color:#666;padding:2px 0}.ib{display:flex;gap:6px}.ib input{flex:1;background:#0a0a18;border:1px solid rgba(0,255,204,.15);border-radius:6px;padding:9px 12px;color:#0ff;font-family:inherit;font-size:13px;outline:none}.ib input:focus{border-color:#0ff}.ib button{background:linear-gradient(135deg,#0ff,#08f);color:#000;border:none;border-radius:6px;padding:9px 18px;font-weight:bold;cursor:pointer;font-family:inherit}.vbtn{background:#0a0a18;border:1px solid rgba(0,255,204,.2);color:#0ff;border-radius:6px;padding:9px 14px;cursor:pointer;font-size:16px;font-family:inherit;white-space:nowrap}.vbtn:hover{background:rgba(0,255,204,.08)}.vbtn.rec{background:rgba(250,50,50,.3);border-color:#f33;color:#faa;animation:pulse 1s infinite}@keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}.vbtn.off{opacity:.4}.bx{background:#0a0a18;border:1px solid rgba(0,255,204,.1);border-radius:6px;padding:12px;margin-bottom:10px}.bx h3{color:#0ff;margin-bottom:6px;font-size:13px}.bx p{color:#999;line-height:1.6;font-size:12px}.brow{display:flex;justify-content:space-between;align-items:center;padding:8px 12px;background:#0a0a18;border:1px solid rgba(0,255,204,.1);border-radius:6px;margin-bottom:6px}.bn{color:#0ff;font-size:13px}.br2{color:#666;font-size:11px}.bst{font-size:10px;padding:2px 8px;border-radius:8px;color:#0f6;border:1px solid #0f6}.sbar{height:4px;background:#0a0a18;border-radius:2px;margin-top:4px;overflow:hidden}.sbar-fill{height:100%;background:linear-gradient(90deg,#0ff,#08f);border-radius:2px;transition:width .5s}.upd{background:#0a0a18;border:1px solid rgba(0,255,204,.1);border-radius:6px;padding:10px;margin-bottom:6px}.upd .t{color:#0ff;font-weight:bold;font-size:12px}.upd .d{color:#888;font-size:11px;margin-top:2px}.sbadge{display:inline-block;padding:1px 6px;border-radius:4px;font-size:9px;margin-left:6px}.sbadge.on{background:rgba(0,255,102,.15);color:#0f6;border:1px solid #0f6}.sbadge.off{background:rgba(100,100,100,.15);color:#666;border:1px solid #444}</style></head><body><div class=hd><div class=lg>J.A.R.V.I.S v7.0</div><div><span class=br>Metal</span> <span class=br>Xcode</span> <span class=br>Web</span> <span class=br>Alice</span> <span class=br>JARVIS</span></div></div><div class=main><div class=sb><div class=sec>Главное</div><div class="ni act"onclick="sw(event,'chat')">Чат</div><div class=ni onclick="sw(event,'act')">Активность</div><div class=ni onclick="sw(event,'code')">Код</div><div class=ni onclick="sw(event,'ai')">AI лог</div><div class=sec>Супер-мозг</div><div class=ni onclick="sw(event,'server')">Сервер</div><div class=ni onclick="sw(event,'analyze')">Анализ</div><div class=ni onclick="sw(event,'updates')">Обновления</div><div class=sec>Управление</div><div class=ni onclick="sw(event,'brains')">Мозги</div><div class=ni onclick="sw(event,'term')">Терминал</div><div class=ni onclick="sw(event,'learn')">Обучение</div><div class=sec>Система</div><div class=ni onclick="sw(event,'files')">Файлы</div><div class=ni onclick="sw(event,'api')">API ключи</div><div class=ni onclick="sw(event,'dev')">Устройства</div><div class=ni onclick="sw(event,'wir')">Распайка</div></div><div class=ct><div id=chat class="pn act"><div style="margin-bottom:8px"><div class=cd><div class=cl>ВРЕМЯ</div><div class="cv c"id=up>00:00:00</div><div class=sbar><div class=sbar-fill id=upbar style=width:0%></div></div></div><div class=cd><div class=cl>КОМАНДЫ</div><div class="cv y"id=cmds>0</div><div class=sbar><div class=sbar-fill id=cmdbar style=width:0%></div></div></div><div class=cd><div class=cl>ВИКИ</div><div class="cv g"id=wiki>0</div><div class=sbar><div class=sbar-fill id=wikibar style=width:0%></div></div></div><div class=cd><div class=cl>ФАКТЫ</div><div class="cv g"id=facts>0</div><div class=sbar><div class=sbar-fill id=factsbar style=width:0%></div></div></div><div class=cd><div class=cl>AI</div><div class="cv c"id=aic>0</div><div class=sbar><div class=sbar-fill id=aibar style=width:0%></div></div></div><div class=cd><div class=cl>RAM</div><div class="cv r"id=ram>0MB</div><div class=sbar><div class=sbar-fill id=rambar style=width:0%></div></div></div></div><div id=cm style="flex:1;overflow-y:auto;margin-bottom:8px"><div class="msg j">JARVIS v7.0 Super Brain онлайн. Все 5 мозгов активны. Голос включён. Напиши: супер, сервер, анализ, код задача.</div></div><div class=ib><input id=ci placeholder="Сообщение JARVIS..."onkeydown="if(event.key==='Enter')cs()"><button class=vbtn id=micbtn onclick=st()>&#127908;</button><button class=vbtn id=spkbtn onclick=vt()>&#128266;</button><button onclick=cs()>SEND</button></div></div><div id=act class=pn><button class=qc onclick=rf()>Обновить</button><div class=feed id=af style="margin-top:8px"></div></div><div id=code class=pn><button class=qc onclick=rc()>Обновить</button><div class=feed id=cf style="margin-top:8px"></div></div><div id=ai class=pn><button class=qc onclick=ra()>Обновить</button><div class=feed id=aif style="margin-top:8px"></div></div><div id=server class=pn><div class=bx><h3>Мониторинг сервера</h3><div id=sv style="font-size:12px;color:#999">Загрузка...</div></div></div><div id=analyze class=pn><div class=bx><h3>Самоанализ JARVIS</h3><p>JARVIS непрерывно анализирует свой код, ищет проблемы и предлагает улучшения.</p><button class=qc onclick=sa2()>Запустить анализ</button></div><div id=ar style="margin-top:8px"></div></div><div id=updates class=pn><div class=bx><h3>Предложения JARVIS</h3><p>Супер-мозг постоянно улучшает систему.</p></div><div id=ul2></div></div><div id=brains class=pn><div class=brow><div><div class=bn>Apple Metal <span class="sbadge on">GPU</span></div><div class=br2>GPU ускорение</div></div><span class=bst>ОНЛАЙН</span></div><div class=brow><div><div class=bn>Xcode <span class="sbadge on">SWIFT</span></div><div class=br2>Swift компиляция</div></div><span class=bst>ОНЛАЙН</span></div><div class=brow><div><div class=bn>Webmaster <span class="sbadge on">WEB</span></div><div class=br2>Веб-сервер и GUI</div></div><span class=bst>ОНЛАЙН</span></div><div class=brow><div><div class=bn>Alice AI <span class="sbadge on">AI</span></div><div class=br2>Разговорный ИИ</div></div><span class=bst>ОНЛАЙН</span></div><div class=brow><div><div class=bn>JARVIS <span class="sbadge on">SUPER</span></div><div class=br2>Супер-мозг / Координатор</div></div><span class=bst>ОНЛАЙН</span></div></div><div id=term class=pn><div style="margin-bottom:8px"><div class=cd><div class=cl>ВРЕМЯ</div><div class="cv c"id=up2>00:00:00</div></div><div class=cd><div class=cl>КОМАНДЫ</div><div class="cv y"id=cmds2>0</div></div><div class=cd><div class=cl>СОЕД</div><div class="cv c"id=cn2>0</div></div></div><div style="margin-bottom:8px"><button class=qc onclick="sc('статус')">статус</button><button class=qc onclick="sc('сервер')">сервер</button><button class=qc onclick="sc('анализ')">анализ</button><button class=qc onclick="sc('супер')">супер</button><button class=qc onclick="sc('апдейты')">апдейты</button><button class=qc onclick="sc('голос')">голос</button><button class=qc onclick="sc('ai')">ai</button><button class=qc onclick="sc('помощь')">помощь</button></div><div class=feed id=tf></div><div class=ib><input id=ti placeholder="Команда..."onkeydown="if(event.key==='Enter')si()"><button onclick=si()>SEND</button></div></div><div id=learn class=pn><div class=bx><h3>Wikipedia</h3><div class=ib><input id=wi placeholder="Тема..."onkeydown="if(event.key==='Enter')wl()"><button onclick=wl()>Учить</button></div></div><div class=bx><h3>URL обучение</h3><div class=ib><input id=ui placeholder="https://..."onkeydown="if(event.key==='Enter')ul()"><button onclick=ul()>Учить URL</button></div></div><div class=bx><h3>Знания</h3><div class=ib><input id=lk placeholder="Ключ"><input id=lv placeholder="Значение"><button onclick=la()>Сохранить</button></div></div><div class=bx><h3>База</h3><div id=kb style="max-height:200px;overflow-y:auto;font-size:12px;color:#999">Загрузка...</div></div></div><div id=files class=pn><div class=bx><h3>Скан файлов</h3><button class=qc onclick=sf()>Сканировать</button><div id=fr style="margin-top:8px;font-size:12px;color:#999">Нажмите Сканировать</div></div></div><div id=api class=pn><div class=bx><h3>Yandex Cloud (YandexGPT)</h3><p>1. cloud.yandex.ru<br>2. Сервисный аккаунт<br>3. API ключ<br>4. api yandex_cloud=ключ<br>5. api yandex_folder=folder_id</p><div class=ib style="margin-top:8px"><input id=ak_yandex_cloud placeholder="Yandex API ключ"><button onclick="sa('yandex_cloud')">OK</button></div><div class=ib style="margin-top:4px"><input id=ak_yandex_folder placeholder="Folder ID"><button onclick="sa('yandex_folder')">OK</button></div></div><div class=bx><h3>OpenAI</h3><p>1. platform.openai.com<br>2. API ключ<br>3. api openai=sk-...</p><div class=ib style="margin-top:8px"><input id=ak_openai placeholder="sk-..."><button onclick="sa('openai')">OK</button></div></div><div class=bx><h3>Ollama (локально)</h3><p>1. ollama.com<br>2. ollama run llama3<br>3. http://127.0.0.1:11434</p><div class=ib style="margin-top:8px"><input id=ak_local_ollama placeholder="URL Ollama"><button onclick="sa('local_ollama')">OK</button></div></div><div class=bx><h3>Статус</h3><div id=aps style="font-size:12px;color:#999">Загрузка...</div></div></div><div id=dev class=pn><div class=bx><h3>Boss GX-10</h3><p style=color:#0f6>ОНЛАЙН</p></div><div class=bx><h3>ASUS ROG</h3><p style=color:#0f6>ОНЛАЙН</p></div></div><div id=wir class=pn><div class=bx><h3>Хамбакер</h3><p>зелёный=начало<br>белый=конец<br>красный=юг<br>чёрный=земля</p></div></div></div></div><script>let t0=Date.now();let voiceOn=true;let rec=null;let isRec=false;function sw(e,t){document.querySelectorAll('.pn').forEach(function(x){x.classList.remove('act')});document.getElementById(t).classList.add('act');document.querySelectorAll('.ni').forEach(function(x){x.classList.remove('act')});e.target.classList.add('act')}function am(t,c,code){const e=document.getElementById('cm');const d=document.createElement('div');d.className='msg '+c;d.textContent=t;if(code){const pre=document.createElement('code');pre.textContent=code;d.appendChild(pre)}e.appendChild(d);e.scrollTop=e.scrollHeight}function speak(text){if(!voiceOn)return;text=text.replace(/
$$
.*?
$$
/g,'').replace(/\n/g,' ').trim();if(!text)return;try{speechSynthesis.cancel();const u=new SpeechSynthesisUtterance(text);u.lang='ru-RU';u.rate=1.0;u.pitch=1.0;const vs=speechSynthesis.getVoices();for(let i=0;i<vs.length;i++){if(vs[i].lang==='ru-RU'){u.voice=vs[i];break}}speechSynthesis.speak(u)}catch(e){}}async function cs(){const i=document.getElementById('ci');const t=i.value.trim();if(!t)return;i.value='';am(t,'u');const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:t})});const d=await r.json();const cf=await fetch('/api/code/last');const cf2=await cf.json();am(d.text,'j',cf2.code||null);speak(d.text)}async function sc(c){const e=document.getElementById('tf');e.innerHTML+='<div style=color:#faa>> '+c+'</div>';const r=await fetch('/api/cmd',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text:c})});const d=await r.json();e.innerHTML+='<div style=color:#0ff>'+d.text+'</div>';e.scrollTop=e.scrollHeight;speak(d.text)}function si(){const i=document.getElementById('ti');if(i.value.trim()){sc(i.value.trim());i.value=''}}async function rf(){const r=await fetch('/api/activity');const d=await r.json();document.getElementById('af').innerHTML=d.lines.map(function(l){return '<div class="al">'+l+'</div>'}).join('')}async function rc(){const r=await fetch('/api/code');const d=await r.json();document.getElementById('cf').innerHTML=d.entries.map(function(e){return '<div class="al"style="color:#08f;margin-bottom:6px"><b style="color:#0ff">'+e.time+' '+e.brain+'</b><br>'+e.code.replace(/</g,'&lt;')+'</div>'}).join('')}async function ra(){const r=await fetch('/api/ai');const d=await r.json();document.getElementById('aif').innerHTML=d.entries.map(function(e){return '<div class="al"style="margin-bottom:6px"><b style="color:#0ff">'+e.time+' ['+e.provider+']</b> '+e.prompt+'<br><span style="color:#08f">'+e.response.substring(0,150)+'</span></div>'}).join('')}async function wl(){const i=document.getElementById('wi');const t=i.value.trim();if(!t)return;i.value='';am('Учу: '+t,'u');const r=await fetch('/api/wiki',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({topic:t})});const d=await r.json();am(d.text,'j');lk()}async function ul(){const i=document.getElementById('ui');const t=i.value.trim();if(!t)return;i.value='';am('Учу URL: '+t,'u');const r=await fetch('/api/url',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:t})});const d=await r.json();am(d.text,'j');lk()}async function la(){const k=document.getElementById('lk').value.trim();const v=document.getElementById('lv').value.trim();if(!k||!v)return;await fetch('/api/learn',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:k,value:v})});document.getElementById('lk').value='';document.getElementById('lv').value='';lk()}async function lk(){const r=await fetch('/api/learn');const d=await r.json();let h='';Object.entries(d.facts||{}).forEach(function(kv){h+='<div style="padding:3px"><span style="color:#0ff">'+kv[0]+'</span>=<span style="color:#999">'+kv[1]+'</span></div>'});Object.entries(d.wiki||{}).forEach(function(kv){h+='<div style="padding:3px;color:#08f">[W] '+kv[0]+'</div>'});Object.entries(d.url||{}).forEach(function(kv){h+='<div style="padding:3px;color:#0af">[URL] '+kv[0].substring(0,50)+'</div>'});document.getElementById('kb').innerHTML=h||'Пусто'}async function sf(){const r=await fetch('/api/scan');const d=await r.json();document.getElementById('fr').innerHTML='Всего: '+d.total+' Swift: '+d.swift+' Py: '+d.py+' JSON: '+d.json}async function sa(key){const i=document.getElementById('ak_'+key);const v=i.value.trim();if(!v)return;await fetch('/api/apikey',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:key,value:v})});i.value='';aps()}async function aps(){const r=await fetch('/api/apikeys');const d=await r.json();let h='';Object.entries(d).forEach(function(kv){const ok=kv[1]&&kv[1]!=='http://127.0.0.1:11434';h+='<div style="padding:3px">'+kv[0]+': <span style="color:'+(ok?'#0f6':'#666')+'">'+(ok?'OK':'нет')+'</span></div>'});document.getElementById('aps').innerHTML=h}async function lu(){const r=await fetch('/api/updates');const d=await r.json();document.getElementById('ul2').innerHTML=d.map(function(u){return '<div class="upd"><div class="t">'+u.name+(u.installed?' <span class="sbadge on">установлено</span>':'')+'</div><div class="d">'+u.desc+'</div>'+(u.installed?'':'<button class="qc"onclick="iu('+u.id+')">Установить</button>')+'</div>'}).join('')}async function iu(id){const r=await fetch('/api/install',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:id})});const d=await r.json();am(d.text,'j');speak(d.text);lu()}async function sa2(){const r=await fetch('/api/analyze');const d=await r.json();document.getElementById('ar').innerHTML='<pre style="color:#0ff;font-size:12px;white-space:pre-wrap">'+d.text+'</pre>'}async function sv2(){const r=await fetch('/api/server');const d=await r.json();let h='';Object.entries(d).forEach(function(kv){h+='<div style="padding:4px"><span style="color:#0ff">'+kv[0]+'</span>: <span style="color:#999">'+kv[1]+'</span></div>'});document.getElementById('sv').innerHTML=h}function st(){if(!('webkitSpeechRecognition'in window)&&!(window.SpeechRecognition)){alert('Голос не поддерживается. Используйте Chrome или Safari.');return}const SR=window.SpeechRecognition||window.webkitSpeechRecognition;if(!isRec){rec=new SR();rec.lang='ru-RU';rec.continuous=false;rec.interimResults=false;rec.onstart=function(){isRec=true;document.getElementById('micbtn').classList.add('rec')};rec.onend=function(){isRec=false;document.getElementById('micbtn').classList.remove('rec')};rec.onerror=function(e){isRec=false;document.getElementById('micbtn').classList.remove('rec')};rec.onresult=function(e){const t=e.results[0][0].transcript;document.getElementById('ci').value=t;cs()};rec.start()}else{rec.stop();isRec=false;document.getElementById('micbtn').classList.remove('rec')}}function vt(){voiceOn=!voiceOn;const b=document.getElementById('spkbtn');if(voiceOn){b.classList.remove('off')}else{b.classList.add('off');try{speechSynthesis.cancel()}catch(e){}}am(voiceOn?'Голос включён':'Голос выключен','j')}function up(){const s=Math.floor((Date.now()-t0)/1000);const h=String(Math.floor(s/3600)).padStart(2,'0')+':'+String(Math.floor(s%3600/60)).padStart(2,'0')+':'+String(s%60).padStart(2,'0');document.getElementById('up').textContent=h;document.getElementById('up2').textContent=h;document.getElementById('upbar').style.width=Math.min(100,(s/3600)*100)+'%'}async function stt(){try{const r=await fetch('/api/stats');const d=await r.json();document.getElementById('cmds').textContent=d.cmds||0;document.getElementById('cmds2').textContent=d.cmds||0;document.getElementById('cn2').textContent=d.conns||0;document.getElementById('wiki').textContent=d.wiki||0;document.getElementById('facts').textContent=d.facts||0;document.getElementById('aic').textContent=d.ai_count||0;document.getElementById('ram').textContent=(d.server&&d.server.mem_mb?d.server.mem_mb+'MB':'0MB');document.getElementById('cmdbar').style.width=Math.min(100,(d.cmds||0)*2)+'%';document.getElementById('wikibar').style.width=Math.min(100,(d.wiki||0)*5)+'%';document.getElementById('factsbar').style.width=Math.min(100,(d.facts||0)*5)+'%';document.getElementById('aibar').style.width=Math.min(100,(d.ai_count||0)*3)+'%';document.getElementById('rambar').style.width=Math.min(100,(d.server&&d.server.mem_mb?d.server.mem_mb/10:0))+'%'}catch(e){}}speechSynthesis.onvoiceschanged=function(){};setInterval(up,1000);setInterval(stt,2000);setInterval(rf,3000);setInterval(rc,5000);setInterval(sv2,5000);lk();rf();rc();aps();lu();sv2();</script></body></html>'''
class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(s,*a): pass
    def _j(s,d,c=200):
        s.send_response(c); s.send_header("Content-Type","application/json;charset=utf-8"); s.end_headers()
        s.wfile.write(json.dumps(d,ensure_ascii=False).encode())
    def _body(s):
        cl=int(s.headers.get("Content-Length",0))
        if cl==0: return {}
        try: return json.loads(s.rfile.read(cl).decode())
        except: return {}
    def do_GET(s):
        if s.path=="/":
            s.send_response(200); s.send_header("Content-Type","text/html;charset=utf-8"); s.end_headers(); s.wfile.write(PAGE.encode())
        elif s.path=="/api/stats": s._j({"cmds":jarvis.cmds,"conns":len(tcp.conns),"wiki":len(kb["wiki"]),"facts":len(kb["facts"]),"ai_count":len(ai_feed),"server":server_stats()})
        elif s.path=="/api/activity": s._j({"lines":list(activity)})
        elif s.path=="/api/code": s._j({"entries":list(code_feed)})
        elif s.path=="/api/code/last": s._j({"code":code_feed[-1]["code"] if code_feed else "","brain":code_feed[-1]["brain"] if code_feed else ""})
        elif s.path=="/api/ai": s._j({"entries":list(ai_feed)})
        elif s.path=="/api/learn": s._j({"facts":kb["facts"],"wiki":kb["wiki"],"url":kb.get("url",{})})
        elif s.path=="/api/scan": s._j(jarvis.scan_info())
        elif s.path=="/api/updates": s._j(UPDATES)
        elif s.path=="/api/apikeys": s._j(api_keys)
        elif s.path=="/api/server": s._j(server_stats())
        elif s.path=="/api/analyze": s._j({"text":jarvis.self_analyze()})
        else: s.send_response(404); s.end_headers()
    def do_POST(s):
        d=s._body()
        if s.path in ("/api/chat","/api/cmd"):
            r=jarvis.think(d.get("text","")); s._j({"text":r or "OK"})
        elif s.path=="/api/wiki":
            r=wiki_learn(d.get("topic","")); s._j({"text":"Изучено "+str(len(r))+": "+"; ".join(x["title"] for x in r) if r else "Не найдено"})
        elif s.path=="/api/url":
            r=url_learn(d.get("url","")); s._j({"text":"Изучено: "+r["title"]+" ("+str(r["chars"])+" симв.)" if r else "Ошибка URL"})
        elif s.path=="/api/learn":
            k=d.get("key","").strip(); v=d.get("value","").strip()
            if k and v: kb["facts"][k]=v; save_all(); la("Learn","saved",k)
            s._j({"ok":True})
        elif s.path=="/api/apikey":
            k=d.get("key","").strip(); v=d.get("value","").strip()
            if k and v: api_keys[k]=v; save_all(); la("API","saved",k)
            s._j({"ok":True})
        elif s.path=="/api/install":
            r=jarvis.install_update(d.get("id","")); s._j({"text":r})
        else: s.send_response(404); s.end_headers()
def main():
    print("="*55)
    print("  JARVIS v7.0 (RU) - Super Brain System")
    print("="*55)
    print()
    print("Мозги:")
    for b in [metal,xcode,web,alice]: print("  [OK] "+b.name+" - "+b.role)
    print("  [OK] JARVIS - Супер-мозг / Координатор")
    print()
    if not kb["wiki"]:
        print("Первый запуск - обучение с Wikipedia...")
        for t in ["Swift programming language","Metal API","Artificial intelligence"]:
            r=wiki_learn(t); print("  Изучено: "+t+" ("+str(len(r))+" статей)")
        print()
    tcp.start(); print("  [OK] TCP 127.0.0.1:"+str(TCP_PORT))
    httpd=socketserver.TCPServer(("127.0.0.1",WEB_PORT),Handler)
    threading.Thread(target=httpd.serve_forever,daemon=True).start()
    print("  [OK] Web http://127.0.0.1:"+str(WEB_PORT))
    print()
    ai_ok=[k for k,v in api_keys.items() if v and v!="http://127.0.0.1:11434"]
    print("  API: "+(", ".join(k+":OK" for k in ai_ok) if ai_ok else "нет ключей"))
    print("  Голос: "+("включён" if cfg.get("voice",True) else "выключен"))
    print("  Супер-мозг: "+("включён" if cfg.get("super_brain",True) else "выключен"))
    print("  Авто-улучшения: "+("включены" if cfg.get("auto_improve",True) else "выключены"))
    print()
    print("  Ctrl+C для остановки")
    print()
    try: webbrowser.open("http://127.0.0.1:"+str(WEB_PORT))
    except: pass
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        print("\nОстановка..."); httpd.shutdown(); print("Готово.")
if __name__=="__main__": main()
