import importlib.util
import io
from importlib.machinery import SourceFileLoader
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "bin" / "betr-randr"


def load_module():
    loader = SourceFileLoader("betr_randr", str(SCRIPT))
    spec = importlib.util.spec_from_loader("betr_randr", loader)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class SimulatedMonitorCommandTests(unittest.TestCase):
    def test_simulated_monitor_commands_are_skipped_for_real_apply(self):
        br = load_module()
        outputs = br.parse_xrandr(
            """Screen 0: minimum 320 x 200, current 1920 x 1200, maximum 16384 x 16384
eDP connected primary 1920x1200+0+0 normal
   1920x1200     60.00*+
"""
        )
        br.add_simulated_monitor(outputs, "SIM-1:1920x1080")
        states = br.create_gui_state(outputs)
        sim = next(state for state in states if state.name == "SIM-1")
        sim.enabled = True
        sim.x = 1920
        sim.y = 0

        commands = br.build_layout_commands(states, dry_run=False)

        self.assertTrue(all("SIM-1" not in command for command in commands))

    def test_simulated_monitor_commands_are_included_for_dry_run(self):
        br = load_module()
        outputs = br.parse_xrandr(
            """Screen 0: minimum 320 x 200, current 1920 x 1200, maximum 16384 x 16384
eDP connected primary 1920x1200+0+0 normal
   1920x1200     60.00*+
"""
        )
        br.add_simulated_monitor(outputs, "SIM-1:1920x1080")
        states = br.create_gui_state(outputs)
        sim = next(state for state in states if state.name == "SIM-1")
        sim.enabled = True
        sim.x = 1920
        sim.y = 0

        commands = br.build_layout_commands(states, dry_run=True)

        self.assertIn(
            ["xrandr", "--output", "SIM-1", "--mode", "1920x1080", "--rotate", "normal", "--pos", "1920x0"],
            commands,
        )

    def test_simulated_monitor_with_geometry_starts_attached(self):
        br = load_module()
        outputs = br.parse_xrandr(
            """Screen 0: minimum 320 x 200, current 1920 x 1200, maximum 16384 x 16384
eDP connected primary 1920x1200+0+0 normal
   1920x1200     60.00*+
"""
        )
        br.add_simulated_monitor(outputs, "SIM-1:1920x1080+1920+0")

        sim_output = next(output for output in outputs if output.name == "SIM-1")
        states = br.create_gui_state(outputs)
        sim_state = next(state for state in states if state.name == "SIM-1")

        self.assertTrue(sim_output.active)
        self.assertTrue(sim_state.enabled)
        self.assertEqual((1920, 0, 1920, 1080), (sim_state.x, sim_state.y, sim_state.width, sim_state.height))
        self.assertEqual("1920x1080", sim_state.mode)

    def test_negative_left_placement_is_normalized_before_commands(self):
        br = load_module()
        current = br.Output(
            name="DP-1",
            connected=True,
            primary=True,
            geometry="3840x2160+0+0",
            width=3840,
            height=2160,
            x=0,
            y=0,
            modes=[br.Mode("3840x2160", current=True, preferred=True)],
        )
        former = br.Output(
            name="eDP",
            connected=True,
            modes=[br.Mode("1920x1200", preferred=True)],
        )
        states = br.create_gui_state([current, former])
        former_state = next(state for state in states if state.name == "eDP")
        former_state.enabled = True
        former_state.x = -1920
        former_state.y = 0

        commands = br.build_layout_commands(states, dry_run=True)

        self.assertIn(["xrandr", "--output", "eDP", "--mode", "1920x1200", "--rotate", "normal", "--pos", "0x0"], commands)
        self.assertIn(
            ["xrandr", "--output", "DP-1", "--mode", "3840x2160", "--rotate", "normal", "--pos", "1920x0", "--primary"],
            commands,
        )

    def test_layout_commands_mark_selected_enabled_monitor_primary(self):
        br = load_module()
        outputs = br.parse_xrandr(
            """Screen 0: minimum 320 x 200, current 3840 x 1200, maximum 16384 x 16384
eDP connected primary 1920x1200+0+0 normal
   1920x1200     60.00*+
HDMI-A-0 connected 1920x1080+1920+0 normal
   1920x1080     60.00*+
"""
        )
        states = br.create_gui_state(outputs)
        for state in states:
            state.primary = state.name == "HDMI-A-0"

        commands = br.build_layout_commands(states, dry_run=True)

        self.assertIn(["xrandr", "--output", "eDP", "--mode", "1920x1200", "--rotate", "normal", "--pos", "0x0"], commands)
        self.assertIn(
            ["xrandr", "--output", "HDMI-A-0", "--mode", "1920x1080", "--rotate", "normal", "--pos", "1920x0", "--primary"],
            commands,
        )

    def test_layout_size_for_rotation_swaps_sideways_rotations(self):
        br = load_module()

        self.assertEqual((1080, 1920), br.layout_size_for_rotation("1920x1080", (1920, 1080), "right"))
        self.assertEqual((1080, 1920), br.layout_size_for_rotation("1920x1080", (1920, 1080), "left"))
        self.assertEqual((1920, 1080), br.layout_size_for_rotation("1920x1080", (1920, 1080), "inverted"))

    def test_layout_commands_include_rotated_monitor(self):
        br = load_module()
        outputs = br.parse_xrandr(
            """Screen 0: minimum 320 x 200, current 3840 x 1200, maximum 16384 x 16384
eDP connected primary 1920x1200+0+0 normal
   1920x1200     60.00*+
HDMI-A-0 connected 1920x1080+1920+0 normal
   1920x1080     60.00*+
"""
        )
        states = br.create_gui_state(outputs)
        hdmi = next(state for state in states if state.name == "HDMI-A-0")
        hdmi.rotation = "right"
        hdmi.width, hdmi.height = br.layout_size_for_rotation(hdmi.mode, (hdmi.width, hdmi.height), hdmi.rotation)

        commands = br.build_layout_commands(states, dry_run=True)

        self.assertIn(
            ["xrandr", "--output", "HDMI-A-0", "--mode", "1920x1080", "--rotate", "right", "--pos", "1920x0"],
            commands,
        )

    def test_simulated_monitor_can_attach_right_of_primary_with_shorthand(self):
        br = load_module()
        outputs = br.parse_xrandr(
            """Screen 0: minimum 320 x 200, current 1920 x 1200, maximum 16384 x 16384
eDP connected primary 1920x1200+0+0 normal
   1920x1200     60.00*+
"""
        )
        br.add_simulated_monitor(outputs, "SIM-ATTACHED:1920x1080@right")
        br.add_simulated_monitor(outputs, "SIM-AVAILABLE:2560x1440")

        states = br.create_gui_state(outputs)
        attached = next(state for state in states if state.name == "SIM-ATTACHED")
        available = next(state for state in states if state.name == "SIM-AVAILABLE")

        self.assertTrue(attached.enabled)
        self.assertEqual((1920, 0, 1920, 1080), (attached.x, attached.y, attached.width, attached.height))
        self.assertFalse(available.enabled)

    def test_four_one_attached_simulated_layout(self):
        br = load_module()
        outputs = br.parse_xrandr(
            """Screen 0: minimum 320 x 200, current 1920 x 1200, maximum 16384 x 16384
eDP connected primary 1920x1200+0+0 normal
   1920x1200     60.00*+
"""
        )
        br.add_simulated_layout(outputs, "four-one-attached")

        states = br.create_gui_state(outputs)
        sim_states = {state.name: state for state in states if state.name.startswith("SIM-")}

        self.assertEqual({"SIM-1", "SIM-2", "SIM-3", "SIM-4"}, set(sim_states))
        self.assertTrue(sim_states["SIM-1"].enabled)
        self.assertFalse(sim_states["SIM-2"].enabled)
        self.assertFalse(sim_states["SIM-3"].enabled)
        self.assertFalse(sim_states["SIM-4"].enabled)

    def test_disconnected_outputs_without_geometry_are_not_position_known(self):
        br = load_module()
        outputs = br.parse_xrandr(
            """Screen 0: minimum 320 x 200, current 1920 x 1200, maximum 16384 x 16384
eDP connected primary 1920x1200+0+0 normal
   1920x1200     60.00*+
HDMI-A-0 disconnected
"""
        )

        states = br.create_gui_state(outputs)
        detached = next(state for state in states if state.name == "HDMI-A-0")

        self.assertFalse(detached.connected)
        self.assertFalse(detached.enabled)
        self.assertFalse(detached.position_known)

    def test_disconnected_outputs_with_reported_geometry_are_position_known_placeholders(self):
        br = load_module()
        outputs = [
            br.Output(
                name="eDP",
                connected=True,
                primary=True,
                geometry="1920x1200+0+0",
                width=1920,
                height=1200,
                x=0,
                y=0,
                modes=[br.Mode("1920x1200", current=True, preferred=True)],
            ),
            br.Output(
                name="HDMI-A-0",
                connected=False,
                geometry="1920x1080+1920+0",
                width=1920,
                height=1080,
                x=1920,
                y=0,
                modes=[br.Mode("1920x1080", current=True, preferred=True)],
            ),
        ]

        states = br.create_gui_state(outputs)
        detached = next(state for state in states if state.name == "HDMI-A-0")

        self.assertFalse(detached.connected)
        self.assertFalse(detached.enabled)
        self.assertTrue(detached.position_known)
        self.assertEqual((1920, 0, 1920, 1080), (detached.x, detached.y, detached.width, detached.height))
        self.assertTrue(all("HDMI-A-0" not in command for command in br.build_layout_commands(states, dry_run=True)))

    def test_disconnected_position_known_placeholder_can_be_marked_for_detach(self):
        br = load_module()
        detached = br.GuiOutputState(
            output=br.Output(
                name="HDMI-A-0",
                connected=False,
                geometry="1920x1080+1920+0",
                width=1920,
                height=1080,
                x=1920,
                y=0,
                modes=[br.Mode("1920x1080", current=True, preferred=True)],
            ),
            enabled=False,
            x=1920,
            y=0,
            width=1920,
            height=1080,
            mode="1920x1080",
            rotation="normal",
            primary=False,
            position_known=False,
            force_off=True,
        )
        current = br.GuiOutputState(
            output=br.Output(
                name="eDP",
                connected=True,
                primary=True,
                geometry="1920x1200+0+0",
                width=1920,
                height=1200,
                x=0,
                y=0,
                modes=[br.Mode("1920x1200", current=True, preferred=True)],
            ),
            enabled=True,
            x=0,
            y=0,
            width=1920,
            height=1200,
            mode="1920x1200",
            rotation="normal",
            primary=True,
            position_known=True,
        )

        commands = br.build_layout_commands([current, detached], dry_run=True)

        self.assertIn(["xrandr", "--output", "HDMI-A-0", "--off"], commands)


class I3FocusSelectionTests(unittest.TestCase):
    def test_focused_state_prefers_i3_output_name(self):
        br = load_module()
        states = br.create_gui_state(
            [
                br.Output(
                    name="eDP",
                    connected=True,
                    primary=True,
                    geometry="1920x1200+0+0",
                    width=1920,
                    height=1200,
                    x=0,
                    y=0,
                    modes=[br.Mode("1920x1200", current=True, preferred=True)],
                ),
                br.Output(
                    name="DisplayPort-6",
                    connected=True,
                    geometry="3840x2160+1920+0",
                    width=3840,
                    height=2160,
                    x=1920,
                    y=0,
                    modes=[br.Mode("3840x2160", current=True, preferred=True)],
                ),
            ]
        )

        focused = br.focused_state_from_i3(states, "DisplayPort-6", (0, 0, 1920, 1200))

        self.assertEqual("DisplayPort-6", focused.name)

    def test_focused_state_uses_largest_overlap_when_rect_is_not_exact(self):
        br = load_module()
        states = br.create_gui_state(
            [
                br.Output(
                    name="eDP",
                    connected=True,
                    primary=True,
                    geometry="1920x1200+0+0",
                    width=1920,
                    height=1200,
                    x=0,
                    y=0,
                    modes=[br.Mode("1920x1200", current=True, preferred=True)],
                ),
                br.Output(
                    name="DisplayPort-6",
                    connected=True,
                    geometry="3840x2160+1920+0",
                    width=3840,
                    height=2160,
                    x=1920,
                    y=0,
                    modes=[br.Mode("3840x2160", current=True, preferred=True)],
                ),
            ]
        )

        focused = br.focused_state_from_i3(states, None, (1920, 24, 3840, 2136))

        self.assertEqual("DisplayPort-6", focused.name)

    def test_visible_i3_output_rects_uses_visible_workspace_viewports(self):
        br = load_module()
        workspaces = [
            {
                "focused": True,
                "visible": True,
                "output": "eDP",
                "rect": {"x": 10, "y": 10, "width": 1900, "height": 1155},
            },
            {
                "focused": False,
                "visible": True,
                "output": "DisplayPort-6",
                "rect": {"x": 1930, "y": 10, "width": 3820, "height": 2115},
            },
            {
                "focused": False,
                "visible": False,
                "output": "DisplayPort-6",
                "rect": {"x": 1920, "y": 0, "width": 3840, "height": 2160},
            },
        ]

        rects = br.visible_i3_output_rects(workspaces)

        self.assertEqual((10, 10, 1900, 1155), rects["eDP"])
        self.assertEqual((1930, 10, 3820, 2115), rects["DisplayPort-6"])


class ProjectModeCommandTests(unittest.TestCase):
    def test_extend_places_external_to_the_right(self):
        br = load_module()
        outputs = br.parse_xrandr(
            """Screen 0: minimum 320 x 200, current 1920 x 1200, maximum 16384 x 16384
eDP connected primary 1920x1200+0+0 normal
   1920x1200     60.00*+
HDMI-A-0 connected 1920x1080+1920+0 normal
   1920x1080     60.00*+
"""
        )

        commands = br.build_project_commands(outputs, "extend")

        self.assertIn(["xrandr", "--output", "eDP", "--mode", "1920x1200", "--pos", "0x0", "--primary"], commands)
        self.assertIn(["xrandr", "--output", "HDMI-A-0", "--mode", "1920x1080", "--right-of", "eDP"], commands)

    def test_duplicate_mirrors_external_to_internal(self):
        br = load_module()
        outputs = br.parse_xrandr(
            """Screen 0: minimum 320 x 200, current 1920 x 1200, maximum 16384 x 16384
eDP connected primary 1920x1200+0+0 normal
   1920x1200     60.00*+
HDMI-A-0 connected 1920x1080+1920+0 normal
   1920x1080     60.00*+
"""
        )

        commands = br.build_project_commands(outputs, "duplicate")

        self.assertIn(["xrandr", "--output", "HDMI-A-0", "--mode", "1920x1080", "--same-as", "eDP"], commands)

    def test_external_only_with_only_simulated_external_is_noop_for_real_apply(self):
        br = load_module()
        outputs = br.parse_xrandr(
            """Screen 0: minimum 320 x 200, current 1920 x 1200, maximum 16384 x 16384
eDP connected primary 1920x1200+0+0 normal
   1920x1200     60.00*+
"""
        )
        br.add_simulated_monitor(outputs, "SIM-1:1920x1080")

        commands = br.build_project_commands(outputs, "external-only", dry_run=False)

        self.assertEqual([], commands)

    def test_largest_mode_picks_highest_area_mode(self):
        br = load_module()
        output = br.Output(
            name="HDMI-A-0",
            connected=True,
            modes=[
                br.Mode("1920x1080", preferred=True),
                br.Mode("2560x1440"),
                br.Mode("1280x720"),
            ],
        )

        self.assertEqual("2560x1440", br.output_largest_mode(output))


class CompositorTests(unittest.TestCase):
    def test_compositor_selection_atom_defaults_to_screen_zero(self):
        br = load_module()

        self.assertEqual("_NET_WM_CM_S0", br.compositor_selection_atom(":0"))

    def test_compositor_selection_atom_uses_display_screen(self):
        br = load_module()

        self.assertEqual("_NET_WM_CM_S1", br.compositor_selection_atom(":0.1"))

    def test_ensure_compositor_reuses_existing_compositor(self):
        br = load_module()

        with mock.patch.object(br, "compositor_running", return_value=True), mock.patch.object(
            br, "start_compositor"
        ) as start_compositor:
            status = br.ensure_compositor("auto")

        self.assertEqual("Using existing X compositor.", status)
        start_compositor.assert_not_called()

    def test_ensure_compositor_starts_first_available_auto_candidate(self):
        br = load_module()

        with mock.patch.object(br, "compositor_running", return_value=False), mock.patch.object(
            br, "start_compositor", side_effect=[False, True]
        ) as start_compositor:
            status = br.ensure_compositor("auto")

        self.assertEqual("Started xcompmgr for overlay transparency.", status)
        self.assertEqual([mock.call("picom"), mock.call("xcompmgr")], start_compositor.mock_calls)


class DependencyCheckTests(unittest.TestCase):
    def test_dependency_statuses_report_required_and_optional_tools(self):
        br = load_module()

        def fake_which(name):
            return f"/usr/bin/{name}" if name in {"xrandr", "rofi", "picom"} else None

        with mock.patch.object(br.shutil, "which", side_effect=fake_which), mock.patch.object(
            br, "python_module_available", return_value=True
        ):
            statuses = br.dependency_statuses()

        status_by_name = {name: (required, available) for name, _purpose, required, available in statuses}
        self.assertEqual((True, True), status_by_name["xrandr"])
        self.assertEqual((True, True), status_by_name["rofi"])
        self.assertEqual((False, True), status_by_name["picom or xcompmgr"])
        self.assertEqual((False, False), status_by_name["xprop"])

    def test_print_dependency_check_fails_when_required_dependency_is_missing(self):
        br = load_module()

        with mock.patch.object(
            br,
            "dependency_statuses",
            return_value=[
                ("xrandr", "required for display query/apply", True, False),
                ("picom or xcompmgr", "optional compositor for transparent overlay", False, False),
            ],
        ):
            output = io.StringIO()
            with redirect_stdout(output):
                status = br.print_dependency_check()

        self.assertEqual(1, status)
        self.assertIn("missing xrandr", output.getvalue())


if __name__ == "__main__":
    unittest.main()
