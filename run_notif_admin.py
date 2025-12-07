import uvicorn
import sys
import os

if __name__ == "__main__":
    # Запуск FastAPI приложения
    uvicorn.run(
        "app_notif.main:app",
        host="10.10.10.12",
        port=8011,
        reload=True,
        log_level="info"
    )