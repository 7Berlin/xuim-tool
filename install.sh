#!/usr/bin/env python3
import sqlite3
import json
import time
import os
from tabulate import tabulate

DB_PATH = "/etc/x-ui/x-ui.db"
now = int(time.time())

def connect_db():
    return sqlite3.connect(DB_PATH)

def list_inbounds():
    """Return list of inbounds (id, remark)."""
    conn = connect_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, remark FROM inbounds")
    rows = cursor.fetchall()
    conn.close()
    return rows

def select_inbound():
    """Ask user to choose inbound or all."""
    inbounds = list_inbounds()
    if not inbounds:
        print("⚠️ No inbounds found in database.")
        return None

    print("\n===== Inbounds =====")
    for idx, (iid, remark) in enumerate(inbounds, start=1):
        print(f"{idx} - {remark} (ID: {iid})")
    print("0 - All Inbounds")

    choice = input("👉 Select inbound: ").strip()
    if choice == "0":
        return None  # None = All inbounds
    try:
        choice = int(choice)
        if 1 <= choice <= len(inbounds):
            return inbounds[choice-1][0]  # return inbound_id
    except:
        pass
    print("❌ Invalid choice! Defaulting to All Inbounds.")
    return None

def get_expired_users(days=0, name=None, inbound_id=None):
    conn = connect_db()
    cursor = conn.cursor()

    if inbound_id:
        cursor.execute("SELECT id, remark, settings FROM inbounds WHERE id=?", (inbound_id,))
    else:
        cursor.execute("SELECT id, remark, settings FROM inbounds")

    rows = cursor.fetchall()
    expired_users = []

    for row in rows:
        inbound_id, remark, settings_json = row
        try:
            settings = json.loads(settings_json)
        except Exception:
            continue

        if "clients" not in settings:
            continue

        for c in settings["clients"]:
            expiry = c.get("expiryTime", 0)
            if expiry != 0 and expiry < now:
                days_expired = (now - expiry) // (24*3600)

                if days > 0 and days_expired < days:
                    continue
                if name and name.lower() not in (c.get("email") or "").lower():
                    continue

                expired_users.append({
                    "inbound_id": inbound_id,
                    "inbound_remark": remark,
                    "email": c.get("email"),
                    "expiryTime": expiry,
                    "days_expired": days_expired
                })
    conn.close()
    return expired_users

def delete_expired_users(expired_users):
    conn = connect_db()
    cursor = conn.cursor()

    for u in expired_users:
        cursor.execute("SELECT settings FROM inbounds WHERE id=?", (u["inbound_id"],))
        row = cursor.fetchone()
        if not row:
            continue
        settings_json = row[0]
        try:
            settings = json.loads(settings_json)
        except Exception:
            continue

        settings["clients"] = [c for c in settings["clients"] if c.get("email") != u["email"]]
        new_settings_json = json.dumps(settings, ensure_ascii=False)
        cursor.execute("UPDATE inbounds SET settings=? WHERE id=?", (new_settings_json, u["inbound_id"]))
        print(f"[-] Removed {u['email']} from {u['inbound_remark']}")

    conn.commit()
    conn.close()
    print("✅ Deletion completed.")

def show_table(users):
    if not users:
        print("⚠️ No expired users found.")
        return
    table = []
    for u in users:
        exp_date = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(u["expiryTime"]))
        table.append([u['email'], u['inbound_remark'], exp_date, u['days_expired']])
    print(tabulate(table, headers=["Email", "Inbound", "Expiry Time", "Days Expired"], tablefmt="grid"))

def expired_users_menu():
    inbound_id = select_inbound()

    while True:
        print("\n===== Expired Users Management =====")
        print("1 - Show All Expired Users")
        print("2 - Show Expired Users Contain Specific Name")
        print("3 - Show Expired Users More Than Some Days (Default: 30 Days)")
        print("4 - Delete All Expired Users")
        print("5 - Delete Expired Users Contain Specific Name")
        print("6 - Delete Expired Users More Than Some Days (Default: 30 Days)")
        print("0 - Back to Main Menu")

        choice = input("👉 Enter choice: ").strip()
        if choice == "1":
            users = get_expired_users(inbound_id=inbound_id)
            show_table(users)

        elif choice == "2":
            name = input("🔎 Enter name: ").strip()
            users = get_expired_users(name=name, inbound_id=inbound_id)
            show_table(users)

        elif choice == "3":
            days = input("⏳ Days (default 30): ").strip()
            days = int(days) if days.isdigit() else 30
            users = get_expired_users(days=days, inbound_id=inbound_id)
            show_table(users)

        elif choice == "4":
            users = get_expired_users(inbound_id=inbound_id)
            show_table(users)
            if users and input("⚠️ Delete all expired users? (yes/no): ").lower() == "yes":
                delete_expired_users(users)

        elif choice == "5":
            name = input("🔎 Enter name: ").strip()
            users = get_expired_users(name=name, inbound_id=inbound_id)
            show_table(users)
            if users and input(f"⚠️ Delete expired users with name '{name}'? (yes/no): ").lower() == "yes":
                delete_expired_users(users)

        elif choice == "6":
            days = input("⏳ Days (default 30): ").strip()
            days = int(days) if days.isdigit() else 30
            users = get_expired_users(days=days, inbound_id=inbound_id)
            show_table(users)
            if users and input(f"⚠️ Delete expired users older than {days} days? (yes/no): ").lower() == "yes":
                delete_expired_users(users)

        elif choice == "0":
            break
        else:
            print("❌ Invalid choice!")

def uninstall_tool():
    print("⚠️ Uninstalling X-UI Management Tool...")
    os.system("bash /opt/xuim/uninstall.sh")
    exit()

def main_menu():
    while True:
        print("\n===== X-UI Management Tool =====")
        print("1 - Expired Users Management")
        print("9 - Uninstall X-UI Management Tool")
        print("0 - Exit")

        choice = input("👉 Enter choice: ").strip()
        if choice == "1":
            expired_users_menu()
        elif choice == "9":
            uninstall_tool()
        elif choice == "0":
            exit()
        else:
            print("❌ Invalid choice!")

if __name__ == "__main__":
    main_menu()
