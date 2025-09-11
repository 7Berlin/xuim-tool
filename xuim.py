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


# ---------------- User Fetch ----------------
def get_users_by_status(status, name=None):
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, settings FROM inbounds")
        rows = cursor.fetchall()
    except Exception as e:
        print(f"{RED}DB query failed: {e}{RESET}")
        conn.close()
        return []

    users = []
    for row in rows:
        inbound_id, settings_json = row
        try:
            settings = json.loads(settings_json)
        except:
            continue
        clients = settings.get("clients") or []
        if not isinstance(clients, list):
            continue
        for c in clients:
            email = c.get("email") or c.get("id") or "<no-email>"
            port = c.get("port", 0)
            expiry = c.get("expiryTime", 0) or 0
            enable = c.get("enable", True)
            created_at = int(c.get("created_at", now * 1000) / 1000)
            days_since_creation = (now - created_at) // (24 * 3600)

            if name and name.lower() not in email.lower():
                continue

            if status == "expired" and 0 < expiry < now:
                days_expired = (now - expiry) // (24 * 3600)
                users.append(
                    {"email": email, "port": port, "days_expired": days_expired}
                )
            elif status == "not_started" and expiry == -2851200000:
                # started but first usage not yet counted
                users.append(
                    {
                        "email": email,
                        "port": port,
                        "days_since_creation": days_since_creation,
                    }
                )
            elif status == "unlimited" and expiry == 0:
                users.append({"email": email, "port": port})
            elif status == "inactive" and not enable:
                users.append({"email": email, "port": port})
    conn.close()
    return users


# ---------------- Display ----------------
def show_users(users, status):
    if not users:
        print(f"{RED}No {status.replace('_', ' ')} users found.{RESET}")
        return
    table = []
    if status == "expired":
        for u in users:
            table.append([u["email"], u["port"], u["days_expired"]])
        headers = ["Email", "Port", "Days Expired"]
    elif status == "not_started":
        for u in users:
            table.append([u["email"], u["port"], u["days_since_creation"]])
        headers = ["Email", "Port", "Days Since Creation"]
    else:
        for u in users:
            table.append([u["email"], u["port"]])
        headers = ["Email", "Port"]

    print(tabulate(table, headers=headers, tablefmt="grid"))


# ---------------- Delete / Enable ----------------
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
                c
                for c in clients
                if (c.get("email") or c.get("id") or "") not in email_list
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
                if (c.get("email") or c.get("id") or "") in email_list and not c.get(
                    "enable", True
                ):
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
def expired_users_menu():
    while True:
        options = [
            "Show All Expired Users",
            "Show Expired Users by Name",
            "Delete Expired Users by Name",
        ]
        idx = menu_select(options, "Expired Users Management")
        if idx == 0:
            break
        elif idx == 1:
            users = get_users_by_status("expired")
            show_users(users, "expired")
        elif idx == 2:
            name = input("Enter name filter: ").strip()
            users = get_users_by_status("expired", name=name)
            show_users(users, "expired")
        elif idx == 3:
            name = input("Enter name filter for deletion: ").strip()
            users = get_users_by_status("expired", name=name)
            emails = [u["email"] for u in users]
            delete_users_by_email(emails)


def not_started_menu():
    while True:
        options = [
            "Show Not-started Users",
            "Delete Not-started Users by Name",
            "Delete All Not-started Users",
        ]
        idx = menu_select(options, "Not-started Users Management")
        if idx == 0:
            break
        elif idx == 1:
            users = get_users_by_status("not_started")
            show_users(users, "not_started")
        elif idx == 2:
            name = input("Enter name filter: ").strip()
            users = get_users_by_status("not_started", name=name)
            emails = [u["email"] for u in users]
            delete_users_by_email(emails)
        elif idx == 3:
            users = get_users_by_status("not_started")
            emails = [u["email"] for u in users]
            delete_users_by_email(emails)


def unlimited_menu():
    while True:
        options = ["Show Unlimited Users"]
        idx = menu_select(options, "Unlimited Users Management")
        if idx == 0:
            break
        elif idx == 1:
            users = get_users_by_status("unlimited")
            show_users(users, "unlimited")


def inactive_users_menu():
    while True:
        options = [
            "Show All Inactive Users",
            "Show Inactive Users by Name",
            "Delete All Inactive Users",
            "Delete Inactive Users by Name",
            "Enable All Inactive Users",
            "Enable Inactive Users by Name",
        ]
        idx = menu_select(options, "Inactive Users Management")
        if idx == 0:
            break
        elif idx == 1:
            users = get_users_by_status("inactive")
            show_users(users, "inactive")
        elif idx == 2:
            name = input("Enter name filter: ").strip()
            users = get_users_by_status("inactive", name=name)
            show_users(users, "inactive")
        elif idx == 3:
            users = get_users_by_status("inactive")
            emails = [u["email"] for u in users]
            delete_users_by_email(emails)
        elif idx == 4:
            name = input("Enter name filter for deletion: ").strip()
            users = get_users_by_status("inactive", name=name)
            emails = [u["email"] for u in users]
            delete_users_by_email(emails)
        elif idx == 5:
            users = get_users_by_status("inactive")
            emails = [u["email"] for u in users]
            enable_users_by_email(emails)
        elif idx == 6:
            name = input("Enter name filter for enabling: ").strip()
            users = get_users_by_status("inactive", name=name)
            emails = [u["email"] for u in users]
            enable_users_by_email(emails)


# ---------------- Uninstall ----------------
def uninstall_tool():
    print(f"\n{RED}Uninstall X-UI Management Tool{RESET}\n")
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
            "Unlimited Users Management",
            "Update Client Traffic",
            "Inactive Users Management",
            "",
            "Uninstall X-UI Management Tool",
        ]
        idx = menu_select(options, "X-UI Management Tool", is_main=True)
        if idx == 0:
            print(f"{RED}Bye.{RESET}")
            sys.exit(0)
        elif idx == 1:
            expired_users_menu()
        elif idx == 2:
            not_started_menu()
        elif idx == 3:
            unlimited_menu()
        elif idx == 4:
            update_client_traffic()
        elif idx == 5:
            inactive_users_menu()
        elif idx == 7:
            uninstall_tool()


# ---------------- Run ----------------
if __name__ == "__main__":
    main_menu()
