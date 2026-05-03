from creator_admin.app import create_app
from creator_admin.config import AdminSettings


def main() -> None:
    settings = AdminSettings.from_env()
    app = create_app(settings)

    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
