#!/usr/bin/env python3
import sqlite3
import json
import time
import os
import sys
from tabulate import tabulate

DB_PATH = "/etc/x-ui/x-ui.db"
now = int(time.time())


def connect_db():
    try:
        return sqlite3.connect(DB_PATH)
    except Exception as e:
        print(f"Cannot open database '{DB_PATH}': {e}")
        sys.exit(1)


def list_inbounds():
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, remark FROM inbounds")
        rows = cursor.fetchall()
    except Exception as e:
        print(f"DB query failed: {e}")
        rows = []
    conn.close()
    return rows


def select_inbound():
    inbounds = list_inbounds()
    if not inbounds:
        print("No inbounds found.")
        return None

    print("\nInbounds:")
    for idx, (iid, remark) in enumerate(inbounds, start=1):
        label = remark if remark else "(no remark)"
        print(f"{idx} - {label} (ID: {iid})")
    print("0 - All Inbounds")

    choice = input("Select inbound (number): ").strip()
    if choice == "0" or choice == "":
        return None
    try:
        choice = int(choice)
        if 1 <= choice <= len(inbounds):
            return inbounds[choice - 1][0]
    except Exception:
        pass
    print("Invalid choice — defaulting to All Inbounds.")
    return None


def get_expired_users(days=0, name=None, inbound_id=None):
    conn = connect_db()
    cursor = conn.cursor()
    try:
        if inbound_id:
            cursor.execute(
                "SELECT id, remark, settings FROM inbounds WHERE id=?", (inbound_id,)
            )
        else:
            cursor.execute("SELECT id, remark, settings FROM inbounds")
        rows = cursor.fetchall()
    except Exception as e:
        print(f"DB query failed: {e}")
        conn.close()
        return []

    expired_users = []
    for row in rows:
        inbound_id_row, remark, settings_json = row
        try:
            settings = json.loads(settings_json)
        except Exception:
            continue

        clients = settings.get("clients") or []
        if not isinstance(clients, list):
            continue

        for c in clients:
            expiry_ms = c.get("expiryTime", 0) or 0
            expiry_sec = expiry_ms // 1000  # تبدیل میلی‌ثانیه به ثانیه
            if expiry_sec == 0:
                continue  # شروع نشده یا نامحدود، منقضی نشده
            if expiry_sec < now:
                days_expired = (now - expiry_sec) // (24 * 3600)
                if days > 0 and days_expired < days:
                    continue
                email = (
                    c.get("email")
                    or c.get("emailAddress")
                    or c.get("id")
                    or "<no-email>"
                )
                if name and name.lower() not in (email or "").lower():
                    continue
                expired_users.append(
                    {
                        "inbound_id": inbound_id_row,
                        "inbound_remark": remark or "",
                        "email": email,
                        "expiryTime": expiry_sec,
                        "days_expired": days_expired,
                    }
                )
    conn.close()
    return expired_users


def get_not_started_users(inbound_id=None):
    conn = connect_db()
    cursor = conn.cursor()
    try:
        if inbound_id:
            cursor.execute(
                "SELECT id, remark, settings FROM inbounds WHERE id=?", (inbound_id,)
            )
        else:
            cursor.execute("SELECT id, remark, settings FROM inbounds")
        rows = cursor.fetchall()
    except Exception as e:
        print(f"DB query failed: {e}")
        conn.close()
        return []

    not_started = []
    for row in rows:
        inbound_id_row, remark, settings_json = row
        try:
            settings = json.loads(settings_json)
        except Exception:
            continue
        clients = settings.get("clients") or []
        if not isinstance(clients, list):
            continue
        for c in clients:
            expiry_ms = c.get("expiryTime", 0) or 0
            expiry_sec = expiry_ms // 1000
            if expiry_sec != 0:
                continue  # فقط کسانی که expiryTime صفر دارند
            email = (
                c.get("email") or c.get("emailAddress") or c.get("id") or "<no-email>"
            )
            not_started.append(
                {
                    "inbound_id": inbound_id_row,
                    "inbound_remark": remark or "",
                    "email": email,
                    "expiryTime": expiry_sec,
                }
            )
    conn.close()
    return not_started


def delete_users(users):
    if not users:
        print("No users to delete.")
        return
    conn = connect_db()
    cursor = conn.cursor()
    removed = 0
    for u in users:
        try:
            cursor.execute(
                "SELECT settings FROM inbounds WHERE id=?", (u["inbound_id"],)
            )
            row = cursor.fetchone()
            if not row:
                continue
            settings_json = row[0]
            settings = json.loads(settings_json)
            clients = settings.get("clients") or []
            new_clients = [
                c for c in clients if (c.get("email") or c.get("id")) != u["email"]
            ]
            if len(new_clients) == len(clients):
                lowered = u["email"].lower() if isinstance(u["email"], str) else None
                filtered = []
                changed = False
                for c in clients:
                    candidate = c.get("email") or c.get("id") or ""
                    if lowered and candidate.lower() == lowered:
                        changed = True
                    else:
                        filtered.append(c)
                if changed:
                    new_clients = filtered
                else:
                    continue
            settings["clients"] = new_clients
            new_settings_json = json.dumps(settings, ensure_ascii=False)
            cursor.execute(
                "UPDATE inbounds SET settings=? WHERE id=?",
                (new_settings_json, u["inbound_id"]),
            )
            removed += 1
            print(f"Removed {u['email']} from inbound ID {u['inbound_id']}")
        except Exception as e:
            print(f"Failed to remove {u.get('email')}: {e}")
            continue
    conn.commit()
    conn.close()
    print(f"Deletion completed. Total removed attempts: {removed}")


def show_table(users, not_started=False):
    if not users:
        print("No users found for this query.")
        return
    table = []
    if not_started:
        for u in users:
            table.append([u["email"], u["inbound_remark"], "Not started"])
        print(tabulate(table, headers=["Email", "Inbound", "Status"], tablefmt="grid"))
    else:
        for u in users:
            exp_date = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(u["expiryTime"])
            )
            table.append([u["email"], u["inbound_remark"], exp_date, u["days_expired"]])
        print(
            tabulate(
                table,
                headers=["Email", "Inbound", "Expiry Time", "Days Expired"],
                tablefmt="grid",
            )
        )


if __name__ == "__main__":
    main_menu()
