"""NEXUS SIGNAL COMMANDER - Research and ranking orchestrator."""

from datetime import datetime
from skills.ai_to_earn.trend_engine.story_selector import discover_winning_stories
from skills.signal_commander.trend_radar import rank_signals
from skills.signal_commander.report_engine import save_report


class SignalCommander:

    def run_research(self):
        print("[SIGNAL COMMANDER] Discovering YouTube stories...")

        stories = discover_winning_stories()

        print("[SIGNAL COMMANDER] Ranking opportunities...")
        ranked = rank_signals(stories or [])

        report = {
            "project": "NEXUS SIGNAL COMMANDER",
            "timestamp": datetime.now().isoformat(),
            "status": "SUCCESS" if ranked else "NO_DATA",
            "stories_found": len(ranked),
            "ranking_method": "NEXUS SIGNAL RADAR",
            "competition_data": "BASELINE ESTIMATE - NOT MEASURED",
            "stories": ranked,
        }

        path = save_report(report)

        print("\n========== SIGNAL RADAR ==========")

        for index, story in enumerate(ranked, 1):
            radar = story["radar"]
            print(
                f"{index}. {story.get('title', 'Untitled')}"
                f" | Score: {radar['score']}"
                f" | Views: {story.get('views', 0)}"
                f" | Niche: {story.get('niche', 'Unknown')}"
            )

        print("\nREPORT:", path)
        return report


if __name__ == "__main__":
    SignalCommander().run_research()
