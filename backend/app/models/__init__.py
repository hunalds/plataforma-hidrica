"""Importa todos los modelos para que Base.metadata los conozca (Alembic, pruebas)."""

from app.models.audit import AuditLog
from app.models.base import Base
from app.models.measurement import BatchStatus, DailyMeasurement, ImportBatch, MeasurementSource, VolumeSource
from app.models.reservoir import ElevationCurve, ElevationCurvePoint, Reservoir, Threshold
from app.models.satellite import Job, JobStatus, SatelliteObservation, Scope
from app.models.user import PasswordResetToken, RefreshToken, Role, User, user_reservoir

__all__ = [
    "AuditLog",
    "Base",
    "BatchStatus",
    "DailyMeasurement",
    "ImportBatch",
    "MeasurementSource",
    "VolumeSource",
    "ElevationCurve",
    "Job",
    "JobStatus",
    "SatelliteObservation",
    "Scope",
    "ElevationCurvePoint",
    "PasswordResetToken",
    "RefreshToken",
    "Reservoir",
    "Role",
    "Threshold",
    "User",
    "user_reservoir",
]
