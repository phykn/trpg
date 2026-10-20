import sys
from pathlib import Path

QA = Path(__file__).resolve().parent
REPO = QA.parent
RUNS = REPO / "qa_test" / "runs"      # recordings stay out of git


def checkout() -> Path:
    """`--root DIR` runs another checkout's server and stories, so a baseline can run beside edits."""
    return Path(sys.argv[sys.argv.index("--root") + 1]).resolve() if "--root" in sys.argv else REPO


sys.path.insert(0, str(checkout() / "server"))


def story(stories: dict):
    """`--story ID`, else the only story there is."""
    if "--story" in sys.argv:
        return stories[sys.argv[sys.argv.index("--story") + 1]]
    if len(stories) != 1:
        raise SystemExit(f"--story is one of {sorted(stories)}")
    return next(iter(stories.values()))


def models():
    """The models `run_api.py --local` would use, so a bench never tests a model the game does not run."""
    from run_api import local_settings
    from src.models.decision import DecisionClient
    from src.models.llm import LLMClient
    s = local_settings()
    return (DecisionClient(s.decision_base_url, model=s.decision_model, api_key=s.decision_api_key),
            LLMClient(s.llm_base_url, model=s.llm_model))
