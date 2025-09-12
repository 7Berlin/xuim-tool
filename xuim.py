import sqlite3
import json
import subprocess
import time
import os
import sys
from tabulate import tabulate

__version__ = "v1.0.0"
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
def menu_select(options, title="Menu", gap_after=None):
    if gap_after is None:
        gap_after = [6, 8]

    print("\033[1;36m" + title + "\033[0m\n")
    for idx, option in enumerate(options, start=1):
        print(f"\033[1;33m{idx}.\033[0m {option}")
        if idx in gap_after:
            print()

    print(
        f"\033[1;31m0.\033[0m {'Exit' if title == f'X-UI Management Tool {__version__}' else 'Back'}"
    )

    choice = input("\nEnter number: ").strip()
    if choice.isdigit():
        idx = int(choice)
        if idx == 0:
            return 0
        elif 1 <= idx <= len(options):
            return idx
    print("Invalid choice, try again.")
    return menu_select(options, title, gap_after)


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
    users: list of dicts with keys 'email'
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
        # Loop all inbounds
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

        # Delete traffic records for all emails
        for email in emails_to_remove:
            cursor.execute("DELETE FROM client_traffics WHERE email=?", (email,))

        conn.commit()
        print(f"✅ Deleted {removed_count} users and removed their traffic records.")

    except Exception as e:
        print(f"Failed to delete users: {e}")
    finally:
        conn.close()


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
    else:
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

            down = int(float(down_gb) * 1073741824) if down_gb else 0
            up = int(float(up_gb) * 1073741824) if up_gb else 0

            cursor.execute(
                "SELECT down, up, all_time FROM client_traffics WHERE email=?",
                (email,),
            )
            row = cursor.fetchone()
            if row:
                current_down, current_up, current_all_time = row
                delta = (up - current_up) + (down - current_down)
                new_all_time = max(current_all_time + delta, 0)

                cursor.execute(
                    "UPDATE client_traffics SET down=?, up=?, all_time=? WHERE email=?",
                    (down, up, new_all_time, email),
                )
            else:
                cursor.execute(
                    "INSERT INTO client_traffics (email, down, up, all_time) VALUES (?, ?, ?, ?)",
                    (email, down, up, down + up),
                )

            cursor.execute("SELECT id, settings FROM inbounds")
            inbounds = cursor.fetchall()
            for inbound_id, settings in inbounds:
                try:
                    settings_json = json.loads(settings)
                    modified = False
                    if "clients" in settings_json:
                        for client in settings_json["clients"]:
                            if client.get("email") == email:
                                current_client_up = client.get("up", 0)
                                current_client_down = client.get("down", 0)
                                current_client_all_time = client.get("all_time", 0)

                                delta_client = (up - current_client_up) + (
                                    down - current_client_down
                                )
                                client["up"] = down
                                client["down"] = up
                                client["all_time"] = max(
                                    current_client_all_time + delta_client, 0
                                )
                                modified = True
                    if modified:
                        cursor.execute(
                            "UPDATE inbounds SET settings=? WHERE id=?",
                            (json.dumps(settings_json, ensure_ascii=False), inbound_id),
                        )
                except Exception:
                    continue

            conn.commit()
            print(
                f"✅ Updated traffic for {email} (Down: {down_gb} GB, Up: {up_gb} GB)"
            )

        except Exception as e:
            print(f"❌ Failed to update traffic: {e}")

    conn.close()


# ------------------------- Give Days ------------------------- #


def give_days_to_clients():
    print("\n\033[1;36mGive / Subtract Days To Clients\033[0m\n")
    inbounds_selected = select_inbound()
    if inbounds_selected is None:
        inbounds_ids = [i[0] for i in list_inbounds()]
    else:
        inbounds_ids = [inbounds_selected]

    while True:
        options = [
            "Add days to all non-expired clients",
            "Add days to non-expired clients containing a name",
            "Subtract days from all non-expired clients",
            "Subtract days from non-expired clients containing a name",
        ]
        idx = menu_select(options, "Give Days To Clients")
        if idx == 0:
            break

        days_input = input("Enter number of days: ").strip()
        if not days_input.isdigit():
            print("Invalid number of days.")
            continue
        days = int(days_input)

        name_filter = None
        if idx in [3, 4]:
            days = -days
        if idx == 2 or idx == 4:
            name_filter = input("Enter name substring to filter: ").strip()

        conn = connect_db()
        cursor = conn.cursor()
        try:
            for inbound_id in inbounds_ids:
                cursor.execute(
                    "SELECT id, settings FROM inbounds WHERE id=?", (inbound_id,)
                )
                row = cursor.fetchone()
                if not row:
                    continue
                inbound_id_row, settings_json = row
                settings = json.loads(settings_json)
                modified = False
                clients = settings.get("clients") or []

                for client in clients:
                    expiry_ms = client.get("expiryTime", 0) or 0
                    expiry_sec = expiry_ms // 1000
                    if expiry_sec <= now:
                        continue
                    email = client.get("email") or client.get("id") or "<no-email>"
                    if name_filter and name_filter.lower() not in email.lower():
                        continue
                    new_expiry_sec = expiry_sec + days * 24 * 3600
                    if new_expiry_sec < now:
                        new_expiry_sec = now
                    client["expiryTime"] = new_expiry_sec * 1000
                    modified = True

                if modified:
                    cursor.execute(
                        "UPDATE inbounds SET settings=? WHERE id=?",
                        (json.dumps(settings, ensure_ascii=False), inbound_id_row),
                    )
            conn.commit()
            print(f"✅ Updated expiry for applicable clients by {days} days.")

        except Exception as e:
            print(f"❌ Failed to update clients: {e}")
        finally:
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
    confirm = (
        input("⚠️ Are you sure you want to uninstall X-UI Management Tool? (yes/no): ")
        .strip()
        .lower()
    )
    if confirm != "yes":
        print("❌ Uninstall cancelled. Returning to main menu...")
        return

    try:
        print("🚀 Running uninstall script...")
        result = subprocess.run(
            "bash <(curl -s https://raw.githubusercontent.com/7berlin/xuim-tool/main/uninstall.sh)",
            shell=True,
            executable="/bin/bash",
        )
        if result.returncode == 0:
            print("✅ Uninstall completed successfully. Exiting program...")
            sys.exit(0)
        else:
            print(f"❌ Uninstall script failed with exit code {result.returncode}")
    except Exception as e:
        print(f"⚠️ Error running uninstall script: {e}")


def update_tool():
    try:
        print("🚀 Running update script...")
        result = subprocess.run(
            "bash <(curl -s https://raw.githubusercontent.com/7berlin/xuim-tool/main/install.sh)",
            shell=True,
            executable="/bin/bash",
        )
        if result.returncode == 0:
            print("✅ Update completed successfully. You can continue using the tool.")
        else:
            print(f"❌ Update script failed with exit code {result.returncode}")
    except Exception as e:
        print(f"⚠️ Error running update script: {e}")


# ------------------------- Main Menu ------------------------- #
def main_menu():
    while True:
        options = [
            "Expired Users Management",
            "Not-started Users (Start After First Use)",
            "Unlimited Users",
            "Inactive Users",
            "Update Client Traffic",
            "Give/Remove Days To Clients",
            "Update X-UI Management Tool",
            "Uninstall X-UI Management Tool",
        ]
        idx = menu_select(options, f"X-UI Management Tool {__version__}", gap_after=[6])
        if idx == 0:
            print("You can use xuim for run it again.")
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
        elif idx == 6:
            give_days_to_clients()
        elif idx == 7:
            update_tool()
        elif idx == 8:
            uninstall_tool()


if __name__ == "__main__":
    main_menu()
