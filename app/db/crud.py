from datetime import datetime, timezone
from sqlalchemy.orm import Session
from .models import User, Message


def _utcnow():
    return datetime.now(timezone.utc)


def get_user_by_telegram_id(db: Session, telegram_id: int):
    return db.query(User).filter(User.telegram_id == telegram_id).first()


def get_or_create_user(db: Session, telegram_id: int, username: str = None, first_name: str = None):
    user = get_user_by_telegram_id(db, telegram_id)
    if user:
        changed = False
        if username is not None and user.username != username:
            user.username = username
            changed = True
        if first_name is not None and user.first_name != first_name:
            user.first_name = first_name
            changed = True
        if changed:
            user.updated_at = _utcnow()
            db.commit()
            db.refresh(user)
        return user

    user = User(telegram_id=telegram_id, username=username, first_name=first_name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_all_users(db: Session):
    return db.query(User).all()


def add_message(db: Session, user_id: int, role: str, content: str):
    msg = Message(user_id=user_id, role=role, content=content)
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def get_user_history(db: Session, user_id: int, limit: int = 10):
    return (
        db.query(Message)
        .filter(Message.user_id == user_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
        .all()
    )
