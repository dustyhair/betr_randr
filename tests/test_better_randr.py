import importlib.util
from importlib.machinery import SourceFileLoader
import sys
import unittest
from unittest import mock
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "bin" / "better-randr"


def load_module():
    loader = SourceFileLoader("better_randr", str(SCRIPT))
    spec = importlib.util.spec_from_loader("better_randr", loader)
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


if __name__ == "__main__":
    unittest.main()
