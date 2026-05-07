# betr_randr

`betr_randr` is a small display-mode switcher for i3/X11, backed by `xrandr`.
It is intended to feel closer to the Windows display function key / `Win+P`
workflow, with an advanced layout editor available when the simple modes are not
enough.

## Requirements

- Python 3.10+
- `xrandr`
- `rofi`
- i3 or another X11 window manager
- GTK 3 Python bindings and Cairo for the transparent overlay (`python3-gi`,
  `python3-cairo`, and GTK 3 on Debian/Ubuntu)
- Optional: `picom` or `xcompmgr` for a fully transparent overlay background

To check the local environment:

```sh
./bin/betr-randr --check-deps
```

## Run

```sh
./bin/betr-randr
```

The default command opens Rofi first. Choose `advanced placement overlay` to
open the keyboard-driven overlay, or choose a monitor row for the menu-only
workflow.

The top-level Rofi menu includes these display modes:

- `internal only`: use the internal/current primary display
- `duplicate`: mirror the internal/current primary display to the first external
  display
- `extend`: place the first external display to the right
- `external only`: use the first external display

For a function-key style binding, use the project menu directly:

```sh
./bin/betr-randr --project menu
```

You can also apply a mode directly:

```sh
./bin/betr-randr --project extend
./bin/betr-randr --project duplicate
./bin/betr-randr --project internal-only
./bin/betr-randr --project external-only
```

To skip Rofi and open the overlay directly:

```sh
./bin/betr-randr --gui
```

To work on the interface without plugging in another monitor, add a simulated
connected output:

```sh
./bin/betr-randr --gui --simulate-monitor --dry-run
```

You can give the fake output a name and mode:

```sh
./bin/betr-randr --gui --simulate-monitor SIM-1:2560x1440 --dry-run
```

To start a simulated monitor already attached, add `+X+Y` geometry:

```sh
./bin/betr-randr --gui --simulate-monitor SIM-1:1920x1080+1920+0 --dry-run
```

Or attach it relative to the current monitor:

```sh
./bin/betr-randr --gui --dry-run \
  --simulate-monitor SIM-ATTACHED:1920x1080@right \
  --simulate-monitor SIM-AVAILABLE:2560x1440
```

To simulate four monitors with one already attached and three available:

```sh
./bin/betr-randr --gui --dry-run --simulate-layout four-one-attached
```

Simulated monitors are only for interaction testing. In a normal apply, fake
outputs are skipped so the script does not call `xrandr --output SIM-1`.
With `--dry-run`, the generated commands are printed.

The menu lets you:

- open a transparent full-screen overlay for keyboard-only monitor placement
- enable a connected output
- disable an active output
- view the current monitor layout, resolution, coordinates, and rotation in the
  Rofi message area
- use a wider Rofi panel with monospace layout preview and styled rows
- move an active output left, right, above, below, or mirrored with another
  active output
- snap monitor edges while moving: top, center, bottom, left, or right alignment
- choose a resolution
- rotate an output: normal, left, right, or inverted
- mark an output as primary

The overlay opens a transparent window on each active monitor so it remains
visible across the attached layout in i3. The current monitor gets the focused
control window; the other monitors use unmanaged popup overlays so i3 does not
move them back to the launching output. Each attached monitor window shows that
monitor from its own perspective, including neighboring attached monitors in
their relative positions; the selected current display also shows the monitor
being attached or moved at the selected edge/corner. It lets you:

- attach an available connected monitor at its largest supported resolution
- see every available connected monitor as a scaled thumbnail centered along
  the bottom, even when there is only one other monitor
- see the primary monitor marked with a `PRIMARY` badge, and a `P` badge in
  the thumbnail row
- see each monitor's rotation in the preview details, with a badge when it is
  rotated away from normal
- see disconnected XRandR outputs with reported positions as grey disconnected
  placeholders instead of forgetting that the output exists
- select a disconnected placeholder only to detach it from the pending layout
- see thumbnails relative to each overlay monitor, so the current monitor for
  that window is omitted and neighboring monitors remain selectable/visible
- see placed monitors in the thumbnail row with a distinct color treatment
- keep the thumbnail row scaled to fit inside the current overlay window, using
  each monitor's largest reported mode for relative size
- click a thumbnail, press its number, or press `n`/`Tab` to choose the attach
  candidate
- rotate the selected candidate monitor before attaching or while moving it
- use `Shift`+arrow keys to switch the current display to another attached
  monitor
- place a selected unattached monitor on the current display edge when there is
  an open aligned slot; only fully occupied edges place beyond another monitor
- normalize final positions before applying, so left/above placements do not
  create negative XRandR coordinates
- move an already-attached monitor to the selected edge/corner before applying
- keep the current display at a stable visual size while changing placement
- cycle the selected border around the current display
- apply the generated `xrandr` commands when the layout looks right
- close automatically when you click outside it

Overlay controls:

- `a`: attach or move the candidate monitor to the selected edge/corner
- `1`-`9`: select the numbered candidate monitor
- `n` or `Tab`: cycle the candidate monitor
- `t`: cycle the selected border
- `r`: rotate the candidate monitor
- Arrow keys: choose a border. Press the same arrow again to toggle that
  border's alignment end.
- `Shift` + Arrow keys: switch the current display to an attached monitor in
  that direction
- `p`: make the current perspective monitor primary, regardless of which
  candidate monitor is selected for placement.
- `d`: detach the candidate monitor
- `Enter`: apply
- `?`: show or hide the help/status panel
- `Escape` or `q`: cancel

The help and status text is hidden by default. Press `?` to show it in a
translucent panel with a hotkey/action table.

The overlay focuses itself but does not actively grab the keyboard, so global i3
bindings such as Print Screen can still pass through.

The overlay uses GTK/Cairo ARGB drawing and derives its palette from the active
GTK theme background, foreground, and selected/accent colors. If no X compositor
is running, `betr-randr` tries to start `picom` first, then `xcompmgr`. To leave
compositor management to your i3 session:

```sh
./bin/betr-randr --gui --compositor none
```

To inspect the parsed layout without opening Rofi:

```sh
./bin/betr-randr --print-layout
```

Rotation maps directly to `xrandr --rotate`, so the generated commands are:

```sh
xrandr --output HDMI-A-0 --rotate normal
xrandr --output HDMI-A-0 --rotate left
xrandr --output HDMI-A-0 --rotate right
xrandr --output HDMI-A-0 --rotate inverted
```

## i3 Binding

Add a binding like this to your i3 config:

```i3
bindsym $mod+p exec --no-startup-id /home/jwagner/Development/side_projects/betr_randr/bin/betr-randr --project menu
```

Reload i3 after editing the config.

If your laptop exposes a monitor/projector function key as a keysym, bind that
keysym to the same command. For example, after identifying the key with `xev`:

```i3
bindsym XF86Display exec --no-startup-id /home/jwagner/Development/side_projects/betr_randr/bin/betr-randr --project menu
```

If you always want the overlay editor:

```i3
bindsym $mod+p exec --no-startup-id /home/jwagner/Development/side_projects/betr_randr/bin/betr-randr --gui
```

## Theme

By default, the script uses your active Rofi theme. You can add extra Rofi theme
colors and adds only sizing/spacing/font tweaks for the layout preview. You can
replace those tweaks with `BETR_RANDR_ROFI_THEME_STR`:

```sh
BETR_RANDR_ROFI_THEME_STR='window { width: 42em; }' ./bin/betr-randr
```

That keeps the menu compatible with both dark and light themes while still
allowing project-specific sizing or layout tweaks.

## License

This project is released under CC0 1.0 Universal. See [LICENSE](LICENSE).
