import pytest

from grokbot.agents.checker import CheckerAgent
from grokbot.agents.llm import ScriptedLlmClient
from grokbot.config import LlmConfig
from grokbot.models import (
    Analysis,
    AuditResult,
    NarrativeScore,
    ScoreBreakdown,
    TimingMood,
    Token,
)


async def _run(client: ScriptedLlmClient, token: Token) -> None:
    agent = CheckerAgent(client, LlmConfig(checker_model="grok-4"))
    return await agent.run(
        token,
        Analysis(),
        AuditResult(passed=True),
        NarrativeScore(narrative_fit=0.9, virality=0.9),
        TimingMood(mood=0.7),
        ScoreBreakdown(total=0.8, components={}, threshold=0.62, passed=True),
    )


@pytest.mark.asyncio
async def test_checker_parse_error_is_fail_closed(good_token: Token):
    client = ScriptedLlmClient(default="this is not json at all")
    result = await _run(client, good_token)
    assert result.approve is False
    assert result.parse_error is True
    assert "parse" in result.reasons_not_to_buy[0]


@pytest.mark.asyncio
async def test_checker_transport_error_is_fail_closed(good_token: Token):
    class Boom(ScriptedLlmClient):
        async def complete(self, **kwargs):
            raise RuntimeError("network down")

    result = await _run(Boom(), good_token)
    assert result.approve is False
    assert result.parse_error is True


@pytest.mark.asyncio
async def test_checker_explicit_false(good_token: Token):
    client = ScriptedLlmClient(default='{"approve": false, "reasons_not_to_buy": ["insider"]}')
    result = await _run(client, good_token)
    assert result.approve is False
    assert "insider" in result.reasons_not_to_buy


@pytest.mark.asyncio
async def test_checker_can_approve(good_token: Token):
    client = ScriptedLlmClient(default='{"approve": true, "reasons_not_to_buy": []}')
    result = await _run(client, good_token)
    assert result.approve is True


@pytest.mark.asyncio
async def test_auditor_parse_error_is_pessimistic_reject(good_token: Token):
    from grokbot.agents.auditor import AuditorAgent

    client = ScriptedLlmClient(default="NOPE")
    result = await AuditorAgent(client, LlmConfig()).run(good_token, Analysis())
    assert result.passed is False
    assert result.parse_error is True
