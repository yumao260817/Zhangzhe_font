import uvicorn


def run(host: str = "127.0.0.1", port: int = 8000, config: str | None = None) -> None:
    from .paths import CONFIG_FILE
    from .server.app import make_app

    app = make_app(config or str(CONFIG_FILE))
    print(f"评审台已启动: http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)