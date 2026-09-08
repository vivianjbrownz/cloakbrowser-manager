from ops.verify_runtime_upgrade import compare


def baseline():
    return {"browser_path": "/chrome", "browser_sha256": "browser", "font_files": 1,
            "fonts_sha256": "fonts", "python_packages_sha256": "python",
            "system_packages": {"kasmvncserver": "1.3.3-1", "libgbm1": "fixed"}}


def test_only_the_display_package_may_change():
    old = baseline()
    new = {**old, "system_packages": {**old["system_packages"], "kasmvncserver": "1.5.0-1"}}
    assert compare(old, new)["passed"]
    new["system_packages"]["libgbm1"] = "drift"
    assert not compare(old, new)["passed"]


def test_unchanged_binary_is_not_enough_if_fonts_drift():
    old = baseline()
    new = {**old, "fonts_sha256": "different", "system_packages": {"kasmvncserver": "1.5.0-1", "libgbm1": "fixed"}}
    assert not compare(old, new)["passed"]
