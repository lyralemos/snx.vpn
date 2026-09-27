#!/usr/bin/env python3
"""
SNX VPN multi-connection backend for Omarchy plugin.

Connection files: ~/.config/snx/<id>.snxrc  (standard snxrc format)
Metadata files:   ~/.config/snx/<id>.json   (display name, etc.)
Active marker:    ~/.config/snx/.active      (active connection id)
Passwords:        secret-tool  attribute: snx-connection <id>
"""

import sys
import os
import subprocess
import json
import re
import time
import glob
import pty
import select
import termios
import fcntl

SNX_DIR = os.path.expanduser("~/.config/snx")
ACTIVE_FILE = os.path.join(SNX_DIR, ".active")


def ensure_dir() -> None:
    os.makedirs(SNX_DIR, exist_ok=True)


def sanitize_id(name: str) -> str:
    """Convert a display name to a safe filename id."""
    s = re.sub(r"[^a-z0-9-]", "_", name.lower().strip())
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "conn"


def unique_id(base_id: str) -> str:
    """Return a unique id, appending a number suffix if base already exists."""
    candidate = base_id
    i = 2
    while os.path.exists(os.path.join(SNX_DIR, f"{candidate}.snxrc")):
        candidate = f"{base_id}_{i}"
        i += 1
    return candidate


# ── File helpers ──────────────────────────────────────────────────────────────

def _load_connection(conn_id: str) -> dict:
    snxrc_path = os.path.join(SNX_DIR, f"{conn_id}.snxrc")
    meta_path  = os.path.join(SNX_DIR, f"{conn_id}.json")

    conn = {"id": conn_id, "name": conn_id, "server": "", "username": "", "reauth": "yes"}

    if os.path.exists(snxrc_path):
        try:
            with open(snxrc_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    parts = line.strip().split(None, 1)
                    if len(parts) == 2:
                        k, v = parts[0].lower(), parts[1].strip()
                        if k in ("server", "username", "reauth"):
                            conn[k] = v
        except Exception:
            pass

    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
                conn["name"] = meta.get("name", conn_id)
        except Exception:
            pass

    return conn


def _write_snxrc(conn_id: str, server: str, username: str, reauth: str = "yes") -> None:
    """Write a standard snxrc file (no custom fields, SNX-compatible)."""
    path = os.path.join(SNX_DIR, f"{conn_id}.snxrc")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"server {server}\n")
        f.write(f"username {username}\n")
        if reauth:
            f.write(f"reauth {reauth}\n")


def _write_meta(conn_id: str, name: str) -> None:
    path = os.path.join(SNX_DIR, f"{conn_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"name": name}, f)


def list_connections() -> list:
    ensure_dir()
    conns = []
    for path in sorted(glob.glob(os.path.join(SNX_DIR, "*.snxrc"))):
        conn_id = os.path.basename(path)[:-6]  # strip .snxrc
        conns.append(_load_connection(conn_id))
    return conns


# ── secret-tool helpers ───────────────────────────────────────────────────────

def get_password(conn_id: str) -> str:
    try:
        res = subprocess.run(
            ["secret-tool", "lookup", "snx-connection", conn_id],
            capture_output=True, text=True, timeout=3,
        )
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return ""


def store_password(conn_id: str, name: str, password: str) -> bool:
    if not password:
        return False
    try:
        p = subprocess.Popen(
            ["secret-tool", "store", f"--label=SNX VPN: {name}", "snx-connection", conn_id],
            stdin=subprocess.PIPE, text=True,
        )
        p.communicate(input=password + "\n", timeout=5)
        return p.returncode == 0
    except Exception:
        return False


def clear_password(conn_id: str) -> None:
    try:
        subprocess.run(
            ["secret-tool", "clear", "snx-connection", conn_id],
            capture_output=True, timeout=2,
        )
    except Exception:
        pass


# ── SNX process helpers ───────────────────────────────────────────────────────

def is_installed() -> bool:
    return subprocess.run(["which", "snx"], capture_output=True).returncode == 0


def is_running() -> bool:
    return subprocess.run(["pgrep", "-x", "snx"], capture_output=True).returncode == 0


def get_tunnel_ip() -> str:
    try:
        res = subprocess.run(
            ["ip", "-brief", "addr", "show", "tunsnx"],
            capture_output=True, text=True, timeout=2,
        )
        if res.returncode == 0 and res.stdout.strip():
            m = re.search(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", res.stdout)
            if m:
                return m.group(1)
    except Exception:
        pass
    try:
        res = subprocess.run(["ip", "-brief", "addr"], capture_output=True, text=True, timeout=2)
        for line in res.stdout.splitlines():
            if "tun" in line.lower() or "snx" in line.lower():
                m = re.search(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", line)
                if m:
                    return m.group(1)
    except Exception:
        pass
    return ""


# ── Active connection tracking ────────────────────────────────────────────────

def get_active_id() -> str:
    try:
        if os.path.exists(ACTIVE_FILE):
            with open(ACTIVE_FILE, "r") as f:
                return f.read().strip()
    except Exception:
        pass
    return ""


def set_active_id(conn_id: str) -> None:
    ensure_dir()
    try:
        with open(ACTIVE_FILE, "w") as f:
            f.write(conn_id)
    except Exception:
        pass


def clear_active_id() -> None:
    try:
        os.remove(ACTIVE_FILE)
    except Exception:
        pass


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_status() -> None:
    running = is_running()
    if not running:
        clear_active_id()
    tunnel_ip = get_tunnel_ip() if running else ""
    active_id = get_active_id() if running else ""
    print(json.dumps({
        "installed": is_installed(),
        "connected": running,
        "tunnelIp": tunnel_ip,
        "interface": "tunsnx" if running else "",
        "activeConnectionId": active_id,
        "connections": list_connections(),
    }))


def cmd_add(name: str, server: str, username: str, password: str = "") -> None:
    ensure_dir()
    base_id  = sanitize_id(name)
    conn_id  = unique_id(base_id)
    _write_snxrc(conn_id, server, username)
    _write_meta(conn_id, name)
    if password:
        store_password(conn_id, name, password)
    print(json.dumps({"success": True, "id": conn_id, "message": f"Connection '{name}' saved"}))


def cmd_edit(conn_id: str, name: str, server: str, username: str, password: str = "") -> None:
    ensure_dir()
    snxrc_path = os.path.join(SNX_DIR, f"{conn_id}.snxrc")
    if not os.path.exists(snxrc_path):
        print(json.dumps({"success": False, "error": f"Connection '{conn_id}' not found"}))
        sys.exit(1)
    _write_snxrc(conn_id, server, username)
    _write_meta(conn_id, name)
    if password:
        store_password(conn_id, name, password)
    print(json.dumps({"success": True, "id": conn_id, "message": f"Connection '{name}' updated"}))


def cmd_remove(conn_id: str) -> None:
    snxrc_path = os.path.join(SNX_DIR, f"{conn_id}.snxrc")
    meta_path  = os.path.join(SNX_DIR, f"{conn_id}.json")
    try:
        if os.path.exists(snxrc_path):
            os.remove(snxrc_path)
        if os.path.exists(meta_path):
            os.remove(meta_path)
        clear_password(conn_id)
        if get_active_id() == conn_id:
            clear_active_id()
        print(json.dumps({"success": True}))
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


def run_snx_pty(server: str, username: str, password: str, timeout: int = 25) -> tuple[bool, str]:
    """Run snx inside a fully-formed pseudo-terminal fork (controlling terminal)."""
    master_fd, slave_fd = pty.openpty()

    pid = os.fork()
    if pid == 0:
        # Child process: establish slave_fd as controlling terminal
        os.close(master_fd)
        os.setsid()
        
        try:
            fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)
        except Exception:
            pass

        # Duplicate slave to stdin, stdout, stderr
        os.dup2(slave_fd, 0)
        os.dup2(slave_fd, 1)
        os.dup2(slave_fd, 2)
        if slave_fd > 2:
            os.close(slave_fd)

        # Set environment variables for terminal compatibility
        env = os.environ.copy()
        env["TERM"] = "xterm-256color"

        os.execvpe("snx", ["snx", "-s", server, "-u", username], env)
        sys.exit(1)

    # Parent process
    os.close(slave_fd)

    # Make master_fd non-blocking
    flags = fcntl.fcntl(master_fd, fcntl.F_GETFL)
    fcntl.fcntl(master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

    output = []
    password_sent = False
    start_time = time.time()

    while time.time() - start_time < timeout:
        r, _, _ = select.select([master_fd], [], [], 0.3)
        if master_fd in r:
            try:
                data = os.read(master_fd, 1024)
                if not data:
                    break
                text = data.decode("utf-8", errors="ignore")
                output.append(text)
                combined = "".join(output).lower()

                # Check if snx is asking for password
                if not password_sent and ("password:" in combined or "senha:" in combined or "password :" in combined):
                    time.sleep(0.2)
                    os.write(master_fd, (password + "\n").encode("utf-8"))
                    password_sent = True

                # Check for certificate confirmation / yes-no prompts
                if "do you accept? [y/n]" in combined or "(y/n)" in combined or "accept this certificate?" in combined:
                    os.write(master_fd, b"y\n")

                # Check if connection succeeded
                if "connected" in combined and "failed" not in combined:
                    break

            except OSError:
                break

        # Check if child process exited
        pid_res, _ = os.waitpid(pid, os.WNOHANG)
        if pid_res != 0:
            # Drain remaining output
            try:
                while True:
                    data = os.read(master_fd, 1024)
                    if not data:
                        break
                    output.append(data.decode("utf-8", errors="ignore"))
            except OSError:
                pass
            break

    try:
        os.close(master_fd)
    except OSError:
        pass

    full_output = "".join(output)
    return is_running() or ("connected" in full_output.lower() and "failed" not in full_output.lower()), full_output


def cmd_connect(conn_id: str, password: str = "") -> None:
    conn = _load_connection(conn_id)
    if not conn["server"]:
        print(json.dumps({"success": False, "error": f"Connection '{conn_id}' not found"}))
        sys.exit(1)

    server   = conn["server"]
    username = conn["username"]
    name     = conn["name"]

    # Use saved password if none provided
    if not password:
        password = get_password(conn_id)

    if not password:
        print(json.dumps({
            "success": False,
            "needsPassword": True,
            "error": "Please enter password to connect",
        }))
        sys.exit(1)

    # Already connected?
    if is_running():
        print(json.dumps({
            "success": True,
            "alreadyConnected": True,
            "ip": get_tunnel_ip(),
            "activeConnectionId": get_active_id(),
            "message": "Already connected",
        }))
        return

    # Invoke snx using controlling PTY
    try:
        connected, combined = run_snx_pty(server, username, password, timeout=25)
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)

    time.sleep(1.0)
    connected = is_running() or ("connected" in combined.lower() and "failed" not in combined.lower())

    if connected:
        ip_match = re.search(r"Office Mode IP\s*:\s*([\d\.]+)", combined)
        ip = ip_match.group(1) if ip_match else get_tunnel_ip()
        to_match = re.search(r"Timeout\s*:\s*(.+)", combined)
        timeout_val = to_match.group(1).strip() if to_match else ""

        store_password(conn_id, name, password)
        set_active_id(conn_id)

        print(json.dumps({
            "success": True,
            "ip": ip,
            "timeout": timeout_val,
            "server": server,
            "username": username,
            "activeConnectionId": conn_id,
            "message": "Connected",
        }))
    else:
        err_msg = "Failed to connect via SNX"
        low = combined.lower()
        if any(x in low for x in ["wrong user", "authentication failed", "access denied", "incorrect"]):
            err_msg = "Wrong username/password or access denied"
        else:
            m = re.search(r"SNX:\s*(.+)", combined)
            if m:
                err_msg = m.group(1).strip()
            elif combined.strip():
                lines = [l.strip() for l in combined.splitlines() if l.strip()]
                if lines:
                    err_msg = lines[-1]

        print(json.dumps({"success": False, "error": err_msg}))
        sys.exit(1)


def cmd_disconnect() -> None:
    try:
        subprocess.run(["snx", "-d"], capture_output=True, timeout=5)
        for _ in range(15):
            if not is_running():
                break
            time.sleep(0.2)
        if is_running():
            subprocess.run(["pkill", "-9", "-x", "snx"], capture_output=True)
        clear_active_id()
        print(json.dumps({"success": True, "message": "Disconnected"}))
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 2:
        cmd_status()
        return

    action = sys.argv[1].lower()

    if action == "status":
        cmd_status()

    elif action == "add":
        # add <name> <server> <username> [password]
        if len(sys.argv) < 5:
            print(json.dumps({"success": False, "error": "Usage: add <name> <server> <username> [password]"}))
            sys.exit(1)
        pwd = sys.argv[5] if len(sys.argv) > 5 else ""
        cmd_add(sys.argv[2], sys.argv[3], sys.argv[4], pwd)

    elif action == "edit":
        # edit <id> <name> <server> <username> [password]
        if len(sys.argv) < 6:
            print(json.dumps({"success": False, "error": "Usage: edit <id> <name> <server> <username> [password]"}))
            sys.exit(1)
        pwd = sys.argv[6] if len(sys.argv) > 6 else ""
        cmd_edit(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], pwd)

    elif action == "remove":
        if len(sys.argv) < 3:
            print(json.dumps({"success": False, "error": "Usage: remove <id>"}))
            sys.exit(1)
        cmd_remove(sys.argv[2])

    elif action == "connect":
        if len(sys.argv) < 3:
            print(json.dumps({"success": False, "error": "Usage: connect <id> [password]"}))
            sys.exit(1)
        pwd = sys.argv[3] if len(sys.argv) > 3 else ""
        cmd_connect(sys.argv[2], pwd)

    elif action == "disconnect":
        cmd_disconnect()

    else:
        print(json.dumps({"error": f"Unknown action: {action}"}))
        sys.exit(2)


if __name__ == "__main__":
    main()
