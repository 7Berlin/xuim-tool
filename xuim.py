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


# ---------------- Expired Users ----------------
def get_expired_users(name=None):
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, remark, settings FROM inbounds")
        rows = cursor.fetchall()
    except Exception as e:
        print(f"{RED}DB query failed: {e}{RESET}")
        conn.close()
        return []

    expired_users = []
    for row in rows:
        inbound_id, remark, settings_json = row
        try:
            settings = json.loads(settings_json)
        except Exception:
            continue
        clients = settings.get("clients") or []
        if not isinstance(clients, list):
            continue
        for c in clients:
            expiry = int(c.get("expiryTime", 0) or 0)
            email = c.get("email") or c.get("id") or "<no-email>"

            # expired: expiry > 0 and expiry < now (here 'now' is seconds)
            if expiry > 0 and expiry < now:
                if name and name.lower() not in email.lower():
                    continue
                days_expired = (now - expiry) // (24 * 3600)
                expired_users.append(
                    {
                        "email": email,
                        "remark": remark or "",
                        "expiryTime": expiry,
                        "days_expired": days_expired,
                    }
                )
    conn.close()
    return expired_users


def show_expired_users(users):
    if not users:
        print(f"{RED}No expired users found.{RESET}")
        return
    table = []
    for u in users:
        # expiryTime might be in seconds or ms depending on your DB; try seconds formatting
        try:
            exp_date = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(u["expiryTime"])
            )
        except Exception:
            # fallback if stored in ms
            exp_date = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(u["expiryTime"] / 1000)
            )
        table.append([u["email"], u["remark"], exp_date, u["days_expired"]])
    print(
        tabulate(
            table,
            headers=["Email", "Inbound", "Expiry Time", "Days Expired"],
            tablefmt="grid",
        )
    )


# ---------------- Not Started Users ----------------
def get_not_started_users(name=None):
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, remark, settings FROM inbounds")
        rows = cursor.fetchall()
    except Exception as e:
        print(f"{RED}DB query failed: {e}{RESET}")
        conn.close()
        return []

    not_started = []
    for row in rows:
        inbound_id, remark, settings_json = row
        try:
            settings = json.loads(settings_json)
        except Exception:
            continue
        clients = settings.get("clients") or []
        if not isinstance(clients, list):
            continue
        for c in clients:
            expiry = int(c.get("expiryTime", 0) or 0)
            # شروع نشده: expiry < 0
            if expiry >= 0:
                continue
            email = c.get("email") or c.get("id") or "<no-email>"
            if name and name.lower() not in email.lower():
                continue
            created_at = c.get("created_at", None)
            # created_at is likely ms; fallback to now if missing
            try:
                created_at_ts = (
                    int(created_at) // 1000
                    if created_at and int(created_at) > 1e10
                    else int(created_at or now)
                )
            except Exception:
                created_at_ts = int(created_at or now)
            days_since_creation = (now - created_at_ts) // (24 * 3600)
            not_started.append(
                {
                    "email": email,
                    "remark": remark or "",
                    "days_since_creation": days_since_creation,
                }
            )
    conn.close()
    return not_started


def show_not_started_users(users):
    if not users:
        print(f"{RED}No not-started users found.{RESET}")
        return
    table = [[u["email"], u["remark"], u["days_since_creation"]] for u in users]
    print(
        tabulate(
            table, headers=["Email", "Inbound", "Days Since Creation"], tablefmt="grid"
        )
    )


# ---------------- Inactive Users ----------------
def get_inactive_users(name=None):
    conn = connect_db()
    cursor = conn.cursor()
    try:
        # include port
        cursor.execute("SELECT id, remark, settings, port FROM inbounds")
        rows = cursor.fetchall()
    except Exception as e:
        print(f"{RED}DB query failed: {e}{RESET}")
        conn.close()
        return []
    users = []
    for row in rows:
        inbound_id, remark, settings_json, port = row
        try:
            settings = json.loads(settings_json)
        except Exception:
            continue
        clients = settings.get("clients") or []
        for c in clients:
            if c.get("enable", True):
                continue
            email = c.get("email") or c.get("id") or "<no-email>"
            if name and name.lower() not in email.lower():
                continue
            users.append(
                {
                    "email": email,
                    "remark": remark or "",
                    "port": port,
                    "client_obj": c,
                    "inbound_id": inbound_id,
                }
            )
    conn.close()
    return users


def show_inactive_users(users):
    if not users:
        print(f"{RED}No inactive users found.{RESET}")
        return
    table = [[u["email"], u["remark"], u.get("port", "N/A")] for u in users]
    print(tabulate(table, headers=["Email", "Inbound", "Port"], tablefmt="grid"))


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
            except Exception:
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
            except Exception:
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
        except Exception as e:
            print(f"{RED}Failed to update traffic: {e}{RESET}")
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
            users = get_expired_users()
            show_expired_users(users)
        elif idx == 2:
            name = input("Enter name filter: ").strip()
            users = get_expired_users(name=name)
            show_expired_users(users)
        elif idx == 3:
            name = input("Enter name filter to delete: ").strip()
            users = get_expired_users(name=name)
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
            name = input("Enter name filter (leave empty for all): ").strip()
            users = get_not_started_users(name=name if name else None)
            show_not_started_users(users)
        elif idx == 2:
            name = input("Enter name filter for deletion: ").strip()
            users = get_not_started_users(name=name if name else None)
            emails = [u["email"] for u in users]
            delete_users_by_email(emails)
        elif idx == 3:
            users = get_not_started_users()
            emails = [u["email"] for u in users]
            delete_users_by_email(emails)


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
            users = get_inactive_users()
            show_inactive_users(users)
        elif idx == 2:
            name = input("Enter name filter: ").strip()
            users = get_inactive_users(name=name)
            show_inactive_users(users)
        elif idx == 3:
            users = get_inactive_users()
            emails = [u["email"] for u in users]
            delete_users_by_email(emails)
        elif idx == 4:
            name = input("Enter name filter for deletion: ").strip()
            users = get_inactive_users(name=name)
            emails = [u["email"] for u in users]
            delete_users_by_email(emails)
        elif idx == 5:
            users = get_inactive_users()
            emails = [u["email"] for u in users]
            enable_users_by_email(emails)
        elif idx == 6:
            name = input("Enter name filter for enabling: ").strip()
            users = get_inactive_users(name=name)
            emails = [u["email"] for u in users]
            enable_users_by_email(emails)


# ---------------- Uninstall ----------------
def uninstall_tool():
    print(f"\n{RED}Uninstalling X-UI Management Tool...{RESET}")
    script_path = "/opt/xuim/uninstall.sh"
    try:
        if os.path.isfile(script_path):
            os.system(f"bash {script_path}")
        else:
            if os.path.isdir("/opt/xuim"):
                os.system("rm -rf /opt/xuim")
            if os.path.isfile("/usr/bin/xuim"):
                os.remove("/usr/bin/xuim")
        print(f"{GREEN}Uninstalled (best-effort).{RESET}")
    except Exception as e:
        print(f"{RED}Uninstall failed: {e}{RESET}")
    input("Press Enter to continue...")


# ---------------- Main Menu (custom layout so Uninstall is red + separated) ----------------
def main_menu():
    while True:
        os.system("clear")
        print(f"\n{CYAN}==== X-UI Management Tool ===={RESET}")
        print(f"{YELLOW}1. Expired Users Management{RESET}")
        print(f"{YELLOW}2. Not-started Users Management{RESET}")
        print(f"{YELLOW}3. Update Client Traffic{RESET}")
        print(f"{YELLOW}4. Inactive Users Management{RESET}")
        # blank line separator
        print()
        print(f"{RED}5. Uninstall X-UI Management Tool{RESET}")
        print(f"{RED}0. Exit{RESET}")

        choice = input("\nEnter choice: ").strip()
        if choice == "0":
            print(f"{RED}Bye.{RESET}")
            sys.exit(0)
        elif choice == "1":
            expired_users_menu()
        elif choice == "2":
            not_started_menu()
        elif choice == "3":
            update_client_traffic()
        elif choice == "4":
            inactive_users_menu()
        elif choice == "5":
            uninstall_tool()
        else:
            print(f"{RED}Invalid choice!{RESET}")


# ---------------- Run ----------------
if __name__ == "__main__":
    main_menu()
