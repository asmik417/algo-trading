"""Evidence sources for the brain (docs/BRAIN_PLAN.md -> Sources): one module per source, each with
fetch(day) (raises SourceUnavailable with the reason) and pull(day) (never raises; [] on failure).
"""
SOURCES = ("announcements", "deals", "insider", "shareholding", "market", "global_cues", "news", "results")
