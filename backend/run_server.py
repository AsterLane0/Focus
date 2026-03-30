import os

import uvicorn
from dotenv import load_dotenv


def main() -> None:
    load_dotenv()
    host = os.getenv("FOCUS_HOST", "0.0.0.0").strip() or "0.0.0.0"
    port = int(os.getenv("FOCUS_PORT", "8000"))
    uvicorn.run("backend.api_server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
