"""
Terminal Diary App
Single-file Python application with two storage backends: SQLite and JSON.
Features:
 - Add new diary entry (date, title, body, mood, tags)
 - Read entries by date
 - Search entries by keyword (title/body/tags)
 - List all entries (dates or titles)
 - Export entry or all entries (.txt or .md)
 - Mood tracker (store mood with entry)
 - Tag entries with categories
 - Edit or delete entries
 - Storage: sqlite (default) or JSON file

Usage:
  python terminal_diary_app.py           # interactive menu (SQLite by default)
  python terminal_diary_app.py --storage json --file mydiary.json
  python terminal_diary_app.py --storage sqlite --db diary.db

The app is designed to be run in a terminal. It's single-file and depends only on Python standard library.
"""

import argparse
import sqlite3
import json
import os
import sys
from datetime import datetime
from uuid import uuid4
from typing import List, Optional, Dict, Any

DATE_FMT = "%Y-%m-%d"


# ------------------------- Storage Backends -------------------------
class StorageInterface:
    def add_entry(self, entry: Dict[str, Any]) -> str:
        raise NotImplementedError

    def get_entry(self, entry_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def get_entries_by_date(self, date_str: str) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def search_entries(self, keyword: str) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def list_entries(self) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def update_entry(self, entry_id: str, updated: Dict[str, Any]) -> bool:
        raise NotImplementedError

    def delete_entry(self, entry_id: str) -> bool:
        raise NotImplementedError

    def export_all(self) -> List[Dict[str, Any]]:
        raise NotImplementedError


class SQLiteStorage(StorageInterface):
    def __init__(self, db_path: str = "diary.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self):
        c = self.conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS entries (
                id TEXT PRIMARY KEY,
                date TEXT,
                title TEXT,
                body TEXT,
                mood TEXT,
                tags TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        self.conn.commit()

    def add_entry(self, entry: Dict[str, Any]) -> str:
        entry_id = entry.get("id", str(uuid4()))
        now = datetime.utcnow().isoformat()
        c = self.conn.cursor()
        c.execute(
            "INSERT INTO entries (id, date, title, body, mood, tags, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
            (
                entry_id,
                entry["date"],
                entry.get("title", ""),
                entry.get("body", ""),
                entry.get("mood", ""),
                ",".join(entry.get("tags", [])),
                now,
                now,
            ),
        )
        self.conn.commit()
        return entry_id

    def _row_to_entry(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "id": row["id"],
            "date": row["date"],
            "title": row["title"],
            "body": row["body"],
            "mood": row["mood"],
            "tags": row["tags"].split(",") if row["tags"] else [],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def get_entry(self, entry_id: str) -> Optional[Dict[str, Any]]:
        c = self.conn.cursor()
        c.execute("SELECT * FROM entries WHERE id = ?", (entry_id,))
        row = c.fetchone()
        return self._row_to_entry(row) if row else None

    def get_entries_by_date(self, date_str: str) -> List[Dict[str, Any]]:
        c = self.conn.cursor()
        c.execute("SELECT * FROM entries WHERE date = ? ORDER BY created_at DESC", (date_str,))
        rows = c.fetchall()
        return [self._row_to_entry(r) for r in rows]

    def search_entries(self, keyword: str) -> List[Dict[str, Any]]:
        like = f"%{keyword}%"
        c = self.conn.cursor()
        c.execute(
            "SELECT * FROM entries WHERE title LIKE ? OR body LIKE ? OR tags LIKE ? ORDER BY date DESC",
            (like, like, like),
        )
        rows = c.fetchall()
        return [self._row_to_entry(r) for r in rows]

    def list_entries(self) -> List[Dict[str, Any]]:
        c = self.conn.cursor()
        c.execute("SELECT * FROM entries ORDER BY date DESC, created_at DESC")
        rows = c.fetchall()
        return [self._row_to_entry(r) for r in rows]

    def update_entry(self, entry_id: str, updated: Dict[str, Any]) -> bool:
        now = datetime.utcnow().isoformat()
        c = self.conn.cursor()
        c.execute(
            "UPDATE entries SET date=?, title=?, body=?, mood=?, tags=?, updated_at=? WHERE id=?",
            (
                updated["date"],
                updated.get("title", ""),
                updated.get("body", ""),
                updated.get("mood", ""),
                ",".join(updated.get("tags", [])),
                now,
                entry_id,
            ),
        )
        self.conn.commit()
        return c.rowcount > 0

    def delete_entry(self, entry_id: str) -> bool:
        c = self.conn.cursor()
        c.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
        self.conn.commit()
        return c.rowcount > 0

    def export_all(self) -> List[Dict[str, Any]]:
        return self.list_entries()


class JSONStorage(StorageInterface):
    def __init__(self, file_path: str = "diary.json"):
        self.file_path = file_path
        if not os.path.exists(self.file_path):
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump({"entries": []}, f, indent=2)

    def _read(self) -> Dict[str, Any]:
        with open(self.file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write(self, data: Dict[str, Any]):
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def add_entry(self, entry: Dict[str, Any]) -> str:
        data = self._read()
        entry_id = entry.get("id", str(uuid4()))
        now = datetime.utcnow().isoformat()
        stored = {
            "id": entry_id,
            "date": entry["date"],
            "title": entry.get("title", ""),
            "body": entry.get("body", ""),
            "mood": entry.get("mood", ""),
            "tags": entry.get("tags", []),
            "created_at": now,
            "updated_at": now,
        }
        data.setdefault("entries", []).append(stored)
        self._write(data)
        return entry_id

    def get_entry(self, entry_id: str) -> Optional[Dict[str, Any]]:
        data = self._read()
        for e in data.get("entries", []):
            if e["id"] == entry_id:
                return e
        return None

    def get_entries_by_date(self, date_str: str) -> List[Dict[str, Any]]:
        data = self._read()
        return [e for e in data.get("entries", []) if e.get("date") == date_str]

    def search_entries(self, keyword: str) -> List[Dict[str, Any]]:
        keyword_lower = keyword.lower()
        data = self._read()
        res = []
        for e in data.get("entries", []):
            if (
                keyword_lower in (e.get("title", "") or "").lower()
                or keyword_lower in (e.get("body", "") or "").lower()
                or any(keyword_lower in t.lower() for t in e.get("tags", []))
            ):
                res.append(e)
        return sorted(res, key=lambda x: x.get("date", ""), reverse=True)

    def list_entries(self) -> List[Dict[str, Any]]:
        data = self._read()
        return sorted(data.get("entries", []), key=lambda x: (x.get("date", ""), x.get("created_at", "")), reverse=True)

    def update_entry(self, entry_id: str, updated: Dict[str, Any]) -> bool:
        data = self._read()
        for i, e in enumerate(data.get("entries", [])):
            if e["id"] == entry_id:
                e.update({
                    "date": updated["date"],
                    "title": updated.get("title", ""),
                    "body": updated.get("body", ""),
                    "mood": updated.get("mood", ""),
                    "tags": updated.get("tags", []),
                    "updated_at": datetime.utcnow().isoformat(),
                })
                data["entries"][i] = e
                self._write(data)
                return True
        return False

    def delete_entry(self, entry_id: str) -> bool:
        data = self._read()
        new_entries = [e for e in data.get("entries", []) if e["id"] != entry_id]
        if len(new_entries) == len(data.get("entries", [])):
            return False
        data["entries"] = new_entries
        self._write(data)
        return True

    def export_all(self) -> List[Dict[str, Any]]:
        return self.list_entries()


# ------------------------- Helper Functions -------------------------

def parse_date(input_str: str) -> str:
    try:
        d = datetime.strptime(input_str, DATE_FMT)
        return d.strftime(DATE_FMT)
    except ValueError:
        raise ValueError(f"Date should be in {DATE_FMT} format")


def prompt_multiline(prompt_msg: str = "Enter body. End with a single line containing only '.'") -> str:
    print(prompt_msg)
    lines = []
    while True:
        line = input()
        if line.strip() == ".":
            break
        lines.append(line)
    return "\n".join(lines)


def filename_safe(s: str) -> str:
    return "".join(c for c in s if c.isalnum() or c in (" ", "-", "_")).rstrip()


# ------------------------- Export Helpers -------------------------

def export_entry_to_file(entry: Dict[str, Any], path: str, fmt: str = "txt") -> str:
    ext = fmt.lower()
    if ext not in ("txt", "md"):
        raise ValueError("Unsupported export format")
    if not path.lower().endswith(f".{ext}"):
        path = f"{path}.{ext}"

    header = f"{entry.get('title','(No Title)')} - {entry.get('date')}\n"
    header += f"Mood: {entry.get('mood','')}\n"
    header += f"Tags: {', '.join(entry.get('tags', []))}\n"
    header += "\n"

    body = entry.get("body", "")
    content = header + body

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    return path


def export_all_to_folder(entries: List[Dict[str, Any]], folder: str, fmt: str = "md") -> List[str]:
    os.makedirs(folder, exist_ok=True)
    created_files = []
    for e in entries:
        safe_title = filename_safe(e.get("title") or e.get("id", "entry"))
        name = f"{e.get('date')}-{safe_title}" if safe_title else e.get("id")
        path = os.path.join(folder, name)
        created_files.append(export_entry_to_file(e, path, fmt=fmt))
    return created_files


# ------------------------- CLI / Interactive -------------------------
class DiaryApp:
    def __init__(self, storage: StorageInterface):
        self.storage = storage

    def add_new_entry(self):
        date_in = input(f"Date ({DATE_FMT}) [default today]: ").strip()
        if not date_in:
            date_str = datetime.utcnow().strftime(DATE_FMT)
        else:
            try:
                date_str = parse_date(date_in)
            except ValueError as e:
                print(e)
                return

        title = input("Title: ").strip()
        print("Write your entry. End with a single line containing only '.'")
        body = prompt_multiline()
        mood = input("Mood (optional): ").strip()
        tags_in = input("Tags (comma separated, optional): ").strip()
        tags = [t.strip() for t in tags_in.split(",") if t.strip()] if tags_in else []

        entry = {
            "date": date_str,
            "title": title,
            "body": body,
            "mood": mood,
            "tags": tags,
        }
        entry_id = self.storage.add_entry(entry)
        print(f"Saved entry {entry_id}")

    def read_by_date(self):
        date_in = input(f"Enter date ({DATE_FMT}): ")
        try:
            date_str = parse_date(date_in)
        except ValueError as e:
            print(e)
            return
        entries = self.storage.get_entries_by_date(date_str)
        if not entries:
            print("No entries for this date.")
            return
        for e in entries:
            self._print_entry(e)

    def search_entries(self):
        keyword = input("Keyword to search: ").strip()
        if not keyword:
            print("Empty keyword")
            return
        results = self.storage.search_entries(keyword)
        if not results:
            print("No results found")
            return
        for e in results:
            self._print_entry(e)

    def list_entries(self):
        entries = self.storage.list_entries()
        if not entries:
            print("No entries yet.")
            return
        print("ID\tDate\tTitle\tTags\tMood")
        for e in entries:
            print(f"{e['id']}\t{e['date']}\t{(e.get('title') or '')[:30]}\t{','.join(e.get('tags',[]))}\t{e.get('mood','')}")

    def export(self):
        choice = input("Export single entry or all? (single/all): ").strip().lower()
        fmt = input("Format (txt/md) [md]: ").strip().lower() or "md"
        if fmt not in ("txt", "md"):
            print("Unsupported format")
            return
        if choice == "single":
            entry_id = input("Enter entry ID: ").strip()
            e = self.storage.get_entry(entry_id)
            if not e:
                print("Entry not found")
                return
            path = input("Export path (filename, without ext) [default: ./<date>-<title>]: ").strip()
            if not path:
                safe_title = filename_safe(e.get("title") or e.get("id"))
                path = f"{e.get('date')}-{safe_title}"
            out = export_entry_to_file(e, path, fmt=fmt)
            print(f"Exported to {out}")
        elif choice == "all":
            folder = input("Target folder [./exports]: ").strip() or "./exports"
            created = export_all_to_folder(self.storage.export_all(), folder, fmt=fmt)
            print(f"Exported {len(created)} entries to {folder}")
        else:
            print("Unknown option")

    def edit_entry(self):
        entry_id = input("Enter entry ID to edit: ").strip()
        e = self.storage.get_entry(entry_id)
        if not e:
            print("Entry not found")
            return
        print("Leave blank to keep existing value")
        date_in = input(f"Date ({DATE_FMT}) [{e['date']}]: ").strip()
        if date_in:
            try:
                date_str = parse_date(date_in)
            except ValueError as ex:
                print(ex)
                return
        else:
            date_str = e["date"]
        title = input(f"Title [{e.get('title','')}]: ").strip() or e.get("title", "")
        print("Enter body. End with a single line containing only '.' (leave blank to keep current)")
        body = prompt_multiline()
        if not body:
            body = e.get("body", "")
        mood = input(f"Mood [{e.get('mood','')}]: ").strip() or e.get("mood", "")
        tags_in = input(f"Tags comma-separated [{','.join(e.get('tags', []))}]: ").strip()
        tags = [t.strip() for t in tags_in.split(",") if t.strip()] if tags_in else e.get("tags", [])

        updated = {"date": date_str, "title": title, "body": body, "mood": mood, "tags": tags}
        ok = self.storage.update_entry(entry_id, updated)
        print("Updated" if ok else "Failed to update")

    def delete_entry(self):
        entry_id = input("Enter entry ID to delete: ").strip()
        confirm = input("Are you sure? Type 'yes' to confirm: ")
        if confirm.lower() != "yes":
            print("Canceled")
            return
        ok = self.storage.delete_entry(entry_id)
        print("Deleted" if ok else "Not found")

    def mood_stats(self):
        entries = self.storage.list_entries()
        mood_count = {}
        for e in entries:
            m = (e.get("mood") or "(none)").strip()
            mood_count[m] = mood_count.get(m, 0) + 1
        if not mood_count:
            print("No mood data yet")
            return
        print("Mood counts:")
        for m, c in sorted(mood_count.items(), key=lambda x: (-x[1], x[0])):
            print(f"{m}: {c}")

    def _print_entry(self, e: Dict[str, Any]):
        print("-" * 40)
        print(f"ID: {e.get('id')}")
        print(f"Date: {e.get('date')}")
        print(f"Title: {e.get('title')}")
        print(f"Mood: {e.get('mood')}")
        print(f"Tags: {', '.join(e.get('tags', []))}")
        print("-")
        print(e.get("body", ""))
        print("-" * 40)

    def run(self):
        actions = {
            "1": ("Add new entry", self.add_new_entry),
            "2": ("Read entries by date", self.read_by_date),
            "3": ("Search entries by keyword", self.search_entries),
            "4": ("List all entries", self.list_entries),
            "5": ("Export (single/all)", self.export),
            "6": ("Edit an entry", self.edit_entry),
            "7": ("Delete an entry", self.delete_entry),
            "8": ("Mood tracker / stats", self.mood_stats),
            "9": ("Quit", None),
        }

        while True:
            print("\n=== Terminal Diary ===")
            for k, (label, _) in actions.items():
                print(f"{k}. {label}")
            choice = input("Choose an option: ").strip()
            if choice == "9":
                print("Goodbye!")
                break
            action = actions.get(choice)
            if not action:
                print("Invalid choice")
                continue
            try:
                action[1]()
            except Exception as e:
                print(f"Error: {e}")


# ------------------------- Entrypoint -------------------------

def build_storage(args) -> StorageInterface:
    if args.storage == "sqlite":
        return SQLiteStorage(args.db or "diary.db")
    else:
        return JSONStorage(args.file or "diary.json")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Terminal Diary App")
    parser.add_argument("--storage", choices=("sqlite", "json"), default="sqlite", help="Storage backend to use")
    parser.add_argument("--db", help="SQLite DB path (when storage=sqlite)")
    parser.add_argument("--file", help="JSON file path (when storage=json)")
    args = parser.parse_args(argv)

    storage = build_storage(args)
    app = DiaryApp(storage)
    try:
        app.run()
    except KeyboardInterrupt:
        print("\nExiting...")


if __name__ == "__main__":
    main()
