from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from .db_models import Case as CaseModel, CaseComment as CaseCommentModel
from .db_models import User as UserModel, UserProfile
from .models import Case, CaseComment, CaseCreate
from .storage import CaseStore


class DatabaseCaseStore(CaseStore):
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def _get_creator_public_name(self, session: Session, uid: str) -> Optional[str]:
        return (
            session.query(UserProfile.public_name)
            .filter(UserProfile.uid == uid)
            .scalar()
        )

    def _to_case(self, db_case: CaseModel, creator_public_name: Optional[str] = None) -> Case:
        return Case(
            id=db_case.id,
            brand=db_case.brand or "unknown",
            model=db_case.model or "unknown",
            series=db_case.series,
            error_code=db_case.error_code,
            symptom=db_case.symptom or db_case.description or "N/A",
            checks_done=db_case.checks_done,
            diagnosis=db_case.diagnosis,
            status=db_case.status,
            source=db_case.source or "ai",
            matched_case_id=db_case.matched_case_id,
            manual_path=db_case.manual_path,
            manual_meta=db_case.manual_meta,
            tags=db_case.tags or [],
            created_at=db_case.created_at,
            updated_at=db_case.updated_at,
            resolution_note=db_case.resolution_note,
            resolved_at=db_case.resolved_at,
            created_by_uid=db_case.created_by_uid,
            closed_at=db_case.closed_at,
            title=db_case.title,
            description=db_case.description,
            creator_public_name=creator_public_name,
        )

    def _ensure_user(self, session: Session, uid: str) -> UserModel:
        user = session.query(UserModel).filter(UserModel.uid == uid).one_or_none()
        if user:
            return user

        user = UserModel(uid=uid, created_at=datetime.utcnow())
        session.add(user)
        session.flush()
        return user

    def create_case(self, data: CaseCreate) -> Case:
        with self.session_factory() as session:
            user = self._ensure_user(session, data.created_by_uid)
            now = datetime.utcnow()
            db_case = CaseModel(
                title=data.title,
                description=data.description,
                status=data.status,
                created_by_uid=user.uid,
                created_at=now,
                updated_at=now,
                brand=data.brand,
                model=data.model,
                series=data.series,
                error_code=data.error_code,
                symptom=data.symptom,
                checks_done=data.checks_done,
                diagnosis=data.diagnosis,
                source=data.source,
                matched_case_id=data.matched_case_id,
                manual_path=data.manual_path,
                manual_meta=data.manual_meta,
                tags=data.tags or [],
            )
            session.add(db_case)
            session.commit()
            session.refresh(db_case)
            creator_public_name = self._get_creator_public_name(session, db_case.created_by_uid)
            return self._to_case(db_case, creator_public_name)

    def list_cases(self, status: Optional[str] = None, limit: int = 200) -> List[Case]:
        with self.session_factory() as session:
            query = (
                session.query(
                    CaseModel,
                    UserProfile.public_name.label("creator_public_name"),
                )
                .outerjoin(UserProfile, CaseModel.created_by_uid == UserProfile.uid)
            )
            if status:
                query = query.filter(CaseModel.status == status)
            cases = (
                query.order_by(CaseModel.id.desc())
                .limit(max(1, limit))
                .all()
            )
            return [self._to_case(c, public_name) for c, public_name in cases]

    def get_case(self, case_id: int) -> Optional[Case]:
        with self.session_factory() as session:
            db_case = (
                session.query(
                    CaseModel,
                    UserProfile.public_name.label("creator_public_name"),
                )
                .outerjoin(UserProfile, CaseModel.created_by_uid == UserProfile.uid)
                .filter(CaseModel.id == case_id)
                .one_or_none()
            )
            if not db_case:
                return None
            case, public_name = db_case
            return self._to_case(case, public_name)

    def find_resolved_by_key(
        self,
        brand: str,
        model: str,
        series: Optional[str],
        error_code: Optional[str],
    ) -> Optional[Case]:
        if not brand or not model:
            return None

        with self.session_factory() as session:
            query = (
                session.query(
                    CaseModel,
                    UserProfile.public_name.label("creator_public_name"),
                )
                .outerjoin(UserProfile, CaseModel.created_by_uid == UserProfile.uid)
                .filter(
                    CaseModel.status == "resolved",
                    CaseModel.brand.ilike(brand),
                    CaseModel.model.ilike(model),
                )
            )
            if series:
                query = query.filter(CaseModel.series.ilike(series))
            if error_code:
                query = query.filter(CaseModel.error_code.ilike(error_code))

            db_case = query.order_by(CaseModel.id.desc()).first()
            if db_case:
                case_row, creator_public_name = db_case
                return self._to_case(case_row, creator_public_name)
            return None

    def update_case_diagnosis_data(
        self,
        case_id: int,
        *,
        diagnosis: Optional[str],
        source: str,
        matched_case_id: Optional[int] = None,
        manual_path: Optional[str] = None,
        manual_meta: Optional[dict] = None,
    ) -> Optional[Case]:
        with self.session_factory() as session:
            db_case = session.get(CaseModel, case_id)
            if not db_case:
                return None

            db_case.diagnosis = diagnosis
            db_case.source = source
            db_case.matched_case_id = matched_case_id
            db_case.manual_path = manual_path
            db_case.manual_meta = manual_meta
            db_case.touch_updated_at()
            session.commit()
            session.refresh(db_case)
            creator_public_name = self._get_creator_public_name(session, db_case.created_by_uid)
            return self._to_case(db_case, creator_public_name)

    def update_status(self, case_id: int, status: str) -> Optional[Case]:
        with self.session_factory() as session:
            db_case = session.get(CaseModel, case_id)
            if not db_case:
                return None

            db_case.set_status(status)
            session.commit()
            session.refresh(db_case)
            creator_public_name = self._get_creator_public_name(session, db_case.created_by_uid)
            return self._to_case(db_case, creator_public_name)

    def resolve_case(self, case_id: int, resolution_note: str) -> Optional[Case]:
        with self.session_factory() as session:
            db_case = session.get(CaseModel, case_id)
            if not db_case:
                return None

            db_case.mark_resolved((resolution_note or "").strip())
            session.commit()
            session.refresh(db_case)
            creator_public_name = self._get_creator_public_name(session, db_case.created_by_uid)
            return self._to_case(db_case, creator_public_name)

    def update_case(self, case_id: int, updates: dict) -> Optional[Case]:
        allowed_fields = {
            "title",
            "description",
            "brand",
            "model",
            "series",
            "error_code",
            "symptom",
            "checks_done",
        }

        with self.session_factory() as session:
            db_case = session.get(CaseModel, case_id)
            if not db_case:
                return None

            changed = False
            for field, value in updates.items():
                if field in allowed_fields:
                    setattr(db_case, field, value)
                    changed = True

            if not changed:
                return self._to_case(db_case)

            db_case.touch_updated_at()
            session.commit()
            session.refresh(db_case)

            creator_public_name = self._get_creator_public_name(session, db_case.created_by_uid)

            return self._to_case(db_case, creator_public_name)

    def _to_comment(self, db_comment: CaseCommentModel) -> CaseComment:
        return CaseComment(
            id=db_comment.id,
            case_id=db_comment.case_id,
            author_uid=db_comment.author_uid,
            author_public_name=db_comment.author_public_name,
            body=db_comment.body,
            created_at=db_comment.created_at,
        )

    def create_comment(
        self, case_id: int, author_uid: str, body: str
    ) -> Optional[CaseComment]:
        with self.session_factory() as session:
            db_case = session.get(CaseModel, case_id)
            if not db_case:
                return None

            profile = (
                session.query(UserProfile)
                .filter(UserProfile.uid == author_uid)
                .one_or_none()
            )
            comment = CaseCommentModel(
                case_id=case_id,
                author_uid=author_uid,
                author_public_name=profile.public_name if profile else None,
                body=body,
            )
            session.add(comment)
            session.commit()
            session.refresh(comment)
            return self._to_comment(comment)

    def list_comments(self, case_id: int) -> Optional[list[CaseComment]]:
        with self.session_factory() as session:
            case_exists = session.query(CaseModel.id).filter(CaseModel.id == case_id).first()
            if not case_exists:
                return None

            comments = (
                session.query(CaseCommentModel)
                .filter(CaseCommentModel.case_id == case_id)
                .order_by(CaseCommentModel.created_at.asc(), CaseCommentModel.id.asc())
                .all()
            )
            return [self._to_comment(c) for c in comments]
