import os
import shutil
import json
from pathlib import Path
from datetime import datetime

SRC_DIR = Path("/Users/markluck/2123888")
ARCHIVE_DIR = SRC_DIR.parent / "jarvis-archive"
LOG_FILE = ARCHIVE_DIR / "scan_log.txt"
INDEX_FILE = ARCHIVE_DIR / "files_index.json"

# Типы файлов по категориям
CATEGORIES = {
    "Sources": [".swift", ".m", ".h", ".cpp", ".c"],
    "Scripts": [".py", ".sh", ".bat", ".ps1"],
    "DB": [".sql", ".db", ".sqlite", ".dump"],
    "Docs": [".md", ".txt", ".rst", ".html", ".css", ".js"],
}

def get_category(suffix: str) -> str:
    suffix = suffix.lower()
    for cat, exts in CATEGORIES.items():
        if suffix in exts:
            return cat
    return "Other"

def scan_directory(root: Path):
    files_info = []
    total_size = 0

    print(f"🔍 Сканирование: {root}")
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        size = path.stat().st_size
        mtime = datetime.fromtimestamp(path.stat().st_mtime).isoformat()
        info = {
            "path": str(path),
            "name": path.name,
            "suffix": path.suffix,
            "size_bytes": size,
            "mtime": mtime,
        }
        files_info.append(info)
        total_size += size

    return files_info, total_size

def write_log(files_info, total_size):
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write(f"SCAN LOG — {datetime.now().isoformat()}\n")
        f.write(f"Source: {SRC_DIR}\n")
        f.write(f"Archive: {ARCHIVE_DIR}\n")
        f.write(f"Total files: {len(files_info)}\n")
        f.write(f"Total size: {total_size} bytes ({total_size/1024/1024:.2f} MB)\n\n")

        f.write("--- FILES LIST ---\n")
        for i, fi in enumerate(files_info, 1):
            f.write(f"{i}. {fi['path']} | {fi['size_bytes']} B | {fi['mtime']}\n")

    print(f"✅ Лог записан: {LOG_FILE}")

def copy_to_archive(files_info):
    # Создаём структуру архива
    for cat in CATEGORIES.keys():
        (ARCHIVE_DIR / cat).mkdir(parents=True, exist_ok=True)
    (ARCHIVE_DIR / "Other").mkdir(exist_ok=True)

    copied = 0
    skipped = 0

    for fi in files_info:
        src = Path(fi["path"])
        cat = get_category(fi["suffix"])
        dst_dir = ARCHIVE_DIR / cat
        dst = dst_dir / fi["name"]

        # Если имя уже занято — добавляем суффикс _1, _2 и т.д.
        counter = 1
        while dst.exists():
            dst = dst_dir / f"{fi['name'].rsplit('.', 1)[0]}_{counter}{fi['suffix']}"
            counter += 1

        try:
            shutil.copy2(src, dst)  # copy2 сохраняет метаданные
            copied += 1
        except Exception as e:
            print(f"⚠️ Не удалось скопировать {src}: {e}")
            skipped += 1

    print(f"✅ Скопировано: {copied}, пропущено: {skipped}")

def save_index(files_info):
    data = {
        "scan_date": datetime.now().isoformat(),
        "source_dir": str(SRC_DIR),
        "total_files": len(files_info),
        "files": files_info
    }
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✅ Индекс сохранён: {INDEX_FILE}")

def main():
    if not SRC_DIR.exists():
        print(f"❌ Исходная папка не найдена: {SRC_DIR}")
        return

    ARCHIVE_DIR.mkdir(exist_ok=True)

    files_info, total_size = scan_directory(SRC_DIR)
    write_log(files_info, total_size)
    copy_to_archive(files_info)
    save_index(files_info)

    print("\n🎉 Готово! Теперь у тебя есть:")
    print(f"  - Лог: {LOG_FILE}")
    print(f"  - Индекс (JSON): {INDEX_FILE}")
    print(f"  - Архив с файлами в: {ARCHIVE_DIR}")
    print("  - Структура: Sources / Scripts / DB / Docs / Other")

if __name__ == "__main__":
    main()

