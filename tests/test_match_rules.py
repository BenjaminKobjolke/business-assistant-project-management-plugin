"""Tests for match rule DB operations and parsing."""

from __future__ import annotations

from business_assistant_pm.database import PmDatabase
from business_assistant_pm.project_service import ProjectService


class TestMatchRuleDB:
    def test_add_match_rule(self, db: PmDatabase) -> None:
        project = db.add_project("Test")
        rule = db.add_match_rule(project.id, "email_domain", "example.com")
        assert rule.project_id == project.id
        assert rule.rule_type == "email_domain"
        assert rule.value == "example.com"

    def test_add_match_rule_stores_lowercase(self, db: PmDatabase) -> None:
        project = db.add_project("Test")
        rule = db.add_match_rule(project.id, "keyword", "UPPER Case")
        assert rule.value == "upper case"

    def test_add_match_rule_idempotent(self, db: PmDatabase) -> None:
        project = db.add_project("Test")
        r1 = db.add_match_rule(project.id, "email_domain", "example.com")
        r2 = db.add_match_rule(project.id, "email_domain", "example.com")
        assert r1.id == r2.id
        rules = db.get_match_rules_for_project(project.id)
        assert len(rules) == 1

    def test_get_match_rules_for_project(self, db: PmDatabase) -> None:
        p1 = db.add_project("P1")
        p2 = db.add_project("P2")
        db.add_match_rule(p1.id, "email_domain", "a.com")
        db.add_match_rule(p1.id, "keyword", "test")
        db.add_match_rule(p2.id, "email_domain", "b.com")
        rules = db.get_match_rules_for_project(p1.id)
        assert len(rules) == 2

    def test_get_all_match_rules(self, db: PmDatabase) -> None:
        p1 = db.add_project("P1")
        p2 = db.add_project("P2")
        db.add_match_rule(p1.id, "email_domain", "a.com")
        db.add_match_rule(p2.id, "email_domain", "b.com")
        all_rules = db.get_all_match_rules()
        assert len(all_rules) == 2

    def test_delete_match_rule(self, db: PmDatabase) -> None:
        project = db.add_project("Test")
        db.add_match_rule(project.id, "email_domain", "example.com")
        assert db.delete_match_rule(project.id, "email_domain", "example.com")
        assert len(db.get_match_rules_for_project(project.id)) == 0

    def test_delete_match_rule_not_found(self, db: PmDatabase) -> None:
        project = db.add_project("Test")
        assert not db.delete_match_rule(project.id, "email_domain", "nope.com")

    def test_delete_match_rules_for_project(self, db: PmDatabase) -> None:
        project = db.add_project("Test")
        db.add_match_rule(project.id, "email_domain", "a.com")
        db.add_match_rule(project.id, "keyword", "test")
        count = db.delete_match_rules_for_project(project.id)
        assert count == 2
        assert len(db.get_match_rules_for_project(project.id)) == 0


class TestExtractMatchingSection:
    def test_full_section(self) -> None:
        content = (
            "# Project\n\n"
            "**Matching**\n"
            "email_domains: dyadic-agency.com, other.com\n"
            "project_numbers: 260086\n"
            "contacts: user@domain.com\n"
            "keywords: DC Jump n Run, HMI 2026\n"
            "\n**Next Section**\n"
        )
        result = ProjectService.extract_matching_section(content)
        assert result["email_domain"] == ["dyadic-agency.com", "other.com"]
        assert result["project_number"] == ["260086"]
        assert result["contact"] == ["user@domain.com"]
        assert result["keyword"] == ["DC Jump n Run", "HMI 2026"]

    def test_partial_section(self) -> None:
        content = (
            "**Matching**\n"
            "email_domains: example.com\n"
        )
        result = ProjectService.extract_matching_section(content)
        assert result["email_domain"] == ["example.com"]
        assert "keyword" not in result

    def test_empty_section(self) -> None:
        content = "**Matching**\n\n**Other**\n"
        result = ProjectService.extract_matching_section(content)
        assert result == {}

    def test_no_section(self) -> None:
        content = "# Just a normal note\nNo matching section here."
        result = ProjectService.extract_matching_section(content)
        assert result == {}

    def test_unknown_fields_ignored(self) -> None:
        content = (
            "**Matching**\n"
            "email_domains: test.com\n"
            "unknown_field: ignored\n"
        )
        result = ProjectService.extract_matching_section(content)
        assert result == {"email_domain": ["test.com"]}

    def test_whitespace_handling(self) -> None:
        content = (
            "**Matching**\n"
            "  keywords:  word one ,  word two  \n"
        )
        result = ProjectService.extract_matching_section(content)
        assert result["keyword"] == ["word one", "word two"]

    def test_section_at_end_of_file(self) -> None:
        content = (
            "# Header\n\n"
            "**Matching**\n"
            "email_domains: last.com\n"
        )
        result = ProjectService.extract_matching_section(content)
        assert result["email_domain"] == ["last.com"]


class TestBuildMatchingSection:
    def test_build_basic(self, db: PmDatabase) -> None:
        project = db.add_project("Test")
        db.add_match_rule(project.id, "email_domain", "test.com")
        db.add_match_rule(project.id, "keyword", "hello")
        rules = db.get_match_rules_for_project(project.id)
        section = ProjectService.build_matching_section(rules)
        assert "**Matching**" in section
        assert "email_domains: test.com" in section
        assert "keywords: hello" in section

    def test_build_multiple_values(self, db: PmDatabase) -> None:
        project = db.add_project("Test")
        db.add_match_rule(project.id, "email_domain", "a.com")
        db.add_match_rule(project.id, "email_domain", "b.com")
        rules = db.get_match_rules_for_project(project.id)
        section = ProjectService.build_matching_section(rules)
        assert "email_domains: a.com, b.com" in section

    def test_build_empty(self) -> None:
        section = ProjectService.build_matching_section([])
        assert section == "**Matching**"
