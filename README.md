# 🛠 X-UI Management Tool

> A simple command-line tool to manage **X-UI clients** in your server.  
> Easily monitor, update, and maintain client accounts, traffic, and expiry times.

---
## 🖥 Installation
```bash
bash <(curl -s https://raw.githubusercontent.com/7berlin/xuim-tool/main/install.sh)
```
---
## ⚡ Usage
- ✅ **Running Command**  

```bash
xuim
```
---
## 💡 Features

- ✅ **Expired Users Management**  
  - Show all expired users  
  - Filter by name substring  
  - Filter by expiration days  
  - Delete expired users

- ✅ **Not-started Users Management**  
  - Show clients whose accounts have not started  
  - Delete all or filtered by name

- ✅ **Unlimited Users Management**  
  - Show all users with unlimited access

- ✅ **Inactive Users Management**  
  - Show inactive clients  
  - Enable inactive clients

- ✅ **Update Client Traffic**  
  - Update upload & download for clients  
  - **All-time traffic** auto-updates based on changes

- ✅ **Give Days To Clients**  
  - Add or subtract time from client accounts  
  - Apply to all clients or filtered by name

- ✅ **Safe & Reliable**  
  - Works directly with the SQLite database (`x-ui.db`)  
  - Handles all clients’ settings automatically

- ✅ **Uninstall Tool**  
  - One command to remove the tool safely

---
## 🚨 Safety Notes
- Always backup your x-ui.db before batch operations
- Deletion is irreversible
---
## ❌ Uninstall
```bash
bash <(curl -s https://raw.githubusercontent.com/7berlin/xuim-tool/main/uninstall.sh)
```
---
## 💖 Support

> If you like this project and want to support the development, please give a ⭐ on the GitHub repository:

> https://github.com/7berlin/xuim-tool