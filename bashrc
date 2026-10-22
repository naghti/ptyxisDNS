# Applied only to an interactive bash started by runDNS.
if [ -f "$HOME/.bashrc" ]; then
    . "$HOME/.bashrc"
fi
# User startup files may prepend ~/.local/bin again; restore our scoped adapter.
export PATH="$TERMINAL_DNS_BIN:$PATH"
hash -r
