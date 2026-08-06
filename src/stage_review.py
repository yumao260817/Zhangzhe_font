import uvicorn


def run(host: str | None = None, port: int | None = None, config: str | None = None) -> None:
    from .paths import CONFIG_FILE
    from .server.app import make_app, _load_config

    cfg = _load_config(config and __import__("pathlib").Path(config) or CONFIG_FILE)
    server_cfg = cfg.get("server", {}) if isinstance(cfg.get("server"), dict) else {}
    host = host or server_cfg.get("host") or "127.0.0.1"
    port = port or int(server_cfg.get("port") or 8000)

    app = make_app(config or str(CONFIG_FILE))
    print(f"评审台已启动: http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)
