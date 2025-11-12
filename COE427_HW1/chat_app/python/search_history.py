
#!/usr/bin/env python3
import argparse
from persistence import MessageStore

def main():
    p = argparse.ArgumentParser(description="Search chat history (no RTI).")
    p.add_argument("--group", "-g", required=True, help="Group/room name")
    p.add_argument("--query", "-q", required=True, help="Substring to search for")
    p.add_argument("--limit", "-n", type=int, default=100, help="Max hits (default 100)")
    p.add_argument("--db", default="chat.db", help="SQLite DB path (default chat.db)")
    args = p.parse_args()

    store = MessageStore(args.db)
    rows = store.search(args.group, args.query, args.limit)
    for ts, direction, from_user, first_name, last_name, text in rows:
        print(f"[{direction}] {from_user}: {text}")

if __name__ == "__main__":
    main()
