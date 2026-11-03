"""Deterministic review aggregation tool."""

from __future__ import annotations

from ..catalog import DataCatalog
from ..moderation.mock import MockVideoModerator
from ..schemas import ReviewFinding, ReviewResult


class ReviewTool:
    def __init__(self, catalog: DataCatalog, moderator: MockVideoModerator) -> None:
        self.catalog = catalog
        self.moderator = moderator

    def check_rules(self, material_id: str, platform: str) -> dict:
        material = self.catalog.materials.get(material_id)
        if material is None:
            result = ReviewResult(
                material_id=material_id,
                review_status="UNKNOWN",
                next_action="REQUEST_MISSING_INFO",
                findings=[
                    ReviewFinding(
                        rule_id="MATERIAL-001",
                        category="metadata",
                        severity="high",
                        reason="素材档案不存在",
                    )
                ],
            )
            return result.model_dump(mode="json")

        findings: list[ReviewFinding] = []
        authorization = self.catalog.authorizations.get(material_id)
        if authorization is None or platform not in authorization.scope or authorization.status != "VALID":
            findings.append(
                ReviewFinding(
                    rule_id="R-COPYRIGHT-001",
                    category="copyright",
                    severity="high",
                    reason="缺少覆盖目标平台的有效版权授权",
                    evidence={"platform": platform, "authorization": authorization.model_dump(mode="json") if authorization else None},
                )
            )

        for rule in self.catalog.rules:
            if rule.match_terms and any(term in material.subtitle_text for term in rule.match_terms):
                findings.append(
                    ReviewFinding(
                        rule_id=rule.rule_id,
                        category=rule.category,
                        severity=rule.severity,
                        reason=rule.name,
                        evidence={"matched_text": material.subtitle_text, "match_terms": rule.match_terms},
                    )
                )

        moderation = self.moderator.moderate(material_id)
        evidence = {"provider": self.moderator.provider, "moderation": moderation.model_dump(mode="json")}
        if moderation.status == "ERROR":
            result = ReviewResult(
                material_id=material_id,
                review_status="ERROR",
                findings=findings,
                evidence=evidence,
                next_action="RETRY_REVIEW",
            )
        elif moderation.status == "UNKNOWN":
            result = ReviewResult(
                material_id=material_id,
                review_status="UNKNOWN",
                findings=findings,
                evidence=evidence,
                next_action="REQUEST_MISSING_INFO",
            )
        elif moderation.status == "BLOCKED":
            findings.append(
                ReviewFinding(
                    rule_id="R-VIDEO-001",
                    category="content_safety",
                    severity="high",
                    reason="视频审核返回高风险内容",
                    evidence={"provider": self.moderator.provider, "findings": [item.model_dump(mode="json") for item in moderation.findings or []]},
                )
            )
            result = ReviewResult(
                material_id=material_id,
                review_status="BLOCKED",
                findings=findings,
                evidence=evidence,
                next_action="BLOCK",
            )
        elif findings:
            blocking = any(item.rule_id != "R-COPYRIGHT-001" for item in findings)
            result = ReviewResult(
                material_id=material_id,
                review_status="BLOCKED" if blocking else "PENDING",
                findings=findings,
                evidence=evidence,
                next_action="BLOCK" if blocking else "REQUEST_MISSING_INFO",
            )
        else:
            result = ReviewResult(
                material_id=material_id,
                review_status="PASSED",
                findings=[],
                evidence=evidence,
                next_action="CONTINUE",
            )
        return result.model_dump(mode="json")

