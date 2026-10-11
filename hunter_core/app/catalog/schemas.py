"""Схемы справочника §6."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class TopicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    title: str


class SpecializationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    title: str
    topics: list[TopicOut]


class GradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    slug: str
    title: str
    lo: float
    hi: float
    description: str


class ThetaScaleOut(BaseModel):
    min: float
    max: float


class CatalogOut(BaseModel):
    specializations: list[SpecializationOut]
    grades: list[GradeOut]
    theta_scale: ThetaScaleOut
