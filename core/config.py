import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Settings:
    NIM_API_KEY: str = os.getenv("NIM_API_KEY", "")
    NIM_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NIM_MODEL: str = "minimaxai/minimax-m2.7"
    NIM_RPM: int = 40

    GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")

    DB_PATH: Path = Path.home() / ".github-innovator" / "innovations.db"
    LOG_DIR: Path = Path.home() / ".github-innovator" / "logs"

    MAX_RETRIES_PER_CHANGE: int = 3
    TEMP_CLONE_DIR: Path = Path.home() / ".github-innovator" / "tmp"

    LICENSES_ALLOWED: set[str] = {"mit", "apache-2.0", "bsd-2-clause", "bsd-3-clause", "unlicense", "isc", "cc0-1.0"}

    MIN_STARS: int = 3
    MAX_STARS: int = 500
    MIN_LINES: int = 100
    MAX_LINES: int = 50_000

    SUPPORTED_LANGUAGES: set[str] = {"Python", "JavaScript", "TypeScript", "Go", "Rust"}

    INNOVATION_SCORE_THRESHOLD: int = 5


settings = Settings()
