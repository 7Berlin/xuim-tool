#!/usr/bin/env python3
import sqlite3
import json
import time
import os
import sys
from tabulate import tabulate

DB_PATH = "/etc/x-ui/x-ui.db"
now = int(time.time())  # ثانیه


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
            expiry_sec = expiry_ms // 1000
            if expiry_sec == 0:
                continue  # شروع نشده یا نامحدود
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


# منوها
def expired_users_menu():
    inbound_id = select_inbound()
    while True:
        print("\nExpired Users Management")
        print("1 - Show All Expired Users")
        print("2 - Show Expired Users Contain Specific Name")
        print("3 - Show Expired Users More Than Some Days (Default: 30)")
        print("4 - Delete All Expired Users")
        print("5 - Delete Expired Users Contain Specific Name")
        print("6 - Delete Expired Users More Than Some Days (Default: 30)")
        print("7 - Back to Main Menu")
        choice = input("Enter choice: ").strip()
        if choice == "1":
            users = get_expired_users(inbound_id=inbound_id)
            show_table(users)
        elif choice == "2":
            name = input("Enter name (substring): ").strip()
            users = get_expired_users(name=name, inbound_id=inbound_id)
            show_table(users)
        elif choice == "3":
            days = input("Days (default 30): ").strip()
            days = int(days) if days.isdigit() else 30
            users = get_expired_users(days=days, inbound_id=inbound_id)
            show_table(users)
        elif choice == "4":
            users = get_expired_users(inbound_id=inbound_id)
            show_table(users)
            if (
                users
                and input("Delete all expired users? (yes/no): ").strip().lower()
                == "yes"
            ):
                delete_users(users)
        elif choice == "5":
            name = input("Enter name (substring): ").strip()
            users = get_expired_users(name=name, inbound_id=inbound_id)
            show_table(users)
            if (
                users
                and input(f"Delete expired users containing '{name}'? (yes/no): ")
                .strip()
                .lower()
                == "yes"
            ):
                delete_users(users)
        elif choice == "6":
            days = input("Days (default 30): ").strip()
            days = int(days) if days.isdigit() else 30
            users = get_expired_users(days=days, inbound_id=inbound_id)
            show_table(users)
            if (
                users
                and input(f"Delete expired users older than {days} days? (yes/no): ")
                .strip()
                .lower()
                == "yes"
            ):
                delete_users(users)
        elif choice == "7":
            break
        else:
            print("Invalid choice!")


def not_started_menu():
    inbound_id = select_inbound()
    while True:
        print("\nNot-started Users (expiryTime == 0)")
        print("1 - Show Not-started Users")
        print("2 - Delete Not-started Users Contain Specific Name")
        print("3 - Delete All Not-started Users")
        print("0 - Back to Main Menu")
        choice = input("Enter choice: ").strip()
        if choice == "1":
            users = get_not_started_users(inbound_id=inbound_id)
            show_table(users, not_started=True)
        elif choice == "2":
            name = input("Enter name (substring): ").strip()
            users = [
                u
                for u in get_not_started_users(inbound_id=inbound_id)
                if name.lower() in (u["email"] or "").lower()
            ]
            show_table(users, not_started=True)
            if (
                users
                and input(f"Delete not-started users containing '{name}'? (yes/no): ")
                .strip()
                .lower()
                == "yes"
            ):
                delete_users(users)
        elif choice == "3":
            users = get_not_started_users(inbound_id=inbound_id)
            show_table(users, not_started=True)
            if (
                users
                and input("Delete ALL not-started users shown here? (yes/no): ")
                .strip()
                .lower()
                == "yes"
            ):
                delete_users(users)
        elif choice == "0":
            break
        else:
            print("Invalid choice!")


def uninstall_tool():
    print("Uninstalling X-UI Management Tool...")
    script_path = "/opt/xuim/uninstall.sh"
    if os.path.isfile(script_path):
        os.system(f"bash {script_path}")
    else:
        try:
            if os.path.isdir("/opt/xuim"):
                os.system("rm -rf /opt/xuim")
            if os.path.isfile("/usr/bin/xuim"):
                os.remove("/usr/bin/xuim")
            print("Uninstalled (best-effort).")
        except Exception as e:
            print(f"Uninstall failed: {e}")
    input("Press Enter to exit...")
    sys.exit(0)


def main_menu():
    while True:
        print("\nX-UI Management Tool")
        print("1 - Expired Users Management")
        print("2 - Not-started Users (expiryTime == 0)")
        print("9 - Uninstall X-UI Management Tool")
        print("0 - Exit")
        choice = input("Enter choice: ").strip()
        if choice == "1":
            expired_users_menu()
        elif choice == "2":
            not_started_menu()
        elif choice == "9":
            uninstall_tool()
        elif choice == "0":
            print("Bye.")
            sys.exit(0)
        else:
            print("Invalid choice!")


if __name__ == "__main__":
    main_menu()
