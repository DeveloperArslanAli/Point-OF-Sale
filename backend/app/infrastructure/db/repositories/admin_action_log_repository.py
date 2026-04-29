from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.auth.admin_action_log import AdminActionLog
from app.infrastructure.db.models.auth.admin_action_log_model import AdminActionLogModel
from app.shared.pagination import PageParams


class AdminActionLogRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def add(self, log: AdminActionLog) -> None:
        model = AdminActionLogModel(
            id=log.id,
            actor_user_id=log.actor_user_id,
            target_user_id=log.target_user_id,
            action=log.action,
            details=log.details,
            trace_id=log.trace_id,
            created_at=log.created_at,
            # Enhanced audit fields
            category=log.category,
            severity=log.severity,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            before_state=log.before_state,
            after_state=log.after_state,
            ip_address=log.ip_address,
            user_agent=log.user_agent,
        )
        self._session.add(model)
        await self._session.flush()

    async def search(
        self,
        *,
        actor_user_id: str | None = None,
        target_user_id: str | None = None,
        action: str | None = None,
        category: str | None = None,
        severity: str | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        params: PageParams,
    ) -> tuple[list[AdminActionLog], int]:
        stmt = select(AdminActionLogModel)
        count_stmt: Select[Any] = select(func.count(AdminActionLogModel.id))
        conditions = []
        if actor_user_id:
            conditions.append(AdminActionLogModel.actor_user_id == actor_user_id)
        if target_user_id:
            conditions.append(AdminActionLogModel.target_user_id == target_user_id)
        if action:
            conditions.append(AdminActionLogModel.action == action)
        if category:
            conditions.append(AdminActionLogModel.category == category)
        if severity:
            conditions.append(AdminActionLogModel.severity == severity)
        if entity_type:
            conditions.append(AdminActionLogModel.entity_type == entity_type)
        if entity_id:
            conditions.append(AdminActionLogModel.entity_id == entity_id)
        if start:
            conditions.append(AdminActionLogModel.created_at >= start)
        if end:
            conditions.append(AdminActionLogModel.created_at <= end)

        if conditions:
            stmt = stmt.where(*conditions)
            count_stmt = count_stmt.where(*conditions)

        stmt = stmt.order_by(AdminActionLogModel.created_at.desc()).offset(params.offset).limit(params.limit)

        rows = await self._session.execute(stmt)
        models = rows.scalars().all()
        items = [self._to_domain(model) for model in models]

        total_result = await self._session.execute(count_stmt)
        total = total_result.scalar_one()
        return items, total

    async def get_security_events(
        self,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        params: PageParams,
    ) -> tuple[list[AdminActionLog], int]:
        """Get security-related audit events (high/critical severity)."""
        return await self.search(
            category="security",
            start=start,
            end=end,
            params=params,
        )

    @staticmethod
    def _to_domain(model: AdminActionLogModel) -> AdminActionLog:
        return AdminActionLog(
            id=model.id,
            actor_user_id=model.actor_user_id,
            target_user_id=model.target_user_id,
            action=model.action,
            details=model.details or {},
            trace_id=model.trace_id,
            created_at=model.created_at,
            category=model.category,
            severity=model.severity,
            entity_type=model.entity_type,
            entity_id=model.entity_id,
            before_state=model.before_state or {},
            after_state=model.after_state or {},
            ip_address=model.ip_address,
            user_agent=model.user_agent,
        )
