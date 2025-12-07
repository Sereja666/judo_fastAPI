
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
import os
from datetime import datetime, timedelta
import sys

from app_notif.database import get_db
from database.models import Students_parents, Students, Tg_notif_user

# Добавляем путь к корню проекта для импорта schemas
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Импортируем наши модели и зависимости

from config import settings

app = FastAPI(title="Панель администратора регистраций", version="1.0.0")

# Настраиваем CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Настраиваем шаблоны
templates = Jinja2Templates(directory="app_notif/templates")

# Монтируем статические файлы
app.mount("/static", StaticFiles(directory="app_notif/static"), name="static")


# ==================== Вспомогательные функции ====================

def get_user_students(db: Session, user_id: int):
    """Получить информацию о детях пользователя"""
    student_relations = db.query(Students_parents).filter(
        Students_parents.parents == user_id
    ).all()

    students_info = []
    for relation in student_relations:
        student = db.query(Students).filter(Students.id == relation.student).first()
        if student:
            students_info.append({
                "id": student.id,
                "name": student.name,
                "active": student.active,
                "birthday": student.birthday.strftime('%d.%m.%Y') if student.birthday else None,
                "sport_discipline": student.sport_discipline
            })

    return students_info


def log_action(action: str, user_id: int, user_name: str, reason: str = ""):
    """Логировать действия администратора"""
    log_file = "admin_actions.log"
    log_dir = "logs"

    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    log_path = os.path.join(log_dir, log_file)

    with open(log_path, "a", encoding="utf-8") as f:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"{timestamp} | {action.upper()} | UserID: {user_id} | Name: {user_name}"
        if reason:
            log_entry += f" | Reason: {reason}"
        log_entry += "\n"
        f.write(log_entry)


# ==================== Роуты ====================

@app.get("/", response_class=HTMLResponse)
async def admin_panel(request: Request, db: Session = Depends(get_db)):
    """Главная страница админ-панели"""
    # Получаем пользователей, ожидающих подтверждения
    pending_users = db.query(Tg_notif_user).filter(
        Tg_notif_user.is_active == False
    ).order_by(Tg_notif_user.date_reg.desc()).all()

    # Добавляем информацию о детях
    for user in pending_users:
        user.students_info = get_user_students(db, user.id)

    # Получаем подтвержденных пользователей (последние 10)
    approved_users = db.query(Tg_notif_user).filter(
        Tg_notif_user.is_active == True
    ).order_by(Tg_notif_user.date_reg.desc()).limit(10).all()

    for user in approved_users:
        user.students_info = get_user_students(db, user.id)

    # Получаем статистику
    total_users = db.query(Tg_notif_user).count()
    total_pending = db.query(Tg_notif_user).filter(
        Tg_notif_user.is_active == False
    ).count()
    total_approved = db.query(Tg_notif_user).filter(
        Tg_notif_user.is_active == True
    ).count()

    # Статистика за последние 7 дней
    week_ago = datetime.now() - timedelta(days=7)
    recent_registrations = db.query(Tg_notif_user).filter(
        Tg_notif_user.date_reg >= week_ago
    ).count()

    return templates.TemplateResponse(
        "admin_panel.html",
        {
            "request": request,
            "pending_users": pending_users,
            "approved_users": approved_users,
            "total_pending": total_pending,
            "total_approved": total_approved,
            "total_users": total_users,
            "recent_registrations": recent_registrations
        }
    )


@app.get("/api/users/pending")
async def get_pending_users_api(db: Session = Depends(get_db)):
    """API для получения пользователей, ожидающих подтверждения"""
    users = db.query(Tg_notif_user).filter(
        Tg_notif_user.is_active == False
    ).order_by(Tg_notif_user.date_reg.desc()).all()

    for user in users:
        user.students_info = get_user_students(db, user.id)

    return users


@app.get("/api/users/approved")
async def get_approved_users_api(limit: int = 50, db: Session = Depends(get_db)):
    """API для получения подтвержденных пользователей"""
    users = db.query(Tg_notif_user).filter(
        Tg_notif_user.is_active == True
    ).order_by(Tg_notif_user.date_reg.desc()).limit(limit).all()

    for user in users:
        user.students_info = get_user_students(db, user.id)

    return users


@app.post("/api/users/{user_id}/approve")
async def approve_user(user_id: int, db: Session = Depends(get_db)):
    """API для подтверждения пользователя"""
    user = db.query(Tg_notif_user).filter(Tg_notif_user.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    user.is_active = True
    db.commit()
    db.refresh(user)

    # Логируем действие
    log_action("approve", user_id, user.full_name)

    return {"status": "success", "message": f"Пользователь {user.full_name} подтвержден"}


@app.post("/api/users/{user_id}/reject")
async def reject_user(user_id: int, reason: str = "", db: Session = Depends(get_db)):
    """API для отклонения пользователя"""
    user = db.query(Tg_notif_user).filter(Tg_notif_user.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    user.is_active = False
    db.commit()
    db.refresh(user)

    # Логируем действие
    log_action("reject", user_id, user.full_name, reason)

    return {"status": "success", "message": f"Пользователь {user.full_name} отклонен"}


@app.post("/api/users/{user_id}/toggle-notifications")
async def toggle_notifications(
        user_id: int,
        notification_type: str,
        db: Session = Depends(get_db)
):
    """API для включения/выключения уведомлений"""
    if notification_type not in ["news", "pays", "info"]:
        raise HTTPException(status_code=400, detail="Неверный тип уведомления")

    user = db.query(Tg_notif_user).filter(Tg_notif_user.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    if notification_type == "news":
        user.get_news = not user.get_news
    elif notification_type == "pays":
        user.get_pays_notif = not user.get_pays_notif
    elif notification_type == "info":
        user.get_info_student = not user.get_info_student

    db.commit()
    db.refresh(user)

    return {"status": "success", "message": "Настройки обновлены"}


@app.get("/api/stats")
async def get_stats(db: Session = Depends(get_db)):
    """API для получения статистики"""
    total_users = db.query(Tg_notif_user).count()
    pending_users = db.query(Tg_notif_user).filter(
        Tg_notif_user.is_active == False
    ).count()
    approved_users = db.query(Tg_notif_user).filter(
        Tg_notif_user.is_active == True
    ).count()

    # Статистика за последние 7 дней
    week_ago = datetime.now() - timedelta(days=7)
    recent_registrations = db.query(Tg_notif_user).filter(
        Tg_notif_user.date_reg >= week_ago
    ).count()

    recent_approvals = db.query(Tg_notif_user).filter(
        Tg_notif_user.is_active == True,
        Tg_notif_user.date_reg >= week_ago
    ).count()

    return {
        "total_users": total_users,
        "pending_users": pending_users,
        "approved_users": approved_users,
        "recent_registrations": recent_registrations,
        "recent_approvals": recent_approvals
    }


@app.get("/search/student")
async def search_student(name: str, db: Session = Depends(get_db)):
    """Поиск ученика по имени"""
    if len(name) < 2:
        return []

    students = db.query(Students).filter(
        Students.name.ilike(f"%{name}%"),
        Students.active == True
    ).limit(10).all()

    result = []
    for student in students:
        result.append({
            "id": student.id,
            "name": student.name,
            "birthday": student.birthday.strftime('%d.%m.%Y') if student.birthday else None,
            "active": student.active
        })

    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
