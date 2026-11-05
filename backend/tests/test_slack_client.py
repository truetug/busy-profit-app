"""Verify employee eligibility independently of Slack transport."""

import pytest

from busy_profit.slack_client import SlackMember


@pytest.mark.parametrize("flag", ["deleted", "is_bot", "is_restricted", "is_ultra_restricted", "is_stranger"])
def test_employee_policy_rejects_nonemployee_accounts(flag: str) -> None:
    """Every disqualifying member flag must deny access.

    Workspace membership alone is not sufficient authorization.
    """
    member = SlackMember.model_validate({"id": "U1", "team_id": "T1", flag: True})
    assert not member.eligible("T1")


def test_employee_policy_requires_matching_workspace() -> None:
    """Missing or external team identifiers fail closed.

    An ordinary active member of the configured workspace is eligible.
    """
    assert SlackMember(id="U1", team_id="T1").eligible("T1")
    assert not SlackMember(id="U1", team_id="T2").eligible("T1")
    assert not SlackMember(id="U1").eligible("T1")
