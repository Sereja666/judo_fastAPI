from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import os

from app_notif.database import get_db
from database.models import Students_parents, Students, Tg_notif_user
from config import templates

router = APIRouter(prefix="/admin", tags=["telegram-registrations"])


# ====================  Вспомогательные функции ====================

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

@router.get("/registrations", response_class=HTMLResponse)
async def admin_panel(request: Request, db: Session = Depends(get_db)):
    """Главная страница админ-панели"""
    user_info = getattr(request.state, 'user', None)

    # Проверка авторизации и прав (добавьте свою логику проверки ролей)
    if not user_info or not user_info.get("authenticated"):
        return RedirectResponse(url="/")  # Или на страницу логина

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
        "tg_membership.html",
        {
            "request": request,
            "pending_users": pending_users,
            "approved_users": approved_users,
            "total_pending": total_pending,
            "total_approved": total_approved,
            "total_users": total_users,
            "recent_registrations": recent_registrations,
            "user_authenticated": user_info.get("authenticated", False),
            "username": user_info.get("username")
        }
    )


@router.get("/users/pending")
async def get_pending_users_api(db: Session = Depends(get_db)):
    """API для получения пользователей, ожидающих подтверждения"""
    users = db.query(Tg_notif_user).filter(
        Tg_notif_user.is_active == False
    ).order_by(Tg_notif_user.date_reg.desc()).all()

    for user in users:
        user.students_info = get_user_students(db, user.id)

    return users


@router.get("/users/approved")
async def get_approved_users_api(limit: int = 50, db: Session = Depends(get_db)):
    """API для получения подтвержденных пользователей"""
    users = db.query(Tg_notif_user).filter(
        Tg_notif_user.is_active == True
    ).order_by(Tg_notif_user.date_reg.desc()).limit(limit).all()

    for user in users:
        user.students_info = get_user_students(db, user.id)

    return users


@router.post("/users/{user_id}/approve")
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


@router.post("/users/{user_id}/reject")
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


@router.post("/users/{user_id}/toggle-notifications")
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


@router.get("/stats")
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


@router.get("/search/student")
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

#
@router.get("/users/approved-page", response_class=HTMLResponse)
async def approved_users_page(request: Request, db: Session = Depends(get_db)):
    """Страница со всеми подтвержденными пользователями"""
    user_info = getattr(request.state, 'user', None)

    if not user_info or not user_info.get("authenticated"):
        return RedirectResponse(url="/")

    # Получаем всех подтвержденных пользователей
    approved_users = db.query(Tg_notif_user).filter(
        Tg_notif_user.is_active == True
    ).order_by(Tg_notif_user.full_name).all()

    # Для каждого пользователя получаем информацию о детях
    users_with_students = []
    for user in approved_users:
        students_info = get_user_students(db, user.id)

        # Если нет детей, все равно включаем пользователя
        if not students_info:
            users_with_students.append({
                "user": user,
                "students": []
            })
        else:
            for student in students_info:
                users_with_students.append({
                    "user": user,
                    "student": student
                })

    return templates.TemplateResponse(
        "tg_membership_approved.html",
        {
            "request": request,
            "users_with_students": users_with_students,
            "user_authenticated": user_info.get("authenticated", False),
            "username": user_info.get("username")
        }
    )


@router.delete("/users/{user_id}/student/{student_id}")
async def remove_student_from_user(
        user_id: int,
        student_id: int,
        db: Session = Depends(get_db)
):
    """Удалить связь между пользователем и учеником"""
    # Находим связь
    relation = db.query(Students_parents).filter(
        Students_parents.parents == user_id,
        Students_parents.student == student_id
    ).first()

    if not relation:
        raise HTTPException(status_code=404, detail="Связь не найдена")

    # Удаляем связь
    db.delete(relation)
    db.commit()

    # Проверяем, есть ли у пользователя другие дети
    remaining_children = db.query(Students_parents).filter(
        Students_parents.parents == user_id
    ).count()

    # Если детей нет, можно предложить удалить пользователя
    user_info = db.query(Tg_notif_user).filter(
        Tg_notif_user.id == user_id
    ).first()

    return {
        "status": "success",
        "message": f"Связь удалена",
        "remaining_children": remaining_children,
        "user_name": user_info.full_name if user_info else "Пользователь"
    }