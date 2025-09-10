#!/usr/bin/env python3
import sqlite3
import json
import time
import os
import sys
from tabulate import tabulate

DB_PATH = "/etc/x-ui/x-ui.db"
now = int(time.time())


# ------------------------- Database ------------------------- #
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
        cursor.execute("SELECT id, remark, port FROM inbounds")
        rows = cursor.fetchall()
    except Exception as e:
        print(f"DB query failed: {e}")
        rows = []
    conn.close()
    return rows


# ------------------------- Menu ------------------------- #
def menu_select(options, title="Menu", is_main=False):
    """Select menu option by number. 0 is Exit (main) or Back (sub-menu)."""
    print("\033[1;36m" + title + "\033[0m\n")  # Cyan title
    for idx, option in enumerate(options, start=1):
        print(f"\033[1;33m{idx}.\033[0m {option}")  # Yellow numbers
    if is_main:
        print(f"\033[1;31m0.\033[0m Exit")  # Red 0 for main menu
    else:
        print(f"\033[1;31m0.\033[0m Back")  # Red 0 for sub-menu
    choice = input("\nEnter number: ").strip()
    if choice.isdigit():
        idx = int(choice)
        if idx == 0:
            return 0
        elif 1 <= idx <= len(options):
            return idx
    print("Invalid choice, try again.")
    return menu_select(options, title, is_main)


# ------------------------- Inbound Selection ------------------------- #
def select_inbound():
    inbounds = list_inbounds()
    if not inbounds:
        print("No inbounds found.")
        return None
    options = []
    for iid, remark, port in inbounds:
        label = remark if remark else "(no remark)"
        options.append(f"{label} (Port: {port}, ID: {iid})")
    options.append("All Inbounds")
    idx = menu_select(options, "Select Inbound", is_main=False)
    if idx == 0 or idx == len(options):
        return None
    return inbounds[idx - 1][0]


# ------------------------- Users Handling ------------------------- #
def get_expired_users(days=0, name=None, inbound_id=None):
    conn = connect_db()
    cursor = conn.cursor()
    try:
        if inbound_id:
            cursor.execute(
                "SELECT id, remark, settings, port FROM inbounds WHERE id=?",
                (inbound_id,),
            )
        else:
            cursor.execute("SELECT id, remark, settings, port FROM inbounds")
        rows = cursor.fetchall()
    except Exception as e:
        print(f"DB query failed: {e}")
        conn.close()
        return []

    expired_users = []
    for row in rows:
        inbound_id_row, remark, settings_json, port = row
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
            if expiry_sec <= 0:
                continue  # Not-started or Unlimited ignored
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
                expired_users.append(
                    {
                        "inbound_id": inbound_id_row,
                        "port": port,
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
                "SELECT id, remark, settings, port FROM inbounds WHERE id=?",
                (inbound_id,),
            )
        else:
            cursor.execute("SELECT id, remark, settings, port FROM inbounds")
        rows = cursor.fetchall()
    except Exception as e:
        print(f"DB query failed: {e}")
        conn.close()
        return []

    not_started = []
    for row in rows:
        inbound_id_row, remark, settings_json, port = row
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
            if expiry_sec >= 0:
                continue  # فقط Not-started (<0) هستند
            email = (
                c.get("email") or c.get("emailAddress") or c.get("id") or "<no-email>"
            )
            not_started.append(
                {
                    "inbound_id": inbound_id_row,
                    "port": port,
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
            settings = json.loads(row[0])
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
            cursor.execute(
                "UPDATE inbounds SET settings=? WHERE id=?",
                (json.dumps(settings, ensure_ascii=False), u["inbound_id"]),
            )
            removed += 1
            print(f"Removed {u['email']}")
        except Exception as e:
            print(f"Failed to remove {u.get('email')}: {e}")
            continue
    conn.commit()
    conn.close()
    print(f"Deletion completed. Total removed attempts: {removed}")


# ------------------------- Display Tables ------------------------- #
def show_table(users, not_started=False):
    if not users:
        print("No users found for this query.")
        return
    table = []
    if not_started:
        for u in users:
            table.append([u["email"], u.get("port", "N/A"), "Not started"])
        print(tabulate(table, headers=["Email", "Port", "Status"], tablefmt="grid"))
    else:
        for u in users:
            exp_date = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(u["expiryTime"])
            )
            table.append(
                [u["email"], u.get("port", "N/A"), exp_date, u["days_expired"]]
            )
        print(
            tabulate(
                table,
                headers=["Email", "Port", "Expiry Time", "Days Expired"],
                tablefmt="grid",
            )
        )


# ------------------------- Menus ------------------------- #
def expired_users_menu():
    inbound_id = select_inbound()
    while True:
        options = [
            "Show All Expired Users",
            "Show Expired Users Contain Specific Name",
            "Show Expired Users More Than Some Days (Default:30)",
            "Delete All Expired Users",
            "Delete Expired Users Contain Specific Name",
            "Delete Expired Users More Than Some Days (Default:30)",
        ]
        idx = menu_select(options, "Expired Users Management", is_main=False)
        if idx == 0:
            break
        elif idx == 1:
            users = get_expired_users(inbound_id=inbound_id)
            show_table(users)
        elif idx == 2:
            name = input("Enter name substring: ").strip()
            users = get_expired_users(name=name, inbound_id=inbound_id)
            show_table(users)
        elif idx == 3:
            days = input("Days (default 30): ").strip()
            days = int(days) if days.isdigit() else 30
            users = get_expired_users(days=days, inbound_id=inbound_id)
            show_table(users)
        elif idx == 4:
            users = get_expired_users(inbound_id=inbound_id)
            show_table(users)
            if (
                users
                and input("Delete all expired users? (yes/no): ").strip().lower()
                == "yes"
            ):
                delete_users(users)
        elif idx == 5:
            name = input("Enter name substring: ").strip()
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
        elif idx == 6:
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


def not_started_menu():
    inbound_id = select_inbound()
    while True:
        options = [
            "Show Not-started Users",
            "Delete Not-started Users Contain Specific Name",
            "Delete All Not-started Users",
        ]
        idx = menu_select(options, "Not-started Users Management", is_main=False)
        if idx == 0:
            break
        elif idx == 1:
            users = get_not_started_users(inbound_id=inbound_id)
            show_table(users, not_started=True)
        elif idx == 2:
            name = input("Enter name substring: ").strip()
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
        elif idx == 3:
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
        options = [
            "Expired Users Management",
            "Not-started Users (expiryTime < 0)",
            "Uninstall X-UI Management Tool",
        ]
        idx = menu_select(options, "X-UI Management Tool", is_main=True)
        if idx == 0:
            print("Bye.")
            sys.exit(0)
        elif idx == 1:
            expired_users_menu()
        elif idx == 2:
            not_started_menu()
        elif idx == 3:
            uninstall_tool()


if __name__ == "__main__":
    main_menu()
