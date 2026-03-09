"""Display profile helpers for matching the target touchscreen layout."""


def _safe_int(value, default):
    try:
        return int(value)
    except Exception:
        return int(default)


def _safe_float(value, default):
    try:
        return float(value)
    except Exception:
        return float(default)


def _controller_from(anchor):
    controller = getattr(anchor, "controller", None)
    if controller is not None:
        return controller
    return anchor


def get_display_profile(anchor):
    """Return display/layout metrics from config, with target screen fallbacks."""
    controller = _controller_from(anchor)
    cfg = getattr(controller, "config", {}) if controller is not None else {}
    if not isinstance(cfg, dict):
        cfg = {}

    display_cfg = cfg.get("display_profile", {})
    if not isinstance(display_cfg, dict):
        display_cfg = {}

    try:
        actual_screen_w = max(1, int(anchor.winfo_screenwidth()))
        actual_screen_h = max(1, int(anchor.winfo_screenheight()))
    except Exception:
        actual_screen_w = 1920
        actual_screen_h = 1080

    target_width = max(320, _safe_int(display_cfg.get("target_width", 1920), 1920))
    target_height = max(240, _safe_int(display_cfg.get("target_height", 1080), 1080))
    diagonal_inches = max(
        1.0,
        _safe_float(
            display_cfg.get("diagonal_inches", cfg.get("display_diagonal_inches", 13.3)),
            13.3,
        ),
    )

    diagonal_pixels = (target_width ** 2 + target_height ** 2) ** 0.5
    ppi = diagonal_pixels / diagonal_inches if diagonal_inches > 0 else 165.0

    top_dead_zone_px = max(
        0,
        _safe_int(display_cfg.get("touch_dead_zone_top_px", 0), 0),
    )
    bottom_start_px = max(
        0,
        _safe_int(display_cfg.get("touch_dead_zone_bottom_start_px", target_height), target_height),
    )
    bottom_dead_zone_px = max(0, target_height - bottom_start_px)

    return {
        "actual_screen_width": actual_screen_w,
        "actual_screen_height": actual_screen_h,
        "layout_width": target_width,
        "layout_height": target_height,
        "diagonal_inches": diagonal_inches,
        "ppi": ppi,
        "touch_dead_zone_top_px": top_dead_zone_px,
        "touch_dead_zone_bottom_start_px": bottom_start_px,
        "touch_dead_zone_bottom_px": bottom_dead_zone_px,
        "header_px": max(96, int(target_height * 0.15)),
        "footer_px": max(54, int(target_height * 0.05)),
        "status_panel_height_px": max(
            90,
            _safe_int(display_cfg.get("status_panel_height_px", int(target_height * 0.10)), int(target_height * 0.10)),
        ),
        "window_margin_px": max(
            20,
            _safe_int(display_cfg.get("window_margin_px", 40), 40),
        ),
    }


def fit_target_geometry(anchor):
    """Return a centered geometry string that preserves the target aspect ratio."""
    profile = get_display_profile(anchor)
    max_width = max(320, profile["actual_screen_width"] - (profile["window_margin_px"] * 2))
    max_height = max(240, profile["actual_screen_height"] - (profile["window_margin_px"] * 2))
    target_width = profile["layout_width"]
    target_height = profile["layout_height"]

    scale = min(max_width / float(target_width), max_height / float(target_height))
    scale = max(0.2, min(1.0, scale))

    width = max(320, int(round(target_width * scale)))
    height = max(240, int(round(target_height * scale)))
    x = max(0, (profile["actual_screen_width"] - width) // 2)
    y = max(0, (profile["actual_screen_height"] - height) // 2)
    return f"{width}x{height}+{x}+{y}"
