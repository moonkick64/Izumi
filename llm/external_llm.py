"""External LLM integration via LiteLLM.

Responsibility: given user-approved function summaries, find similar OSS.
Only user-approved summaries (never raw source code) are sent externally.
"""

from __future__ import annotations

from litellm import completion  # type: ignore[import]

from analyzer.models import Component
from .prompts import format_oss_similarity_prompt


class ExternalLLM:
    """Wrapper around an external LLM provider via LiteLLM."""

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        timeout: int = 60,
    ) -> None:
        self.model = model
        self.timeout = timeout

    def find_similar_oss(self, summaries: list[str]) -> str:
        """Query the external LLM with *summaries* and return its response.

        Args:
            summaries: User-approved natural-language function summaries.
                Raw source code must NOT appear here.

        Returns:
            Raw LLM response text, presented to the user as an unverified hint.
            Returns empty string if *summaries* is empty.
            Returns ``[ERROR] …`` on LLM call failure.
        """
        if not summaries:
            return ""

        messages = format_oss_similarity_prompt(summaries)
        try:
            response = completion(
                model=self.model,
                messages=messages,
                timeout=self.timeout,
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            return f"[ERROR] External LLM call failed: {exc}"

    def analyse_component(self, component: Component) -> Component:
        """Send approved function summaries from *component* to the external LLM.

        Only summaries where ``FunctionSummary.approved == True`` are sent.
        Sets ``component.oss_hint`` to the LLM response and returns the component.

        Args:
            component: A component that has been through local-LLM summarisation
                and user review.

        Returns:
            The same *component* with ``oss_hint`` set.
        """
        approved_summaries = [
            fs.summary
            for fs in component.function_summaries
            if fs.approved and fs.summary and not fs.summary.startswith("[ERROR]")
        ]

        component.oss_hint = self.find_similar_oss(approved_summaries)
        return component
