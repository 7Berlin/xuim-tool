import os
import sqlite3
import json
import time

# رنگ‌ها
RED = "\033[91m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
RESET = "\033[0m"

DB_PATH = "/etc/x-ui/x-ui.db"


def clear_screen():
    os.system("clear")


def fetch_inbounds():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, remark, settings, port FROM inbounds")
    inbounds = cursor.fetchall()
    conn.close()
    return inbounds


def parse_clients(inbounds):
    clients_data = []
    current_time = int(time.time() * 1000)

    for inbound_id, remark, settings, port in inbounds:
        settings_json = json.loads(settings)
        for client in settings_json.get("clients", []):
            expiry_time = client.get("expiryTime", 0)
            email = client.get("email", "")
            enable = client.get("enable", True)

            if expiry_time == 0:
                status = "Unlimited"
            elif expiry_time > current_time:
                remaining = (expiry_time - current_time) // 1000
                days = remaining // 86400
                status = f"Not Started - {days} Days"
            else:
                status = "Expired"

            clients_data.append(
                {
                    "inbound_id": inbound_id,
                    "inbound": remark,
                    "port": port,
                    "email": email,
                    "status": status,
                    "enable": enable,
                }
            )
    return clients_data


def update_client_traffic(email, upload_gb, download_gb):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    upload_bytes = upload_gb * (1024**3)
    download_bytes = download_gb * (1024**3)
    cursor.execute(
        """
        UPDATE client_traffics
        SET up = ?, down = ?
        WHERE email = ?
    """,
        (upload_bytes, download_bytes, email),
    )
    conn.commit()
    conn.close()


def uninstall_tool():
    print(f"\n{RED}Uninstalling X-UI Management Tool...{RESET}")
    os.remove(__file__)
    print(f"{GREEN}Tool successfully uninstalled.{RESET}")


# ===================== Disabled Users Menu =====================
def disabled_users_menu():
    clients = parse_clients(fetch_inbounds())
    disabled = [c for c in clients if not c["enable"]]

    while True:
        clear_screen()
        print("=== Disabled Users Management ===")
        print(f"{YELLOW}1. Show Disabled Users{RESET}")
        print(f"{YELLOW}2. Search Disabled Users by Name{RESET}")
        print(f"{YELLOW}3. Delete Disabled Users{RESET}")
        print(f"{YELLOW}4. Delete Disabled Users by Name{RESET}")
        print(f"{YELLOW}5. Enable Disabled Users{RESET}")
        print(f"{YELLOW}6. Enable Disabled Users by Name{RESET}")
        print(f"{RED}0. Back{RESET}")

        choice = input("\nChoose an option: ")

        if choice == "0":
            break
        elif choice == "1":
            show_disabled(disabled)
        elif choice == "2":
            name = input("Enter part of name: ")
            show_disabled([u for u in disabled if name in u["email"]])
        elif choice == "3":
            bulk_delete([u["email"] for u in disabled])
        elif choice == "4":
            name = input("Enter part of name to delete: ")
            bulk_delete([u["email"] for u in disabled if name in u["email"]])
        elif choice == "5":
            bulk_enable([u["email"] for u in disabled])
        elif choice == "6":
            name = input("Enter part of name to enable: ")
            bulk_enable([u["email"] for u in disabled if name in u["email"]])
        input("\nPress Enter to continue...")


def show_disabled(users):
    if not users:
        print(f"{RED}No disabled users found.{RESET}")
        return
    for u in users:
        print(
            f"{YELLOW}{u['email']}{RESET} | {u['inbound']}:{u['port']} | {u['status']}"
        )


def bulk_delete(emails):
    if not emails:
        print(f"{RED}No users to delete.{RESET}")
        return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for email in emails:
        cursor.execute("DELETE FROM client_traffics WHERE email = ?", (email,))
    conn.commit()
    conn.close()
    print(f"{GREEN}Deleted {len(emails)} disabled users.{RESET}")


def bulk_enable(emails):
    if not emails:
        print(f"{RED}No users to enable.{RESET}")
        return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for email in emails:
        cursor.execute(
            "UPDATE inbounds SET settings = REPLACE(settings, '\"enable\": false', '\"enable\": true') WHERE settings LIKE ?",
            (f"%{email}%",),
        )
    conn.commit()
    conn.close()
    print(f"{GREEN}Enabled {len(emails)} disabled users.{RESET}")


# ===================== Main Menu =====================
def main_menu():
    while True:
        clear_screen()
        print("==== X-UI Management Tool ====")
        print(f"{YELLOW}1. Expired Users Management{RESET}")
        print(f"{YELLOW}2. Not-started Users Management{RESET}")
        print(f"{YELLOW}3. Unlimited Users Management{RESET}")
        print(f"{YELLOW}4. Update Client Traffic{RESET}")
        print(f"{YELLOW}5. Disabled Users Management{RESET}")

        print()  # فاصله
        print(f"{RED}6. Uninstall X-UI Management Tool{RESET}")
        print(f"{RED}0. Exit{RESET}")

        choice = input("\nChoose an option: ")

        if choice == "1":
            print("👉 Expired Users Management (soon...)")
            input("Press Enter to continue...")
        elif choice == "2":
            print("👉 Not-started Users Management (soon...)")
            input("Press Enter to continue...")
        elif choice == "3":
            print("👉 Unlimited Users Management (soon...)")
            input("Press Enter to continue...")
        elif choice == "4":
            update_traffic_menu()
        elif choice == "5":
            disabled_users_menu()
        elif choice == "6":
            uninstall_tool()
            break
        elif choice == "0":
            break


def update_traffic_menu():
    clients = parse_clients(fetch_inbounds())
    active = [c for c in clients if c["enable"]]

    while True:
        clear_screen()
        print("=== Update Client Traffic ===")
        for i, client in enumerate(active, start=1):
            print(f"{i}. {client['email']} ({client['inbound']}:{client['port']})")
        print(f"{RED}0. Back{RESET}")

        choice = input("\nSelect a client: ")
        if choice == "0":
            break

        if not choice.isdigit() or not (1 <= int(choice) <= len(active)):
            input("Invalid choice! Press Enter...")
            continue

        client = active[int(choice) - 1]
        try:
            up_gb = int(input("Enter Upload (GB): "))
            down_gb = int(input("Enter Download (GB): "))
            update_client_traffic(client["email"], up_gb, down_gb)
            print(f"{GREEN}Traffic updated for {client['email']}.{RESET}")
        except ValueError:
            print(f"{RED}Invalid input!{RESET}")
        input("Press Enter to continue...")


if __name__ == "__main__":
    main_menu()
