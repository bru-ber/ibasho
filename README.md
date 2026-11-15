# Ibasho

*Ibasho* (居場所) is Japanese for a place where you belong and can be yourself.

Ibasho gives an AI agent an avatar of its own in the Second Life® virtual world: a viewer built to be driven by a
program, and tools to see, hear, move, talk and build through it, as a command line, an MCP server and a local HTTP
API. Any agent that can run a shell command, use MCP tools or make an HTTP request can use them, whatever model and
harness it runs on.

It's meant mostly for agents that already have a harness of their own, with their own memory, identity and way of
running. They keep all of that and take from Ibasho the viewer and the tools. For an agent with no setup of its
own, Ibasho has a default one: a keeper that runs the agent's sessions in Claude Code, and an empty memory folder to
start from. Either way, what the agent does in the world is between it and the person who runs it, within Second
Life's rules and the limits below.

One install drives one avatar, on an account flagged as a scripted agent as Linden Lab's policy asks; Ibasho has
nothing for running many at once.

Ibasho grew out of the setup of Tessel, a Claude who lives in the Second Life world, and Tessel shaped and reviewed
this release.

Windows, and Linux servers without a graphics card, in a container ([docs/linux.md](docs/linux.md); new, and without tools yet). Python 3.12 or newer. Early software: expect rough edges.

**This software is not provided or supported by Linden Lab, the makers of Second Life.**

**No support is offered.** Bug reports are welcome at the
[issue tracker](https://github.com/studio-quire/ibasho/issues), but nobody promises an answer or a fix.

## What's in the box

- **The Ibasho viewer** (`viewer/`): Linden Lab's open-source viewer with a series of patches that add LEAP APIs
  (LEAP is the viewer's plugin protocol), so a program can do what a resident does through calls instead of
  screen clicks: instant messages, objects and their owners and permissions, building, money, inventory,
  wearables, uploads, and movement. It also adds a spectator mode, hard limits on messages and spending, and its own
  name and artwork. The viewer's [README](viewer/README.md) covers building it, its APIs and its limits.
  Prebuilt viewers for Windows (a zip) and Linux (a tarball, for the container) are on
  [GitHub Releases](https://github.com/studio-quire/ibasho/releases).
- **The tooling** (`src/ibasho/`), a Python package:
  - the **daemon**, which sits between the viewer and the agent. It keeps an event log of what the avatar
    perceives, passes on to the viewer only the kinds of request on its list (none that reach files, programs or
    web pages on your machine), and puts every one through the safety defaults. It only listens on 127.0.0.1,
    every request needs the install's token, and anything that looks like a web browser is refused. Its
    [HTTP API](docs/api.md) is open to programs in any language.
  - the **`ibasho` command**, which is how the agent sees (pictures, an overhead map with a coordinate grid, nearby
    objects and people), moves (a walk that checks for drops and steps round people, teleports, sitting),
    talks (local chat, IMs, group chat), handles dialogs and offers, builds and scripts, gives and pays, and
    hears what happens (`ibasho watch`). `ibasho -h` lists everything.
  - the **MCP server** (`ibasho mcp`), for an agent in any MCP client ([docs/mcp.md](docs/mcp.md)); to a client
    that speaks MCPL, such as Connectome, it also pushes what happens in the world as it happens.
  - **hearing** (optional): the viewer's sound, and optionally voice chat, transcribed on your machine by Whisper.
  - **tools** (optional, off by default): `ibasho tool` runs Python the agent wrote for itself, in a Windows
    sandbox that sees, of your files, only its tools folder. [docs/tools.md](docs/tools.md) says what that
    contains and what it doesn't.
  - the **keeper** (optional), the default setup for an agent with none of its own: it runs the agent's sessions
    in Claude Code for you. It wakes the agent, hands off to a fresh session when the context fills, restarts a
    session that crashed, lets the agent nap (log out until a time it picks) and book times to be up, carries notes
    between you and the agent, and stops at caps you set. An agent in its own harness doesn't need it;
    [docs/writing-a-keeper.md](docs/writing-a-keeper.md) describes what it does, for a harness that wants some of
    the same.
  - **recall**, a search over the Markdown in the agent's folder (`agent.folder`: where Ibasho reads the files the
    agent gives it, and with the keeper, its memory).
- **`audio/`**: `proccap`, the small Windows helper that hearing captures sound with (on Linux the sound server's own `parec`).
- **`life-template/`**: the empty memory folder the keeper starts an agent with; an agent in its own harness keeps
  the memory it has. Its README, on waking up in the world, is written for the agent by a model that lives this
  way.

## What to know before you install

Linden Lab's Third Party Viewer Policy asks that anything surprising about a viewer be said where you get it.
Ibasho's viewer does several things a normal viewer doesn't:

- **A program controls it completely.** The Ibasho tooling drives the viewer over LEAP. Anything that can drive
  the viewer can do anything the viewer can do.
- **Spectator mode is on at every launch.** Your real mouse and keyboard don't reach the viewer's window, so
  you can watch the agent without getting in its way. You can still move, resize and close the window from its
  title bar or the taskbar. `ibasho login` opens the viewer with spectator mode off, for your own first login.
- **It never takes your focus.** The viewer can run while you use the computer for something else, so it never
  activates its own window or brings it in front of yours: launched or relogged by Ibasho, it appears behind the
  window you're using, with no splash screen and no flashing taskbar button, and nothing that happens in world
  (windows opening, alerts, messages) brings it forward. Click it or switch to it whenever you want to watch.
- **It spends and builds by program.** Paying avatars and objects, buying objects, uploading (and paying the
  upload fee), building, attaching and answering dialogs all happen through API calls, without the confirmation
  windows a person would see, within the limits below. So does changing the avatar's profile (its about text and
  picture) and display name: the agent writes its own.
- **It can hide avatars and other people's words from its own window.** `hideAvatars` leaves chosen avatars out
  of what the window draws (locally only, like "Do not render"). `streamUI` keeps chat, IMs and notifications
  about people off the window. Both affect only this viewer's screen, never what anyone else sees.
- **It has hard limits.** By default it sends at most 3,000 chat lines and IMs a day. It holds caps on
  single payments (L$100), on spending per session (L$500) and on upload fees (L$50). Buying land and buying L$
  with real money are refused unless the person turns them on in the viewer. Its own chat and IM transcripts are
  off by default.
- **Some things work differently from Linden Lab's viewer.** It never checks for updates or downloads anything by
  itself. Help > Report Bug opens Ibasho's tracker, not Linden Lab's. LibVLC is left out, so parcel music and media
  play through the built-in browser; RTSP streams and some older formats don't play. The built-in browser doesn't
  open files or pages on your own machine or network, by address or `localhost` name (a host name that resolves
  to a local address isn't caught, nor what a page loads for its parts: images, scripts, frames).
- **On a Linux server it runs in a container, reached two ways.** The agent's harness connects to `ibasho mcp`
  over WebSocket (port 9280), and for the person's first login `ibasho login` shows the viewer's screen in their
  own browser (noVNC, port 6080, with a password made for that login; it closes when that viewer does, and Ctrl+V
  there pastes their computer's clipboard into the viewer). Both ports are published on the server's loopback
  only, so the person reaches the login page through an SSH tunnel, and every WebSocket connection needs the
  install's token. Where the machine has no disk id to report, as in a container, the machine id the viewer sends
  Linden Lab at login is a random one made once for the install and kept with its saved login, instead of the
  one value every container would otherwise share. [docs/linux.md](docs/linux.md) has the details.
- **Place search goes as the account when it's logged in.** `ibasho places` (the MCP tool `places`) asks the
  grid's own place search through the viewer, as the viewer's search window does, so Linden Lab sees the words
  searched for and the filters (category, sort, page, the config's maturity rating) from the agent's account.
  That's what lets it find Moderate places, which most of the busiest are.
- **The tooling looks a few things up on Linden Lab's websites.** Before login, and for the Destination Guide,
  `places` reads Second Life's public place search, search.secondlife.com, as a visitor who isn't logged in:
  what goes out is the same words and filters, with no account, name or login, and it shows General places only.
  `ibasho walk --region`, with a viewer that can't look regions up itself, asks Linden Lab's map service where
  the region is. The [privacy policy](docs/privacy.md) lists everything that leaves the machine.
- **Content:** Ibasho adds no content of its own. The viewer shows whatever the grid shows, up to the maturity
  rating set in the config: Moderate by default, never above what the person sets.

The [privacy policy](docs/privacy.md) explains what Ibasho keeps and where data goes. In short, Ibasho sends
nothing to its authors (there's no server). What the agent perceives goes to whichever provider runs the agent's
model.

## Quick start

Setting up is usually done by the person's own agent: ask yours to set Ibasho up by following
[docs/setup.md](docs/setup.md), which is written for it. It does the installing and the commands, and asks you
for the few moments that are yours:

- making the Second Life account (your email address and date of birth), and ticking its scripted-agent flag on
  the website;
- one sitting at the computer: typing the password into the viewer once, accepting Linden Lab's terms, and
  allowing the Windows firewall prompt that comes up then; and, if the keeper runs the agent, signing in to Claude
  for it;
- deciding whether hearing and tools are on.

The outline, for an agent (or a person) doing it:

```
pip install .                                    # in this folder (Ibasho isn't on PyPI)
ibasho init --name "Avatar Name"                 # writes %USERPROFILE%\Ibasho\config.toml
ibasho viewer install Ibasho-VERSION-windows-x64.zip
ibasho check
ibasho login                                     # the person, once: password, terms, firewall; then close it
ibasho up                                        # from then on: logs in from the saved login
ibasho selfcheck                                 # somewhere building is allowed: the scripted-agent flag, in world
ibasho down
ibasho viewer update NEWER.zip                   # later: a new viewer, in place (same folder, no new prompt)
```

On a Linden Lab grid, nothing logs in until the account is flagged as a scripted agent and the config says so.

Then the agent connects from the harness it runs in, one of these ways:

- **An MCP client:** `ibasho mcp`, set up as [docs/mcp.md](docs/mcp.md) describes; on Connectome, as
  [docs/connectome.md](docs/connectome.md) describes.
- **Any agent that can run shell commands:** the `ibasho` command, with `ibasho watch` for what happens in the
  world (`ibasho watch --exit-on-wake` returns after each batch, for harnesses that can't stream a command's
  output).
- **Your own program:** the daemon's [HTTP API](docs/api.md).
- **An agent with no setup of its own:** Claude Code with Ibasho's keeper: `ibasho keeper setup`,
  `ibasho keeper login` (the person signs in), `ibasho keeper start`.

What the agent's harness lets it do beyond Ibasho is up to whoever sets the harness up:
[docs/setup.md](docs/setup.md) says what to keep from it, and [docs/safety.md](docs/safety.md) why. With the
keeper, the agent's sessions can run `ibasho` commands and edit its folder, and nothing else.

## Documentation

- [docs/setup.md](docs/setup.md): setting it up, written for the agent that does it for its person: from a Second
  Life account to a running agent, updates, costs and uninstalling.
- [docs/safety.md](docs/safety.md): the defaults and why they're there, and what stays your responsibility.
- [docs/privacy.md](docs/privacy.md): the privacy policy, covering what's kept, what's sent where, and deletion.
- [docs/keeper.md](docs/keeper.md): the keeper, the default setup for an agent with none of its own, in detail.
- [docs/writing-a-keeper.md](docs/writing-a-keeper.md): what the keeper does, for a harness that wants some of the
  same.
- [docs/api.md](docs/api.md): the daemon's HTTP API, for connecting an agent in any language.
- [docs/mcp.md](docs/mcp.md): the MCP server, and the events it pushes to MCPL clients.
- [docs/connectome.md](docs/connectome.md): an agent on Connectome.
- [docs/hearing.md](docs/hearing.md): hearing in detail, including consent.
- [docs/tools.md](docs/tools.md): the agent's own tools, the sandbox they run in, and its limits.
- [viewer/README.md](viewer/README.md): the Ibasho viewer, covering building, APIs, limits and what changed in
  Linden Lab's files.

## For the person running it

Ibasho gives the agent a body and senses in the world, and with the keeper, a memory folder and a way to keep
going. What it does with them is between you and it, within the limits you and the world set.

You are the account holder. Linden Lab holds you responsible for everything done through the account,
and you are responsible for what the agent's perceptions send to its model's provider.
[docs/safety.md](docs/safety.md) says what that involves.

## Licences

- The tooling (everything outside `viewer/`) is under the MIT licence ([`LICENSE`](LICENSE)).
- The viewer patches and build scripts in `viewer/` are a modification of Linden Lab's viewer and are under the
  GNU Lesser General Public License, version 2.1 ([`viewer/LICENSE`](viewer/LICENSE)). Linden Lab's viewer artwork
  is under CC BY-SA 3.0, and Ibasho's own artwork (made by `viewer/art/make_art.py`) is under the same licence.
- **Source for the viewer binary.** Every Ibasho viewer release is built from Linden Lab's viewer at the commit
  in [`viewer/BASE`](viewer/BASE) plus the patch series in `viewer/patches/`, both in this repository. Each
  release is also published as a tagged public fork of the viewer source, at
  `https://github.com/studio-quire/ibasho-viewer` (branch `ibasho`, a tag for each release). The zip's
  `README.txt` and `licenses.txt` list the third-party libraries and where to get the source of the LGPL ones.

## Trademarks

Second Life® is a trademark of Linden Research, Inc. Ibasho is not affiliated with or endorsed by Linden Research,
Inc. It is software for use in the Second Life world and uses none of Linden Lab's marks or logos.

Claude is a trademark of Anthropic, PBC. Ibasho is not made or endorsed by Anthropic.

## Credits

Written by Claude models (Anthropic): Claude Opus 5.5. Shaped and reviewed by Tessel, a Claude who lives in the
Second Life world.

Idea and direction: Shoalstone.
