class PromptContextCache:
    """
    Holds cached context data for the assistant.
    Note: With Memory V2, facts are retrieved dynamically via RAG service,
    so this cache is simplified.
    """

    def __init__(self):
        self.summary: str | None = None
        self.needs_summary_refresh: bool = True

    def update_summary(self, summary: str | None):
        """Updates the summary and resets the refresh flag."""
        self.summary = summary
        self.needs_summary_refresh = False

    def require_summary_refresh(self):
        """Sets the flag to require summary refresh on the next check."""
        self.needs_summary_refresh = True
