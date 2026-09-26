"""Expected failures that can be explained without a Foundry crash report."""


class ExportCancelled(ValueError):
    """Export cannot continue with the supplied asset or export settings."""
