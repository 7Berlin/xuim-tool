#!/usr/bin/env python3
import sqlite3
import json
import time
import os
import sys
from tabulate import tabulate

# -------------------- Colors --------------------
RESET = "\033[0m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"

# -------------------- Config --------------------
DB_PATH = "/etc/x-ui/x-ui.db"
now = int(time.time())


# -------------------- DB --------------------
def connect_db():
    try:
        return sqlite3.connect(DB_PATH)
    except Exception as e:
        print(f"{RED}Cannot open database '{DB_PATH}': {e}{RESET}")
        sys.exit(1)


# -------------------- Menu Helper --------------------
def menu_select(options, title="Menu"):
    print(f"\n{CYAN}{title}{RESET}")
    for idx, option in enumerate(options, start=1):
        print(f"{idx}. {option}")
    print(f"{RED}0. Back/Exit{RESET}")
    choice = input("Enter choice: ").strip()
    if choice == "0":
        return 0
    try:
        choice = int(choice)
        if 1 <= choice <= len(options):
            return choice
    except:
        pass
    print(f"{RED}Invalid choice!{RESET}")
    return -1


# -------------------- Expired Users --------------------
def list_inbounds():
    conn = connect_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, remark, settings FROM inbounds")
        rows = cursor.fetchall()
    except Exception as e:
        print(f"{RED}DB query failed: {e}{RESET}")
        rows = []
    conn.close()
    return rows


def get_expired_users(days=0, name=None):
    inbounds = list_inbounds()
    expired_users = []
    for inbound_id, remark, settings_json in inbounds:
        try:
            settings = json.loads(settings_json)
        except:
            continue
        clients = settings.get("clients") or []
        for c in clients:
            expiry = c.get("expiryTime", 0)
            if expiry == 0 or expiry == -1:
                continue
            if expiry < now:
                days_expired = (now - expiry) // (24 * 3600)
                if days > 0 and days_expired < days:
                    continue
                email = c.get("email") or c.get("id") or "<no-email>"
                if name and name.lower() not in email.lower():
                    continue
                expired_users.append(
                    {"email": email, "expiryTime": expiry, "days_expired": days_expired}
                )
    return expired_users


def show_expired_table(users):
    if not users:
        print(f"{RED}No expired users found.{RESET}")
        return
    table = []
    for u in users:
        exp_date = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(u["expiryTime"]))
        table.append([u["email"], exp_date, u["days_expired"]])
    print(
        tabulate(
            table, headers=["Email", "Expiry Time", "Days Expired"], tablefmt="grid"
        )
    )


# -------------------- Not Started Users --------------------
def get_not_started_users(name=None):
    inbounds = list_inbounds()
    users = []
    for inbound_id, remark, settings_json in inbounds:
        try:
            settings = json.loads(settings_json)
        except:
            continue
        clients = settings.get("clients") or []
        for c in clients:
            expiry = c.get("expiryTime", 0)
            if expiry != 0:
                continue
            email = c.get("email") or c.get("id") or "<no-email>"
            if name and name.lower() not in email.lower():
                continue
            users.append({"email": email})
    return users


def show_not_started_table(users):
    if not users:
        print(f"{RED}No not-started users found.{RESET}")
        return
    table = [[u["email"], "Not started"] for u in users]
    print(tabulate(table, headers=["Email", "Status"], tablefmt="grid"))


# -------------------- Update Traffic --------------------
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


# -------------------- Inactive Users --------------------
def get_inactive_users(name=None):
    inbounds = list_inbounds()
    users = []
    for inbound_id, remark, settings_json in inbounds:
        try:
            settings = json.loads(settings_json)
        except:
            continue
        clients = settings.get("clients") or []
        for c in clients:
            if c.get("enable", True):
                continue
            email = c.get("email") or c.get("id") or "<no-email>"
            if name and name.lower() not in email.lower():
                continue
            users.append({"email": email, "inbound_id": inbound_id, "client_obj": c})
    return users


def show_inactive_users_table(users):
    if not users:
        print(f"{RED}No inactive users found.{RESET}")
        return
    table = [[u["email"]] for u in users]
    print(tabulate(table, headers=["Email"], tablefmt="grid"))


def delete_users_by_email(emails):
    if not emails:
        print(f"{RED}No users to delete.{RESET}")
        return
    inbounds = list_inbounds()
    conn = connect_db()
    cursor = conn.cursor()
    removed = 0
    try:
        for inbound_id, remark, settings_json in inbounds:
            try:
                settings = json.loads(settings_json)
            except:
                continue
            clients = settings.get("clients") or []
            new_clients = [
                c
                for c in clients
                if (c.get("email") or c.get("id") or "") not in emails
            ]
            if len(new_clients) != len(clients):
                settings["clients"] = new_clients
                cursor.execute(
                    "UPDATE inbounds SET settings=? WHERE id=?",
                    (json.dumps(settings), inbound_id),
                )
                removed += len(clients) - len(new_clients)
        conn.commit()
        print(f"{GREEN}Deleted {removed} users.{RESET}")
    finally:
        conn.close()


def enable_users_by_email(emails):
    if not emails:
        print(f"{RED}No users to enable.{RESET}")
        return
    inbounds = list_inbounds()
    conn = connect_db()
    cursor = conn.cursor()
    try:
        for inbound_id, remark, settings_json in inbounds:
            try:
                settings = json.loads(settings_json)
            except:
                continue
            clients = settings.get("clients") or []
            changed = False
            for c in clients:
                if (c.get("email") or c.get("id") or "") in emails:
                    if not c.get("enable", True):
                        c["enable"] = True
                        changed = True
            if changed:
                cursor.execute(
                    "UPDATE inbounds SET settings=? WHERE id=?",
                    (json.dumps(settings), inbound_id),
                )
        conn.commit()
        print(f"{GREEN}Enabled {len(emails)} users.{RESET}")
    finally:
        conn.close()


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
            show_inactive_users_table(users)
        elif idx == 2:
            name = input("Enter name filter: ").strip()
            users = get_inactive_users(name=name)
            show_inactive_users_table(users)
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


# -------------------- Main Menu --------------------
def main_menu():
    while True:
        options = [
            "Expired Users Management",
            "Not-started Users Management",
            "Update Client Traffic",
            "Inactive Users Management",
        ]
        idx = menu_select(options, "X-UI Management Tool")
        if idx == 0:
            print(f"{GREEN}Bye.{RESET}")
            sys.exit(0)
        elif idx == 1:
            expired = get_expired_users()
            show_expired_table(expired)
        elif idx == 2:
            not_started = get_not_started_users()
            show_not_started_table(not_started)
        elif idx == 3:
            update_client_traffic()
        elif idx == 4:
            inactive_users_menu()


if __name__ == "__main__":
    main_menu()
