# ptyxisDNS

`ptyxisDNS` opens a new [Ptyxis](https://gitlab.gnome.org/chergert/ptyxis) terminal window with a per-process DNS and HTTP proxy environment. It is intended for running Codex CLI or other command-line tools through the GeoHide EU hosts list without changing system DNS, `/etc/hosts`, or network routes.

The project uses a local HTTP/CONNECT relay. HTTPS connections are tunneled unchanged, so certificate validation remains with the client. A Bubblewrap mount namespace supplies a temporary hosts file containing the downloaded GeoHide routes and optional local overrides.

## Features

- Start a dedicated Ptyxis window, or run commands in the current terminal.
- Download and refresh the GeoHide EU hosts list on demand.
- Apply proxy environment variables to programs that support them.
- Optionally bind relay connections to a network interface.
- Run anonymous connectivity diagnostics or an authenticated Codex request.
- Keep the system resolver configuration and hosts file unchanged.

## Requirements

- Linux with Bash and Python 3
- [Ptyxis](https://gitlab.gnome.org/chergert/ptyxis) for `ptyxisDNS`
- Bubblewrap (`bwrap`), with user and mount namespaces available
- `curl` for updating the host list and running diagnostics
- Codex CLI for `--test-codex` and the Codex window adapter

## Install

Clone the repository and make its commands available in your `PATH`. For example:

```bash
git clone https://github.com/OWNER/REPOSITORY.git
cd REPOSITORY
mkdir -p "$HOME/.local/bin"
ln -s "$PWD/ptyxisDNS" "$HOME/.local/bin/ptyxisDNS"
ln -s "$PWD/runDNS" "$HOME/.local/bin/runDNS"
```

Ensure `~/.local/bin` is in `PATH`. The first run downloads the GeoHide EU list into `redirects.hosts`.

## Usage

Open a new Ptyxis window with an interactive shell:

```bash
ptyxisDNS
```

Run a command in the current terminal:

```bash
runDNS -- curl https://example.com
runDNS -- codex
```

Update the GeoHide list:

```bash
runDNS --update
```

Run anonymous connectivity checks:

```bash
runDNS --check
runDNS --diagnose
```

These checks do not verify an authenticated Codex session. To make a real, small Codex request with the currently configured account:

```bash
runDNS --test-codex
```

To bind the relay's outbound connections to a specific interface (replace `INTERFACE` with an interface on your machine):

```bash
ptyxisDNS --interface INTERFACE
runDNS --interface INTERFACE -- codex
runDNS --check-direct INTERFACE
runDNS --diagnose-direct INTERFACE
```

Run `ptyxisDNS --help` or `runDNS --help` for command syntax.

## Host overrides

Create an `overrides.hosts` file in the repository directory to add or replace entries. Use standard hosts-file syntax:

```text
203.0.113.10 example.test
```

Overrides take precedence over downloaded entries and are retained when the list is updated. The example address above is reserved for documentation; replace it with an address appropriate for your setup.

## How it works

`runDNS` builds a temporary hosts file from the system hosts file, the downloaded GeoHide list, and local overrides. It starts Bubblewrap with temporary read-only replacements for `/etc/hosts` and `/etc/nsswitch.conf`, then launches `relay.py`. The relay listens on localhost at a temporary port and passes HTTP requests or HTTPS CONNECT tunnels to their destinations. Child processes inherit the relay's proxy settings. Temporary files and the relay are cleaned up when the command exits.

The optional `--interface` setting binds the relay's outbound sockets to the selected interface. It does not affect applications that ignore proxy variables.

## Limitations

This is a hosts override plus an HTTP proxy, not a system-wide VPN. Applications using their own DNS-over-HTTPS, direct IP connections, UDP, or a separately running background service may bypass it. New Ptyxis tabs created through the desktop UI do not automatically inherit this setup; use `ptyxisDNS` to open a configured window. Detached processes cannot use the window-local relay after the parent command exits.

The Codex adapter adds `--no-daemon` to keep Codex requests in the configured process environment. Explicit remote mode and commands that require a shared daemon may not work in that mode.

## Local files

`redirects.hosts`, `overrides.hosts`, and `verification.txt` are machine-specific or generated local files and are intentionally excluded from version control. `redirects.hosts` is recreated by `runDNS --update`; `overrides.hosts` is optional.
