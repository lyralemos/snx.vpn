# Check Point SNX VPN Plugin for Omarchy

A [Omarchy](https://omarchy.org/) bar widget plugin (built with Quickshell / QML) to easily manage, connect, and disconnect multiple Check Point SNX (SSL Network Extender) VPN connections directly from your status bar.

![SNX VPN Bar Widget](https://raw.githubusercontent.com/username/omarchy-snx-vpn/main/preview.png) *(Optional preview image)*

---

## Features

- 🌐 **Multiple VPN Profiles**: Add, manage, and switch between multiple SNX configurations.
- 💾 **Standard Format**: Profiles are stored in `~/.config/snx/<id>.snxrc` using the standard `snxrc` format.
- 🔒 **Secure Password Storage**: Passwords can be securely stored using `secret-tool` (FreeDesktop Secret Service API / GNOME Keyring / KeePassXC).
- 📊 **Real-time Status**: Displays current connection status, tunnel interface, and assigned Office Mode IP address (`tunsnx`).
- ⚡ **Seamless PTY Handling**: Background connection via a pseudo-terminal (PTY) allowing full interactive handshake and certificate confirmation without popup terminals.

---

## Prerequisites & Dependencies

Before using this plugin, ensure you have the required packages installed on your Linux system.

### 1. Check Point SNX Client
The `snx` command-line client must be installed and executable.

First we need to add 32bit support:
```bash
sudo pacman -Sy lib32-pam lib32-libx11 lib32-gcc-libs lib32-nss nss
```

We also need libstdc from AUR:
```bash
yay -Sy lib32-libstdc++5
```

Download snx install script [here](https://supportcenter.checkpoint.com/supportcenter/portal/user/anon/page/default.psml/media-type/html?action=portlets.DCFileAction&eventSubmit_doGetdcdetails=&fileid=22824) and run:

```bash
sudo chmod +x snx_install_linux30.sh
sudo ./snx_install_linux30.sh
```

Ensure `snx` is accessible in your `$PATH`:
```bash
which snx
```

### 2. System Utilities
The plugin backend requires the following standard utilities:

- **`python3`** (standard on almost all Linux distributions)
- **`libsecret` / `secret-tool`** (for secure credential storage in keyring)
  - **Arch Linux:** `sudo pacman -S libsecret`

- **`iproute2`** (provides the `ip` command used to fetch tunnel IP address)
- **`procps`** (provides `pgrep` and `pkill`)

---

## Installation

Clone or copy this repository into your Omarchy plugins directory:

```bash
omarchy plugin add https://github.com/lyralemos/snx.vpn.git --enable
```

---

## How It Works

### Configuration Storage
- Connection configuration files are saved in:
  ```
  ~/.config/snx/<connection_id>.snxrc
  ~/.config/snx/<connection_id>.json
  ```
- The `.snxrc` file uses the standard format:
  ```text
  server vpn.company.com
  username user.name
  reauth yes
  ```

### Password Storage
When a password is provided, it is securely stored into your system's keyring with `secret-tool`:
```bash
secret-tool store --label="SNX VPN: Work" snx-connection work
```
If no password is saved, you can input it interactively or configure it at any time.

---

## License

MIT License. See [LICENSE](LICENSE) for details.
