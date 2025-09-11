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
def menu_select(options, title="Menu"):
    print("\033[1;36m" + title + "\033[0m\n")  # Cyan title
    for idx, option in enumerate(options, start=1):
        print(f"\033[1;33m{idx}.\033[0m {option}")  # Yellow numbers
    print(
        f"\033[1;31m0.\033[0m {'Exit' if title == 'X-UI Management Tool' else 'Back'}"
    )  # Red 0 option
    choice = input("\nEnter number: ").strip()
    if choice.isdigit():
        idx = int(choice)
        if idx == 0:
            return 0
        elif 1 <= idx <= len(options):
            return idx
    print("Invalid choice, try again.")
    return menu_select(options, title)


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
    idx = menu_select(options, "Select Inbound")
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
                "SELECT id, settings, port FROM inbounds WHERE id=?", (inbound_id,)
            )
        else:
            cursor.execute("SELECT id, settings, port FROM inbounds")
        rows = cursor.fetchall()
    except Exception as e:
        print(f"DB query failed: {e}")
        conn.close()
        return []

    expired_users = []
    for row in rows:
        inbound_id_row, settings_json, port = row
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
                continue
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
                if name and name.lower() not in email.lower():
                    continue
                expired_users.append(
                    {
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
                "SELECT id, settings, port FROM inbounds WHERE id=?", (inbound_id,)
            )
        else:
            cursor.execute("SELECT id, settings, port FROM inbounds")
        rows = cursor.fetchall()
    except Exception as e:
        print(f"DB query failed: {e}")
        conn.close()
        return []

    not_started = []
    for row in rows:
        inbound_id_row, settings_json, port = row
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
                continue
            email = (
                c.get("email") or c.get("emailAddress") or c.get("id") or "<no-email>"
            )
            not_started.append({"port": port, "email": email, "expiryTime": expiry_sec})
    conn.close()
    return not_started


def get_unlimited_users(inbound_id=None):
    conn = connect_db()
    cursor = conn.cursor()
    try:
        if inbound_id:
            cursor.execute(
                "SELECT id, settings, port FROM inbounds WHERE id=?", (inbound_id,)
            )
        else:
            cursor.execute("SELECT id, settings, port FROM inbounds")
        rows = cursor.fetchall()
    except Exception as e:
        print(f"DB query failed: {e}")
        conn.close()
        return []

    unlimited = []
    for row in rows:
        inbound_id_row, settings_json, port = row
        try:
            settings = json.loads(settings_json)
        except Exception:
            continue
        clients = settings.get("clients") or []
        for c in clients:
            expiry_ms = c.get("expiryTime", 0) or 0
            if expiry_ms != 0:
                continue
            email = (
                c.get("email") or c.get("emailAddress") or c.get("id") or "<no-email>"
            )
            unlimited.append({"port": port, "email": email})
    conn.close()
    return unlimited


def get_inactive_users(inbound_id=None):
    conn = connect_db()
    cursor = conn.cursor()
    try:
        if inbound_id:
            cursor.execute(
                "SELECT id, settings, port FROM inbounds WHERE id=?", (inbound_id,)
            )
        else:
            cursor.execute("SELECT id, settings, port FROM inbounds")
        rows = cursor.fetchall()
    except Exception as e:
        print(f"DB query failed: {e}")
        conn.close()
        return []

    inactive = []
    for row in rows:
        inbound_id_row, settings_json, port = row
        try:
            settings = json.loads(settings_json)
        except Exception:
            continue
        clients = settings.get("clients") or []
        for c in clients:
            if c.get("enable", True):
                continue
            email = (
                c.get("email") or c.get("emailAddress") or c.get("id") or "<no-email>"
            )
            inactive.append({"port": port, "email": email})
    conn.close()
    return inactive


def delete_users(users):
    """
    Delete users completely from all inbounds and client_traffics.
    users: list of dicts with keys 'email' and optionally 'inbound_id'
    """
    if not users:
        print("No users to delete.")
        return

    emails_to_remove = set(u["email"] for u in users if u.get("email"))
    if not emails_to_remove:
        print("No valid emails to delete.")
        return

    conn = connect_db()
    cursor = conn.cursor()
    removed_count = 0

    try:
        # 1. Remove users from all inbounds
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
                if (c.get("email") or c.get("id") or "") not in emails_to_remove
            ]
            if len(new_clients) < len(clients):
                settings["clients"] = new_clients
                cursor.execute(
                    "UPDATE inbounds SET settings=? WHERE id=?",
                    (json.dumps(settings, ensure_ascii=False), inbound_id),
                )
                removed_count += len(clients) - len(new_clients)

        # 2. Remove from client_traffics
        for email in emails_to_remove:
            cursor.execute("DELETE FROM client_traffics WHERE email=?", (email,))
        conn.commit()
        print(f"✅ Deleted {removed_count} users and removed their traffic records.")

    except Exception as e:
        print(f"Failed to delete users: {e}")
    finally:
        conn.close()
    if not users:
        print("No users to delete.")
        return
    conn = connect_db()
    cursor = conn.cursor()
    removed = 0
    for u in users:
        try:
            # حذف کاربر از inbounds
            cursor.execute(
                "SELECT settings FROM inbounds WHERE id=?", (u["inbound_id"],)
            )
            row = cursor.fetchone()
            if row:
                settings = json.loads(row[0])
                clients = settings.get("clients") or []
                new_clients = [
                    c for c in clients if (c.get("email") or c.get("id")) != u["email"]
                ]
                if len(new_clients) < len(clients):
                    settings["clients"] = new_clients
                    cursor.execute(
                        "UPDATE inbounds SET settings=? WHERE id=?",
                        (json.dumps(settings, ensure_ascii=False), u["inbound_id"]),
                    )
                    removed += 1
                    print(f"Removed {u['email']} from inbounds")

            # حذف رکوردهای ترافیک مرتبط در client_traffics
            cursor.execute("DELETE FROM client_traffics WHERE email=?", (u["email"],))
            conn.commit()
            print(f"Removed {u['email']} from client_traffics")
        except Exception as e:
            print(f"Failed to remove {u.get('email')}: {e}")
            continue

    conn.close()
    print(f"Deletion completed. Total removed attempts: {removed}")
    if not users:
        print("No users to delete.")
        return
    conn = connect_db()
    cursor = conn.cursor()
    removed = 0
    for u in users:
        try:
            # حذف از inbounds
            cursor.execute(
                "SELECT settings FROM inbounds WHERE id=?", (u["inbound_id"],)
            )
            row = cursor.fetchone()
            if row:
                settings = json.loads(row[0])
                clients = settings.get("clients") or []
                new_clients = [
                    c for c in clients if (c.get("email") or c.get("id")) != u["email"]
                ]
                settings["clients"] = new_clients
                cursor.execute(
                    "UPDATE inbounds SET settings=? WHERE id=?",
                    (json.dumps(settings, ensure_ascii=False), u["inbound_id"]),
                )

            # حذف از client_traffics
            cursor.execute("DELETE FROM client_traffics WHERE email=?", (u["email"],))

            removed += 1
            print(f"Removed {u['email']} (from inbounds & client_traffics)")
        except Exception as e:
            print(f"Failed to remove {u.get('email')}: {e}")
            continue
    conn.commit()
    conn.close()
    print(f"Deletion completed. Total removed attempts: {removed}")
    if not users:
        print("No users to delete.")
        return
    conn = connect_db()
    cursor = conn.cursor()
    removed = 0
    for u in users:
        try:
            # پاک کردن از inbounds
            cursor.execute(
                "SELECT settings FROM inbounds WHERE id=?", (u["inbound_id"],)
            )
            row = cursor.fetchone()
            if row:
                settings = json.loads(row[0])
                clients = settings.get("clients") or []
                new_clients = [
                    c for c in clients if (c.get("email") or c.get("id")) != u["email"]
                ]
                if len(new_clients) < len(clients):
                    settings["clients"] = new_clients
                    cursor.execute(
                        "UPDATE inbounds SET settings=? WHERE id=?",
                        (json.dumps(settings, ensure_ascii=False), u["inbound_id"]),
                    )
                    removed += 1
                    print(f"Removed {u['email']} from inbound {u['inbound_id']}")

            # پاک کردن از client_traffics
            cursor.execute("DELETE FROM client_traffics WHERE email=?", (u["email"],))
            conn.commit()
        except Exception as e:
            print(f"Failed to remove {u.get('email')}: {e}")
            continue
    conn.close()
    print(f"Deletion completed. Total removed attempts: {removed}")
    if not users:
        print("No users to delete.")
        return
    conn = connect_db()
    cursor = conn.cursor()
    removed = 0
    for u in users:
        try:
            cursor.execute("SELECT settings FROM inbounds WHERE port=?", (u["port"],))
            row = cursor.fetchone()
            if not row:
                continue
            settings = json.loads(row[0])
            clients = settings.get("clients") or []
            new_clients = [
                c for c in clients if (c.get("email") or c.get("id")) != u["email"]
            ]
            if len(new_clients) == len(clients):
                continue
            settings["clients"] = new_clients
            cursor.execute(
                "UPDATE inbounds SET settings=? WHERE port=?",
                (json.dumps(settings, ensure_ascii=False), u["port"]),
            )
            removed += 1
            print(f"Removed {u['email']}")
        except Exception as e:
            print(f"Failed to remove {u.get('email')}: {e}")
    conn.commit()
    conn.close()
    print(f"Deletion completed. Total removed attempts: {removed}")


# ------------------------- Display Tables ------------------------- #
def show_table(users, status="expired"):
    if not users:
        print(f"No {status} users found.")
        return
    table = []
    if status == "expired":
        for u in users:
            exp_date = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(u["expiryTime"])
            )
            table.append([u["email"], u["port"], exp_date, u["days_expired"]])
        print(
            tabulate(
                table,
                headers=["Email", "Port", "Expiry Time", "Days Expired"],
                tablefmt="grid",
            )
        )
    elif status == "not_started":
        for u in users:
            table.append([u["email"], u["port"], "Not started"])
        print(tabulate(table, headers=["Email", "Port", "Status"], tablefmt="grid"))
    else:  # unlimited or inactive
        for u in users:
            table.append([u["email"], u["port"]])
        print(tabulate(table, headers=["Email", "Port"], tablefmt="grid"))


# ------------------------- Update Client Traffic ------------------------- #
def update_client_traffic():
    print("\n\033[1;36mUpdate Client Traffic (Upload & Download)\033[0m\n")
    conn = connect_db()
    cursor = conn.cursor()

    while True:
        email = input("Enter client email (or 0 to go back): ").strip()
        if email == "0":
            break
        if not email:
            print("Email cannot be empty.")
            continue

        try:
            down_gb = input("Enter download traffic in GB: ").strip()
            up_gb = input("Enter upload traffic in GB: ").strip()

            new_down = int(float(down_gb) * 1073741824) if down_gb else 0
            new_up = int(float(up_gb) * 1073741824) if up_gb else 0

            # 1. آپدیت client_traffics
            cursor.execute(
                "SELECT all_time FROM client_traffics WHERE email=?", (email,)
            )
            row = cursor.fetchone()
            current_all_time = row[0] if row else 0
            new_all_time = current_all_time + new_up + new_down

            cursor.execute(
                "UPDATE client_traffics SET up=?, down=?, all_time=? WHERE email=?",
                (new_up, new_down, new_all_time, email),
            )

            # 2. آپدیت inbounds
            cursor.execute("SELECT id, settings FROM inbounds")
            for inbound_id, settings_json in cursor.fetchall():
                try:
                    settings = json.loads(settings_json)
                    modified = False
                    for client in settings.get("clients", []):
                        if client.get("email") == email:
                            client["up"] = new_up
                            client["down"] = new_down
                            client["all_time"] = new_all_time
                            modified = True
                    if modified:
                        cursor.execute(
                            "UPDATE inbounds SET settings=? WHERE id=?",
                            (json.dumps(settings, ensure_ascii=False), inbound_id),
                        )
                except Exception:
                    continue

            conn.commit()
            print(
                f"✅ Updated {email}: Down={down_gb} GB, Up={up_gb} GB, All-time={new_all_time / 1073741824:.2f} GB"
            )

        except Exception as e:
            print(f"❌ Failed to update traffic: {e}")

    conn.close()


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
        idx = menu_select(options, "Expired Users Management")
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
        idx = menu_select(options, "Not-started Users Management")
        if idx == 0:
            break
        elif idx == 1:
            users = get_not_started_users(inbound_id=inbound_id)
            show_table(users, status="not_started")
        elif idx == 2:
            name = input("Enter name substring: ").strip()
            users = [
                u
                for u in get_not_started_users(inbound_id=inbound_id)
                if name.lower() in (u["email"] or "").lower()
            ]
            show_table(users, status="not_started")
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
            show_table(users, status="not_started")
            if (
                users
                and input("Delete ALL not-started users shown here? (yes/no): ")
                .strip()
                .lower()
                == "yes"
            ):
                delete_users(users)


def unlimited_menu():
    inbound_id = select_inbound()
    while True:
        options = ["Show Unlimited Users"]
        idx = menu_select(options, "Unlimited Users Management")
        if idx == 0:
            break
        elif idx == 1:
            users = get_unlimited_users(inbound_id=inbound_id)
            show_table(users, status="unlimited")


def inactive_menu():
    inbound_id = select_inbound()
    while True:
        options = ["Show All Inactive Users", "Enable All Inactive Users"]
        idx = menu_select(options, "Inactive Users Management")
        if idx == 0:
            break
        elif idx == 1:
            users = get_inactive_users(inbound_id=inbound_id)
            show_table(users, status="inactive")
        elif idx == 2:
            users = get_inactive_users(inbound_id=inbound_id)
            # Enable logic
            conn = connect_db()
            cursor = conn.cursor()
            enabled_count = 0
            for u in users:
                try:
                    cursor.execute(
                        "SELECT settings FROM inbounds WHERE port=?", (u["port"],)
                    )
                    row = cursor.fetchone()
                    if not row:
                        continue
                    settings = json.loads(row[0])
                    clients = settings.get("clients") or []
                    changed = False
                    for c in clients:
                        if (c.get("email") or c.get("id")) == u["email"] and not c.get(
                            "enable", True
                        ):
                            c["enable"] = True
                            changed = True
                    if changed:
                        cursor.execute(
                            "UPDATE inbounds SET settings=? WHERE port=?",
                            (json.dumps(settings, ensure_ascii=False), u["port"]),
                        )
                        enabled_count += 1
                except:
                    continue
            conn.commit()
            conn.close()
            print(f"Enabled {enabled_count} users.")


def uninstall_tool():
    print("\033[1;31mUninstall X-UI Management Tool\033[0m\n")
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


# ------------------------- Main Menu ------------------------- #
def main_menu():
    while True:
        options = [
            "Expired Users Management",
            "Not-started Users (expiryTime < 0)",
            "Unlimited Users",
            "Inactive Users",
            "Update Client Traffic",
            "",
            "Uninstall X-UI Management Tool",
        ]
        idx = menu_select(options, "X-UI Management Tool")
        if idx == 0:
            print("Bye.")
            sys.exit(0)
        elif idx == 1:
            expired_users_menu()
        elif idx == 2:
            not_started_menu()
        elif idx == 3:
            unlimited_menu()
        elif idx == 4:
            inactive_menu()
        elif idx == 5:
            update_client_traffic()
        elif idx == 7:
            uninstall_tool()
    while True:
        options = [
            "Expired Users Management",
            "Not-started Users (expiryTime < 0)",
            "Unlimited Users",
            "Inactive Users",
            "",
            "Uninstall X-UI Management Tool",
        ]
        idx = menu_select(options, "X-UI Management Tool")
        if idx == 0:
            print("Bye.")
            sys.exit(0)
        elif idx == 1:
            expired_users_menu()
        elif idx == 2:
            not_started_menu()
        elif idx == 3:
            unlimited_menu()
        elif idx == 4:
            inactive_menu()
        elif idx == 6:
            uninstall_tool()


if __name__ == "__main__":
    main_menu()
