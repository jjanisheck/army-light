"""Effect step-generator tests. Effects are infinite iterators of
(rgb, transition, delay_s) steps consumed by the controller's effect task —
pure functions, so we just sample the first few steps."""

from itertools import islice

from army_light import effects


def take(gen, n):
    return list(islice(gen, n))


def test_blink_alternates_color_and_off():
    steps = take(effects.blink((255, 0, 0)), 4)
    assert steps[0][0] == (255, 0, 0)
    assert steps[1][0] == (0, 0, 0)
    assert steps[2][0] == (255, 0, 0)
    assert steps[3][0] == (0, 0, 0)
    # Hard cuts: no fade transition.
    assert all(t == 0 for _, t, _ in steps)
    # Constant cadence, sane speed.
    delays = {d for _, _, d in steps}
    assert len(delays) == 1
    assert 0.2 <= delays.pop() <= 2.0


def test_breath_fades_color_and_off():
    steps = take(effects.breath((0, 0, 255)), 4)
    assert steps[0][0] == (0, 0, 255)
    assert steps[1][0] == (0, 0, 0)
    # Smooth: every step carries a non-zero transition (10ms units, fits u8),
    # and the delay leaves time for the fade to complete.
    for _rgb, transition, delay in steps:
        assert 0 < transition <= 255
        assert delay >= transition / 100.0


def test_cycle_walks_the_hue_wheel():
    steps = take(effects.cycle(), 24)
    colors = [rgb for rgb, _, _ in steps]
    # All distinct hues, all valid RGB, and it must include reds and blues
    # (i.e. actually go around the wheel, not sit in one corner).
    assert len(set(colors)) == len(colors)
    assert all(0 <= c <= 255 for rgb in colors for c in rgb)
    assert any(r > 200 and b < 60 for r, g, b in colors)
    assert any(b > 200 and r < 60 for r, g, b in colors)


def test_cycle_repeats_after_full_revolution():
    steps = take(effects.cycle(), 48)
    first, second = steps[:24], steps[24:]
    assert [s[0] for s in first] == [s[0] for s in second]


def test_strobe_is_fast_hard_flashing():
    steps = take(effects.strobe((255, 0, 0)), 4)
    assert steps[0][0] == (255, 0, 0)
    assert steps[1][0] == (0, 0, 0)
    for _rgb, transition, delay in steps:
        assert transition == 0          # hard cuts
        assert 0.05 <= delay <= 0.3     # fast


def test_duo_fade_alternates_the_two_colors_smoothly():
    a, b = (130, 60, 255), (255, 40, 150)
    steps = take(effects.duo_fade(a, b), 4)
    assert [s[0] for s in steps] == [a, b, a, b]
    for _rgb, transition, delay in steps:
        assert transition > 0           # smooth gradient
        assert delay >= transition / 100.0


def test_candle_flickers_warm_and_gentle():
    steps = take(effects.candle(), 40)
    for (r, g, b), transition, delay in steps:
        assert r > g > b                # warm: amber-ish ordering
        assert 0 <= transition <= 30    # gentle, not slow morphs
        assert 0.05 <= delay <= 0.5
    brightnesses = {rgb[0] for rgb, _, _ in steps}
    assert len(brightnesses) > 3        # actually flickers


def test_party_shuffle_jumps_between_distinct_colors():
    steps = take(effects.party(), 40)
    colors = [rgb for rgb, _, _ in steps]
    assert len(set(colors)) > 10        # varied
    assert all(0 <= c <= 255 for rgb in colors for c in rgb)
    assert all(s[0] != s2[0] for s, s2 in zip(steps, steps[1:]))  # always moves
    transitions = {t for _, t, _ in steps}
    assert 0 in transitions and any(t > 0 for t in transitions)  # cuts AND fades


def test_jungle_drifts_through_canopy_palette():
    steps = take(effects.jungle(), 40)
    seen = {rgb for rgb, _, _ in steps}
    assert seen <= set(effects.JUNGLE_COLORS)   # stays on theme
    assert len(seen) >= 4                       # actually drifts around
    for _rgb, transition, delay in steps:
        assert 0 <= transition <= 255
        assert 0.1 <= delay <= 4.0


def test_ice_shimmers_and_sparkles_white():
    steps = take(effects.ice(), 16)
    seen = {rgb for rgb, _, _ in steps}
    assert seen <= set(effects.ICE_COLORS)
    assert (255, 255, 255) in seen              # guaranteed sparkle interval
    for _rgb, transition, delay in steps:
        assert 0 <= transition <= 255
        assert 0.1 <= delay <= 4.0


def test_rainbow_marches_roygbiv_in_order():
    steps = take(effects.rainbow(), 14)
    colors = [rgb for rgb, _, _ in steps]
    assert colors == effects.ROYGBIV * 2          # exact classic order, looping
    for _rgb, transition, delay in steps:
        assert transition > 0                     # smooth fades
        assert delay >= transition / 100.0        # fade completes before next


def test_glow_cycle_breathes_brightness_through_the_hues():
    steps = take(effects.glow_cycle(), 24)  # 12 hues x (bright, dim)
    brights, dims = steps[0::2], steps[1::2]
    for (rgb_b, t_b, d_b), (rgb_d, t_d, d_d) in zip(brights, dims):
        assert max(rgb_b) >= 200            # swells up bright
        assert 0 < max(rgb_d) <= 40         # dims low but never fully off
        assert t_b > 0 and t_d > 0          # both ramps are smooth fades
        assert d_b >= t_b / 100.0 and d_d >= t_d / 100.0
    # The hue actually advances between swells (it cycles, not pulses).
    assert len({rgb for rgb, _, _ in brights}) == len(brights)


def test_glow_cycle_changes_hue_at_the_dim_point():
    steps = take(effects.glow_cycle(), 4)
    (b1, _, _), (d1, _, _), (b2, _, _), _ = steps
    # dim step keeps the current hue (scaled), so the color switch is hidden
    scale = max(d1) / max(b1)
    assert all(abs(d - b * scale) <= 2 for d, b in zip(d1, b1))
    assert b2 != b1


def test_registry_labels_and_arity():
    # The menu builds itself from this registry. arity = colors the effect takes.
    expected = {"Blink": 1, "Breath": 1, "Strobe": 1, "Duo Fade": 2,
                "Color Cycle": 0, "Rainbow": 0, "Glow Cycle": 0,
                "Candle": 0, "Party": 0, "Jungle": 0, "Ice": 0}
    assert {label: e.arity for label, e in effects.EFFECTS.items()} == expected


def test_registry_factories_produce_steps():
    for _label, eff in effects.EFFECTS.items():
        args = [(255, 0, 0), (0, 0, 255)][: eff.arity]
        gen = eff.steps(*args)
        rgb, transition, delay = next(gen)
        assert all(0 <= c <= 255 for c in rgb)
        assert 0 <= transition <= 255
        assert delay > 0
