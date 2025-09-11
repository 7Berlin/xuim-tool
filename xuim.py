#!/usr/bin/env python3
import sqlite3
import json
import time
import os
import sys
from tabulate import tabulate

# ANSI color codes
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RESET = "\033[0m"

DB_PATH = "/etc/x-ui/x-ui.db"
now = int(time.time())


# ---------------- Database Connection ----------------
def connect_db():
    try:
        return sqlite3.connect(DB_PATH)
    except Exception as e:
        print(f"{RED}Cannot open database '{DB_PATH}': {e}{RESET}")
        sys.exit(1)


# ---------------- Menu Helper ----------------
def menu_select(options, title="Menu", is_main=False):
    while True:
        print(f"\n{CYAN}==== {title} ===={RESET}")
        for i, opt in enumerate(options, start=1):
            print(f"{YELLOW}{i}. {opt}{RESET}")
        print(f"{RED}0. {'Exit' if is_main else 'Back'}{RESET}")
        choice = input(f"Enter choice: ").strip()
        if choice == "0":
            return 0
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            return int(choice)
        print(f"{RED}Invalid choice!{RESET}")


# ---------------- Users Fetching ----------------
def fetch_clients():
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, remark, settings FROM inbounds")
        rows = cursor.fetchall()
    except Exception as e:
        print(f"{RED}DB query failed: {e}{RESET}")
        conn.close()
        return []
    result = []
    for inbound_id, remark, settings_json in rows:
        try:
            settings = json.loads(settings_json)
        except Exception:
            continue
        clients = settings.get("clients") or []
        for c in clients:
            result.append(
                {"inbound_id": inbound_id, "remark": remark or "", "client": c}
            )
    conn.close()
    return result


# ---------------- Categorize Users ----------------
def expired_users(name=None):
    users = []
    for row in fetch_clients():
        c = row["client"]
        expiry = c.get("expiryTime", 0) or 0
        email = c.get("email") or "<no-email>"
        if expiry <= 0 or expiry > now:
            continue
        if name and name.lower() not in email.lower():
            continue
        days_expired = (now - expiry) // (24 * 3600)
        users.append(
            {
                "email": email,
                "remark": row["remark"],
                "expiryTime": expiry,
                "days_expired": days_expired,
                "port": c.get("port", ""),
            }
        )
    return users


def not_started_users(name=None):
    users = []
    for row in fetch_clients():
        c = row["client"]
        expiry = c.get("expiryTime", 0) or 0
        if expiry != 0:
            continue
        email = c.get("email") or "<no-email>"
        if name and name.lower() not in email.lower():
            continue
        created_at = int(c.get("created_at", now) / 1000)
        days_since_creation = (now - created_at) // (24 * 3600)
        users.append(
            {
                "email": email,
                "remark": row["remark"],
                "days_since_creation": days_since_creation,
                "port": c.get("port", ""),
            }
        )
    return users


def unlimited_users(name=None):
    users = []
    for row in fetch_clients():
        c = row["client"]
        expiry = c.get("expiryTime", 0) or 0
        if expiry != 0:
            continue
        # skip not-started, only unlimited after first usage
        created_at = int(c.get("created_at", now) / 1000)
        days_since_creation = (now - created_at) // (24 * 3600)
        if days_since_creation < 0:
            continue
        email = c.get("email") or "<no-email>"
        if name and name.lower() not in email.lower():
            continue
        users.append(
            {"email": email, "remark": row["remark"], "port": c.get("port", "")}
        )
    return users


def inactive_users(name=None):
    users = []
    for row in fetch_clients():
        c = row["client"]
        if c.get("enable", True):
            continue
        email = c.get("email") or "<no-email>"
        if name and name.lower() not in email.lower():
            continue
        users.append(
            {
                "email": email,
                "remark": row["remark"],
                "port": c.get("port", ""),
                "inbound_id": row["inbound_id"],
                "client_obj": c,
            }
        )
    return users


# ---------------- Display Tables ----------------
def display_expired(users):
    if not users:
        print(f"{RED}No expired users found.{RESET}")
        return
    table = []
    for u in users:
        exp_date = time.strftime(
            "%Y-%m-%d %H:%M:%S", time.localtime(u["expiryTime"] / 1000)
        )
        table.append([u["email"], u["remark"], exp_date, u["days_expired"], u["port"]])
    print(
        tabulate(
            table,
            headers=["Email", "Inbound", "Expiry Time", "Days Expired", "Port"],
            tablefmt="grid",
        )
    )


def display_not_started(users):
    if not users:
        print(f"{RED}No not-started users found.{RESET}")
        return
    table = [
        [u["email"], u["remark"], u["days_since_creation"], u["port"]] for u in users
    ]
    print(
        tabulate(
            table,
            headers=["Email", "Inbound", "Days Since Creation", "Port"],
            tablefmt="grid",
        )
    )


def display_inactive(users):
    if not users:
        print(f"{RED}No inactive users found.{RESET}")
        return
    table = [[u["email"], u["remark"], u["port"]] for u in users]
    print(tabulate(table, headers=["Email", "Inbound", "Port"], tablefmt="grid"))


# ---------------- User Actions ----------------
def delete_users_by_email(email_list):
    if not email_list:
        print(f"{RED}No users to delete.{RESET}")
        return
    conn = connect_db()
    cursor = conn.cursor()
    removed_total = 0
    try:
        cursor.execute("SELECT id, settings FROM inbounds")
        rows = cursor.fetchall()
        for inbound_id, settings_json in rows:
            try:
                settings = json.loads(settings_json)
            except:
                continue
            clients = settings.get("clients") or []
            new_clients = [
                c for c in clients if (c.get("email") or "") not in email_list
            ]
            if len(new_clients) < len(clients):
                settings["clients"] = new_clients
                cursor.execute(
                    "UPDATE inbounds SET settings=? WHERE id=?",
                    (json.dumps(settings), inbound_id),
                )
                removed_total += len(clients) - len(new_clients)
        conn.commit()
        print(f"{GREEN}Removed {removed_total} users.{RESET}")
    except Exception as e:
        print(f"{RED}Deletion failed: {e}{RESET}")
    finally:
        conn.close()


def enable_users_by_email(email_list):
    if not email_list:
        print(f"{RED}No users to enable.{RESET}")
        return
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, settings FROM inbounds")
        rows = cursor.fetchall()
        for inbound_id, settings_json in rows:
            try:
                settings = json.loads(settings_json)
            except:
                continue
            clients = settings.get("clients") or []
            changed = False
            for c in clients:
                if (c.get("email") or "") in email_list and not c.get("enable", True):
                    c["enable"] = True
                    changed = True
            if changed:
                cursor.execute(
                    "UPDATE inbounds SET settings=? WHERE id=?",
                    (json.dumps(settings), inbound_id),
                )
        conn.commit()
        print(f"{GREEN}Enabled {len(email_list)} users.{RESET}")
    except Exception as e:
        print(f"{RED}Failed to enable: {e}{RESET}")
    finally:
        conn.close()


# ---------------- Update Traffic ----------------
def update_client_traffic():
    while True:
        email = input("Enter client email (or 0 to go back): ").strip()
        if email == "0":
            break
        if not email:
            print(f"{RED}Email cannot be empty.{RESET}")
            continue
        try:
            up_gb = float(input("Upload (GB): ").strip())
            down_gb = float(input("Download (GB): ").strip())
        except ValueError:
            print(f"{RED}Invalid number entered.{RESET}")
            continue
        up_bytes = int(up_gb * 1024**3)
        down_bytes = int(down_gb * 1024**3)
        conn = connect_db()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE client_traffics SET up=?, down=? WHERE email=?",
                (up_bytes, down_bytes, email),
            )
            conn.commit()
            if cursor.rowcount > 0:
                print(
                    f"{GREEN}Traffic updated for {email}: Upload={up_gb}GB, Download={down_gb}GB{RESET}"
                )
            else:
                print(f"{RED}No client found with email '{email}'{RESET}")
        finally:
            conn.close()


# ---------------- Menus ----------------
def expired_menu():
    while True:
        idx = menu_select(
            [
                "Show All Expired Users",
                "Show Expired Users by Name",
                "Delete Expired Users by Name",
            ],
            "Expired Users Management",
        )
        if idx == 0:
            break
        elif idx == 1:
            display_expired(expired_users())
        elif idx == 2:
            name = input("Enter name filter: ").strip()
            display_expired(expired_users(name=name))
        elif idx == 3:
            name = input("Enter name filter to delete: ").strip()
            users = expired_users(name=name)
            delete_users_by_email([u["email"] for u in users])


def not_started_menu():
    while True:
        idx = menu_select(
            [
                "Show Not-started Users",
                "Delete Not-started Users by Name",
                "Delete All Not-started Users",
            ],
            "Not-started Users Management",
        )
        if idx == 0:
            break
        elif idx == 1:
            display_not_started(not_started_users())
        elif idx == 2:
            name = input("Enter name filter for deletion: ").strip()
            users = not_started_users()
            delete_users_by_email(
                [u["email"] for u in users if name.lower() in u["email"].lower()]
            )
        elif idx == 3:
            users = not_started_users()
            delete_users_by_email([u["email"] for u in users])


def inactive_menu():
    while True:
        idx = menu_select(
            [
                "Show All Inactive Users",
                "Show Inactive Users by Name",
                "Delete All Inactive Users",
                "Delete Inactive Users by Name",
                "Enable All Inactive Users",
                "Enable Inactive Users by Name",
            ],
            "Inactive Users Management",
        )
        if idx == 0:
            break
        elif idx == 1:
            display_inactive(inactive_users())
        elif idx == 2:
            name = input("Enter name filter: ").strip()
            display_inactive(inactive_users(name=name))
        elif idx == 3:
            users = inactive_users()
            delete_users_by_email([u["email"] for u in users])
        elif idx == 4:
            name = input("Enter name filter to delete: ").strip()
            users = inactive_users(name=name)
            delete_users_by_email([u["email"] for u in users])
        elif idx == 5:
            users = inactive_users()
            enable_users_by_email([u["email"] for u in users])
        elif idx == 6:
            name = input("Enter name filter to enable: ").strip()
            users = inactive_users(name=name)
            enable_users_by_email([u["email"] for u in users])


def uninstall_tool():
    print(f"\n{RED}--- Uninstall X-UI Management Tool ---{RESET}")
    script_path = "/opt/xuim/uninstall.sh"
    if os.path.isfile(script_path):
        os.system(f"bash {script_path}")
    else:
        try:
            if os.path.isdir("/opt/xuim"):
                os.system("rm -rf /opt/xuim")
            if os.path.isfile("/usr/bin/xuim"):
                os.remove("/usr/bin/xuim")
            print(f"{GREEN}Uninstalled (best-effort).{RESET}")
        except Exception as e:
            print(f"{RED}Uninstall failed: {e}{RESET}")
    input("Press Enter to exit...")
    sys.exit(0)


# ---------------- Main Menu ----------------
def main_menu():
    while True:
        options = [
            "Expired Users Management",
            "Not-started Users Management",
            "Update Client Traffic",
            "Inactive Users Management",
            f"{RED}Uninstall X-UI Management Tool{RESET}",
        ]
        idx = menu_select(options, "X-UI Management Tool", is_main=True)
        if idx == 0:
            print(f"{RED}Bye.{RESET}")
            sys.exit(0)
        elif idx == 1:
            expired_menu()
        elif idx == 2:
            not_started_menu()
        elif idx == 3:
            update_client_traffic()
        elif idx == 4:
            inactive_menu()
        elif idx == 5:
            uninstall_tool()


# ---------------- Run ----------------
if __name__ == "__main__":
    main_menu()
