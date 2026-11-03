"""Material lookup tool."""

from __future__ import annotations

from ..catalog import DataCatalog


class MaterialTool:
    def __init__(self, catalog: DataCatalog) -> None:
        self.catalog = catalog

    def get_material(self, material_id: str) -> dict:
        material = self.catalog.materials.get(material_id)
        if material is None:
            return {
                "status": "NOT_FOUND",
                "material_id": material_id,
                "reason": "素材档案不存在，不能据此判断审核通过。",
            }
        authorization = self.catalog.authorizations.get(material_id)
        return {
            "status": "FOUND",
            "material": material.model_dump(mode="json"),
            "authorization": authorization.model_dump(mode="json") if authorization else None,
        }

