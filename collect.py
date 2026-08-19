"""收集表 (Collect Form) - 数据收集功能"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import Column, Integer, String, Text, DateTime, Float
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from database import get_db, Base, engine, SessionLocal
from auth import get_current_user, require_editor, User
import json
import hashlib

router = APIRouter(prefix="/api/collect", tags=["收集表"])


class CollectForm(BaseModel):
    id: Optional[int] = None
    title: str
    columns: List[str]
    description: str = ""
    is_active: bool = True
    share_code: str = ""


class CollectSubmission(BaseModel):
    form_id: int
    data: Dict[str, Any]


class CollectFormDB(Base):
    __tablename__ = "collect_forms"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    columns = Column(Text, default="[]")  # JSON array of column names
    description = Column(Text, default="")
    share_code = Column(String(32), unique=True, index=True)
    is_active = Column(Integer, default=1)
    created_by = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class CollectSubmissionDB(Base):
    __tablename__ = "collect_submissions"
    id = Column(Integer, primary_key=True, index=True)
    form_id = Column(Integer, nullable=False)
    data = Column(Text, default="{}")  # JSON
    submitted_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# Create tables
Base.metadata.create_all(bind=engine)


@router.post("/form")
def create_form(
    form: CollectForm,
    db: Session = Depends(get_db),
    user: User = Depends(require_editor),
):
    """Create a new collect form"""
    share_code = hashlib.md5(f"{form.title}{datetime.now().isoformat()}".encode()).hexdigest()[:8]
    db_form = CollectFormDB(
        title=form.title,
        columns=json.dumps(form.columns, ensure_ascii=False),
        description=form.description,
        share_code=share_code,
        created_by=user.id,
    )
    db.add(db_form)
    db.commit()
    db.refresh(db_form)
    return {
        "id": db_form.id,
        "share_code": db_form.share_code,
        "share_url": f"/collect/{db_form.share_code}",
        "message": "表单创建成功",
    }


@router.get("/form/{share_code}")
def get_form_by_code(share_code: str, db: Session = Depends(get_db)):
    """Get form by share code (public)"""
    form = db.query(CollectFormDB).filter(
        CollectFormDB.share_code == share_code,
        CollectFormDB.is_active == 1,
    ).first()
    if not form:
        raise HTTPException(status_code=404, detail="表单不存在或已关闭")
    return {
        "id": form.id,
        "title": form.title,
        "columns": json.loads(form.columns),
        "description": form.description,
    }


@router.post("/submit")
def submit_form(
    submission: CollectSubmission,
    db: Session = Depends(get_db),
):
    """Submit data to a collect form (public)"""
    form = db.query(CollectFormDB).filter(
        CollectFormDB.id == submission.form_id,
        CollectFormDB.is_active == 1,
    ).first()
    if not form:
        raise HTTPException(status_code=404, detail="表单不存在或已关闭")
    
    db_sub = CollectSubmissionDB(
        form_id=submission.form_id,
        data=json.dumps(submission.data, ensure_ascii=False),
    )
    db.add(db_sub)
    db.commit()
    return {"message": "提交成功", "id": db_sub.id}


@router.get("/forms")
def list_forms(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List all forms (auth required)"""
    forms = db.query(CollectFormDB).order_by(CollectFormDB.created_at.desc()).all()
    return [
        {
            "id": f.id,
            "title": f.title,
            "columns": json.loads(f.columns),
            "share_code": f.share_code,
            "is_active": bool(f.is_active),
            "submissions": db.query(CollectSubmissionDB).filter(CollectSubmissionDB.form_id == f.id).count(),
            "created_at": f.created_at.isoformat() if f.created_at else "",
        }
        for f in forms
    ]


@router.get("/submissions/{form_id}")
def get_submissions(
    form_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get submissions for a form"""
    submissions = db.query(CollectSubmissionDB).filter(
        CollectSubmissionDB.form_id == form_id
    ).order_by(CollectSubmissionDB.submitted_at.desc()).all()
    return [
        {
            "id": s.id,
            "data": json.loads(s.data),
            "submitted_at": s.submitted_at.isoformat() if s.submitted_at else "",
        }
        for s in submissions
    ]


@router.put("/form/{form_id}/toggle")
def toggle_form(
    form_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_editor),
):
    """Toggle form active/inactive"""
    form = db.query(CollectFormDB).filter(CollectFormDB.id == form_id).first()
    if not form:
        raise HTTPException(status_code=404, detail="表单不存在")
    form.is_active = 0 if form.is_active else 1
    db.commit()
    return {"is_active": bool(form.is_active), "message": "更新成功"}