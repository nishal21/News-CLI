class SentimentAnalyzer:
    POSITIVE = [
        "good",
        "great",
        "best",
        "success",
        "win",
        "winning",
        "love",
        "agree",
        "improve",
        "growth",
        "gain",
        "up",
        "rise",
        "boom",
        "record",
        "praise",
        "happy",
        "celebrate",
        "breakthrough",
        "approved",
        "support",
        "help",
        "benefit",
        "progress",
        "positive",
        "strong",
        "recovery",
        "surge",
        "soar",
        "optimism",
        "deal",
        "peace",
        "launch",
        "expand",
        "profit",
    ]
    NEGATIVE = [
        "bad",
        "worst",
        "fail",
        "loss",
        "crash",
        "kill",
        "death",
        "dead",
        "deadly",
        "war",
        "attack",
        "conflict",
        "crisis",
        "scandal",
        "corruption",
        "fraud",
        "accident",
        "disaster",
        "tragedy",
        "hate",
        "disagree",
        "down",
        "drop",
        "fall",
        "decline",
        "ban",
        "sanction",
        "threat",
        "danger",
        "fear",
        "concern",
        "negative",
        "weak",
        "collapse",
        "plunge",
        "pessimism",
        "arrest",
        "charged",
        "accused",
        "sue",
        "lawsuit",
        "fire",
        "layoff",
        "cut",
        "reduce",
    ]

    def analyze(self, text):
        text = text.lower()
        words = text.split()
        pos = sum(1 for w in words if w in self.POSITIVE)
        neg = sum(1 for w in words if w in self.NEGATIVE)
        if pos > neg:
            return "positive", pos, neg
        if neg > pos:
            return "negative", pos, neg
        return "neutral", pos, neg


def estimate_reading_time(text, wpm=238):
    words = len(text.split())
    minutes = words / wpm if wpm else 0
    if minutes < 1:
        return f"{max(1, int(minutes * 60))}s read"
    return f"{int(minutes)}m {max(0, int((minutes - int(minutes)) * 60))}s read"
