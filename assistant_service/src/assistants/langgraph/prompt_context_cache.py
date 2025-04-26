from typing import List, Optional


class PromptContextCache:
    """
    Holds the cached summary and facts, along with refresh flags,
    to be shared between the LangGraphAssistant instance and specific graph nodes.
    """

    def __init__(self):
        self.summary: Optional[str] = None
        self.facts: Optional[List[str]] = None
        self.needs_summary_refresh: bool = True
        self.needs_fact_refresh: bool = True

    def update_summary(self, summary: Optional[str]):
        """Updates the summary and resets the refresh flag."""
        self.summary = summary
        self.needs_summary_refresh = False

    def update_facts(self, facts: Optional[List[str]]):
        """Updates the facts and resets the refresh flag."""
        self.facts = facts
        self.needs_fact_refresh = False

    def require_summary_refresh(self):
        """Sets the flag to require summary refresh on the next check."""
        self.needs_summary_refresh = True

    def require_fact_refresh(self):
        """Sets the flag to require fact refresh on the next check."""
        self.needs_fact_refresh = True
