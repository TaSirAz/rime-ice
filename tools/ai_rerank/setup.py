"""Opt-in setup for a local Rime folder and optional cloud-managed sync folder."""
import argparse
import datetime
from pathlib import Path
import yaml


def update_yaml(path, change):
    original = path.read_text(encoding="utf-8-sig") if path.exists() else ""
    data = yaml.safe_load(original) or {}
    change(data)
    if original:
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        path.with_name(path.name + "." + stamp + ".bak").write_text(original, encoding="utf-8")
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def configure(user_dir, enable=False, disable=False, sync_dir=None):
    if not user_dir.is_dir():
        raise ValueError("Select the actual Weasel user directory")
    if enable or disable:
        bridge = user_dir / "ai_bridge"
        bridge.mkdir(exist_ok=True)
        def patch(data):
            p = data.setdefault("patch", {})
            p["ai_rerank/enabled"] = bool(enable and not disable)
            p["ai_rerank/bridge_dir"] = str(bridge)
            if enable:
                p["ai_rerank/auto_refresh"] = True
                for key, value in [("engine/processors/@before 0", "lua_processor@*ai_rerank*processor"),
                                   ("engine/filters/+", "lua_filter@*ai_rerank*filter")]:
                    if key.endswith("@before 0"):
                        if key in p and p[key] != value:
                            raise ValueError("Existing processor insertion must be merged manually")
                        p[key] = value
                    else:
                        items = p.setdefault(key, [])
                        if value not in items:
                            items.append(value)
            if disable:
                components = {
                    "engine/processors/@before 0": "lua_processor@*ai_rerank*processor",
                    "engine/processors/+": "lua_processor@*ai_rerank*processor",
                    "engine/filters/+": "lua_filter@*ai_rerank*filter",
                }
                for key, component in components.items():
                    value = p.get(key)
                    if value == component:
                        p.pop(key)
                    elif isinstance(value, list):
                        remaining = [item for item in value if item != component]
                        if remaining:
                            p[key] = remaining
                        else:
                            p.pop(key)
        update_yaml(user_dir / "rime_ice.custom.yaml", patch)
    if sync_dir:
        sync_dir = sync_dir.resolve()
        if sync_dir == user_dir.resolve() or user_dir.resolve() in sync_dir.parents:
            raise ValueError("Use a separate cloud-managed folder, outside the live Rime user directory")
        sync_dir.mkdir(parents=True, exist_ok=True)
        def sync(data):
            # Preserve installation_id: each computer must keep its own identity.
            if not data.get("installation_id"):
                raise ValueError("installation.yaml has no installation_id; deploy Weasel first")
            data["sync_dir"] = str(sync_dir)
        update_yaml(user_dir / "installation.yaml", sync)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--user-dir", required=True, type=Path)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--enable-ai", action="store_true")
    g.add_argument("--disable-ai", action="store_true")
    p.add_argument("--sync-dir", type=Path, help="Existing OneDrive/Dropbox/etc. folder; no account connection is made")
    args = p.parse_args()
    configure(args.user_dir, args.enable_ai, args.disable_ai, args.sync_dir)
    print("Configuration saved with backups. Redeploy Weasel. For cloud sync, then run 用戶資料同步.")
