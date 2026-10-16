class InvalidConfigurationError(Exception):
    def __init__(self, reason: str, profile: str | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.profile = profile
