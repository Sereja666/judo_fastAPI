from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from datetime import datetime
from typing import List, Optional
import json
import os

from database.models import Students_parents, Students
from . import models
from . import schemas


def get_pending_users(db: Session) -> List[models.User]:
    """Получить пользователей, ожидающих подтверждения"""
    users = db.query(models.User).filter(
        models.User.is_active == False
    ).order_by(models.User.date_reg.desc()).all()

    # Добавляем информацию о детях для каждого пользователя
    for user in users:
        user.students_info = get_user_students(db, user.id)

    return users


def get_approved_users(db: Session, limit: int = 50) -> List[models.User]:
    """Получить подтвержденных пользователей"""
    users = db.query(models.User).filter(
        models.User.is_active == True
    ).order_by(models.User.date_reg.desc()).limit(limit).all()

    for user in users:
        user.students_info = get_user_students(db, user.id)

    return users


def get_rejected_users(db: Session, limit: int = 50) -> List[models.User]:
    """Получить отклоненных пользователей"""
    # Проверяем, есть ли поле rejection_reason в модели
    if hasattr(models.User, 'rejection_reason'):
        users = db.query(models.User).filter(
            models.User.rejection_reason != None,
            models.User.rejection_reason != ''
        ).order_by(models.User.date_reg.desc()).limit(limit).all()
    else:
        # Если поля нет, используем только is_active == False
        users = db.query(models.User).filter(
            models.User.is_active == False
        ).order_by(models.User.date_reg.desc()).limit(limit).all()

    for user in users:
        user.students_info = get_user_students(db, user.id)

    return users


def get_user_students(db: Session, user_id: int) -> List:
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
                "active": student.active
            })

    return students_info


def approve_user(db: Session, user_id: int) -> Optional[models.User]:
    """Подтвердить пользователя"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user:
        user.is_active = True
        db.commit()
        db.refresh(user)

        # Логируем действие
        log_action("approve", user_id, user.full_name)

        return user
    return None


def reject_user(db: Session, user_id: int, reason: str = "") -> Optional[models.User]:
    """Отклонить пользователя"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user:
        user.is_active = False
        if hasattr(user, 'rejection_reason'):
            user.rejection_reason = reason
        db.commit()
        db.refresh(user)

        # Логируем действие
        log_action("reject", user_id, user.full_name, reason)

        return user
    return None


def toggle_user_notification(db: Session, user_id: int, notification_type: str) -> Optional[models.User]:
    """Включить/выключить уведомления пользователя"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user:
        if notification_type == "news":
            user.get_news = not user.get_news
        elif notification_type == "pays":
            user.get_pays_notif = not user.get_pays_notif
        elif notification_type == "info":
            user.get_info_student = not user.get_info_student

        db.commit()
        db.refresh(user)
        return user
    return None


def get_registration_stats(db: Session) -> dict:
    """Получить статистику по регистрациям"""
    total_users = db.query(models.User).count()

    # Вместо rejection_reason используем is_active
    pending_users = db.query(models.User).filter(
        models.User.is_active == False
    ).count()

    approved_users = db.query(models.User).filter(
        models.User.is_active == True
    ).count()

    # Для отклоненных используем ту же логику, что и для pending
    # В реальном приложении нужно добавить поле rejection_reason
    rejected_users = 0

    # Статистика за последние 7 дней
    from datetime import timedelta
    week_ago = datetime.now() - timedelta(days=7)

    recent_registrations = db.query(models.User).filter(
        models.User.date_reg >= week_ago
    ).count()

    recent_approvals = db.query(models.User).filter(
        models.User.is_active == True,
        models.User.date_reg >= week_ago
    ).count()

    return {
        "total_users": total_users,
        "pending_users": pending_users,
        "approved_users": approved_users,
        "rejected_users": rejected_users,
        "recent_registrations": recent_registrations,
        "recent_approvals": recent_approvals
    }


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


