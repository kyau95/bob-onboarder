from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Bob the Onboarder"
    app_version: str = "0.1.0"
    debug: bool = False

    # Where cloned repositories are stored inside the container / locally
    repos_base_dir: str = "/tmp/onboarder_repos"

    # CORS — allow the Vite dev server by default
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
