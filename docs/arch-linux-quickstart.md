# Sidee on Arch Linux: from clone to a launcher tile

A single path through the project: get it onto the machine, start it, pair the
TV, add a tile, and know what each failure means. For every other distribution
and install method see the [Linux guide](linux.md); for firmware-specific
pairing limits see the [Toshiba compatibility notes](toshiba-compatibility.md).

Every step below is a normal user command. Nothing needs root except `pacman`
and the optional system-wide package install.

## 0. Prerequisites

```bash
sudo pacman -S --needed git python
python3 --version          # must be 3.9 or newer
```

You do not need `python-paho-mqtt`, `tkinter`, a desktop environment, or pip.
The launcher either finds an existing copy of the TV connection library or
downloads its own checksum-verified copy into the project folder. `iproute2`
(`ip`) is part of `base` on Arch and is what discovery uses to pick the right
interface.

You also need:

- the TV switched on and on the **same** network as the laptop,
- once-only internet access for the first launch,
- the port 8787 dashboard opened in a browser.

## 1. Clone

```bash
git clone https://github.com/kevin909867/Sidee-linux.git
cd Sidee-linux
```

`main` is the default branch and contains both the Linux support and the
firmware pairing changes. To confirm you have the newest code later:

```bash
git pull --ff-only
```

## 2. Start it

### Option A — run from the checkout (simplest, no install)

```bash
./start-linux.sh
```

First run prints `First launch: preparing the app.` and fetches `paho-mqtt`
2.1.0, verifies its SHA-256, and unpacks it into `.runtime/` (git-ignored). Later
runs reuse it and start immediately.

### Option B — install it with pacman

```bash
cd packaging/linux
makepkg -si
```

This pulls `python` and `python-paho-mqtt` from `extra`, installs the program to
`/usr/share/sidee`, the `sidee` launcher to `/usr/bin`, an application-menu
entry, and a systemd **user** unit. Build from the repository root first, since
the PKGBUILD packages the tree it sits in.

### Options that matter later

```bash
./start-linux.sh --headless           # no browser (server, SSH, second machine)
./start-linux.sh --port 8787          # pin the port (8787 is the default)
./start-linux.sh --prepare-only       # download the library, then exit
SIDEE_PYTHON=/usr/bin/python3.13 ./start-linux.sh   # force an interpreter
SIDEE_STATE_DIR=/tmp/try ./start-linux.sh           # scratch state, real pairing untouched
./start-linux.sh -v                                   # diagnostics (silent by default)
```

## 3. Open the dashboard

The launcher prints two links and opens the first one for you:

```
Sidee (this computer): http://127.0.0.1:8787/?key=<access key>
Sidee (from your phone, same network): http://192.168.x.x:8787/?key=<access key>
```

The `key=` part is the access token. Opening the dashboard **without** it returns
`403` by design. Keep the link private, and treat the phone link the same way —
anyone on your Wi-Fi holding it can drive the TV. The dashboard also shows a QR
code for the phone.

Leave the launcher running while you use the dashboard. `Ctrl+C` stops it.

## 4. Pair the TV

1. **Find TV** — Sidee broadcasts an SSDP search and also listens for TVs that
   only announce themselves, for about four seconds. Your TV should appear with
   its address and model.
2. If nothing appears, type the TV's IP shown in **TV Settings → Network** and use
   **Check TV IP**. That verifies the device description and that TCP 36669 is
   reachable before pairing is offered.
3. **Request code** — the TV shows a four-digit PIN.
4. Type it into **TV PIN** and press **Confirm code**. A PIN you did not approve
   on the TV cannot complete pairing.

When it works, the dashboard reports `Paired` and the launcher logs the profile
that was accepted, for example:

```
auth: pairing connection static: rc=0
```

On firmware where the first profile is accepted but ignored, you will instead
see the fallback doing its job — this is normal, wait for the PIN:

```
auth: no PIN from profile static: trying the next one
auth: pairing connection middle: rc=0
```

## 5. Add a launcher tile

The dashboard offers three tiles: **Install Nuvio**, **Install Stremio**, and
**Install Jellyfin**. Jellyfin additionally asks for the **Server address** of
your own media server (`192.168.1.20:8096`).

The TV is asked to register the tile and then re-read to confirm it. The result
is explicit:

- `REGISTERED` — the TV returned the tile with the expected app ID and URL.
- `NOT confirmed by the TV` — the TV accepted the request but did not register it.
  That is a firmware limitation, not a credential problem.

Tiles stay in the launcher across TV restarts and after Sidee is closed. The tile
opens a web app, so whatever it points at (your Jellyfin server, a streaming
site) still needs to be reachable from the TV itself.

### If the tile does not appear

Network tile registration is not a VIDAA feature. No public project installs a
tile over the TV's control interface, and older firmware (U6-era, `V0000.06.x`)
silently ignores the request — pairing works, `NOT confirmed by the TV` comes back,
and Home stays unchanged. That is the firmware, not a bad PIN.

The documented route on those sets is the TV's own browser:

1. On the TV, open the **Browser** app.
2. Type `hisense://debug` and confirm.
3. Enter the tile's **name** and **address** (Sidee prints both, and the dashboard
   shows them in the install message).
4. Choose **Install**.

`hisense://debug` is the correct address — lowercase, no trailing slash. **Not
every build ships that page.** If the Browser answers *"please enter a valid
address"*, that firmware has no debug installer, and there is no alternate
spelling, bookmark or `http://` equivalent that opens it: the handler is simply
absent. In that case the address can still be **bookmarked** in the Browser, which
works immediately but lives in the Browser's bookmarks rather than on Home.

For Stremio there is a better option than any of this: **Stremio Lite** is
published in the TV's own VIDAA app store, so it installs without a tile, a
bookmark or a debug page.

Values for the built-in tiles:

| Tile | Name | Address |
| --- | --- | --- |
| Nuvio | `Nuvio` | `https://nuviotvsmart.vercel.app/vidaa.html` |
| Stremio | `Stremio` | `https://noobygains.github.io/stremio-vidaa-tv/?install_source=sidee` |
| Jellyfin | `Jellyfin` | `http://YOUR_SERVER:8096/web/index.html` |

The tile lands at the end of **My Apps**; restart the TV if it does not appear.
This is a documented workaround reported by other projects, not something Sidee
can verify on your model.

## 6. Command line instead of the dashboard

The same operations without a browser:

```bash
./start-linux.sh discover                       # list TVs: host, name, is it VIDAA
./start-linux.sh pair 192.168.1.50              # prompts for the PIN
./start-linux.sh install jellyfin --server 192.168.1.20:8096
./start-linux.sh list                           # tiles the TV reports
./start-linux.sh launch jellyfin                # open it on the TV
./start-linux.sh refresh                        # renew stored tokens
```

With the installed package, replace `./start-linux.sh` with `sidee`. Saved
pairings live in `~/.sidee/session.json` (mode `600`) and survive updates, so you
pair once per TV.

## 7. Verify the install without a TV

```bash
./start-linux.sh --self-test      # resources, bundled MQTT client, TLS, QR code
```

Exit status 0 means the runtime is intact; it never contacts a TV.

## 8. Background service (optional)

Only if you installed the package (Option B):

```bash
systemctl --user daemon-reload
systemctl --user enable --now sidee
systemctl --user status sidee
journalctl --user -u sidee -n 50
```

The unit runs `sidee --headless`. The dashboard access key stays out of the
journal; read it from `~/.local/state/sidee/runtime/dashboard.json`. A second
`sidee` launch reopens the dashboard that is already running rather than starting
another one.

## 9. When it does not work

| What you see | What it means | What to do |
| --- | --- | --- |
| `403` on the dashboard | Missing or wrong `key=` | Use the full printed URL |
| `Find TV` finds nothing | SSDP blocked, VPN, or guest Wi-Fi | Enter the IP manually; disable the VPN; use the main SSID |
| `Port 36669 answered, so this looks like your TV, but its device description could not be confirmed` + `Tried …` | The control port answered; identity could not be read from any descriptor endpoint. Check TV IP **still accepts it** so you can pair, but the device stays unverified | Pair anyway — the PIN is the authorization. Keep the `Tried …` list for a report |
| `No VIDAA TV description or port 36669 response at that IP` | Host unreachable or port closed | Check the address, the TV subnet, and any firewall |
| `... rc=5` for every profile | Broker refused all four credential profiles | Firmware not supported; see the compatibility notes |
| `no PIN from profile X: trying the next one` | Connected but ignored — the fallback working | Wait; the next profile is being tried |
| `the TV did not display the PIN (profiles tried: static, modern, middle, remotenow)` | All profiles connected or refused, none produced a PIN | Report the line with your firmware string |
| `NOT confirmed by the TV` | Auth fine, tile registration unsupported | Firmware limitation |
| `Sidee is already preparing this folder` | A real second launch holds the lock | Wait for it, or close the other window |
| `ModuleNotFoundError: No module named 'paho'` | Ran `sidee.py` directly instead of the launcher | Use `./start-linux.sh`, or `sudo pacman -S python-paho-mqtt` |
| Browser does not open | No `xdg-open` / headless session | Open the printed URL; use `--headless` over SSH |

### Getting diagnostics

Nothing is printed beyond the dashboard links unless you ask for it. `-v`
(`--verbose`) turns on tagged diagnostics for the whole run: the interfaces and
search targets used for discovery, every descriptor URL with its status code,
the auth profile outcomes, and the install result.

```bash
./start-linux.sh -v
# or, from the installed package:
sidee -v

[06:35:59] discovery: interfaces: 192.168.1.0/192.168.1.255
[06:35:59] discovery: search targets: 192.168.1.255, 255.255.255.255, 239.255.255.250
[06:36:03] discovery: 0 SSDP repl(y/ies) in 4s
[06:36:15] tv: descriptor http://192.168.1.50:18400/description.xml: HTTP 404
[06:36:18] tv: descriptor https://192.168.1.50:38400/description.xml: HTTP 200
[06:36:18] tv: descriptor https://192.168.1.50:38400/description.xml: VIDAA (Living room)
```

Run it in a terminal (`Ctrl+C` to stop) so the lines stay visible; logs contain no
PIN, no tokens and no dashboard key.

### When the IP check cannot identify the TV

When an address is entered by hand, Sidee tries each descriptor port with plain
HTTP **and** the self-signed TLS those sets use, with a 10-second total budget. A
port that swallows plain HTTP instead of refusing it (a timeout rather than
`ConnectionRefusedError`) usually means the descriptor is served over TLS there:

```
http://TV_IP:18400/MediaServer/rendererdevicedesc.xml
https://TV_IP:18400/MediaServer/rendererdevicedesc.xml
http://TV_IP:18400/description.xml
https://TV_IP:18400/description.xml
... the same four for port 38400, then for port 80
```

If none of them answer, Sidee reports the attempts and continues anyway when port
36669 answered: the broker is what the control protocol needs, and the PIN on the
TV is the real authorization.

Check them from a shell yourself — whichever answers tells you what the TV serves:

```bash
for u in http://TV_IP:18400/description.xml http://TV_IP:38400/description.xml \
         https://TV_IP:38400/description.xml; do
  echo "== $u"; curl -k -s -m 3 -o /dev/null -w '%{http_code}\n' "$u"
done
```

Any `200` means the TV does publish a descriptor; include that URL and your
firmware string when reporting the problem. All `000` means the TV exposes only
the control port, which Sidee currently refuses to pair with.

Discovery needs only outbound traffic: UDP 1900 to `239.255.255.250` and each
interface's broadcast address, plus TCP 36669 to the TV. With `firewalld` or
`ufw` installed, allow those outbound; there is nothing to open inbound.

## 10. Update and remove

```bash
git pull --ff-only            # Option A: then run ./start-linux.sh again
cd packaging/linux && makepkg -si    # Option B
```

```bash
sudo pacman -Rns sidee        # remove the package
rm -rf ~/.sidee               # forget the TV (optional; deletes the pairing)
```

For the uninstalled checkout, delete the folder. `.runtime/` and `.venv/`, if you
made one, are both disposable and git-ignored.
