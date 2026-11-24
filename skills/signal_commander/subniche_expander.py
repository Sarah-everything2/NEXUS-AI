"""NEXUS domain-aware sub-niche extraction and evidence collection."""

import asyncio
import re
from ddgs import DDGS

MAX_RESULTS = 8

DOMAIN_PATTERNS = {
    "artificial intelligence": {
        "AI Agents & Autonomous Agents": [r"\bai agents?\b", r"\bagentic ai\b", r"\bautonomous agents?\b"],
        "Generative AI": [r"\bgenerative ai\b", r"\bai content generation\b"],
        "AI Video Generation": [r"\bai video\b", r"\bvideo generation\b"],
        "AI Coding Assistants": [r"\bai coding\b", r"\bcode assistants?\b"],
        "AI Robotics": [r"\bai robotics?\b", r"\brobotic ai\b"],
        "Small Language Models": [r"\bsmall language models?\b", r"\bslms?\b"],
        "AI Cybersecurity": [r"\bai cybersecurity\b", r"\bai security\b"],
        "AI Infrastructure & Chips": [r"\bai chips?\b", r"\bai infrastructure\b", r"\bai computing\b"],
        "AI Healthcare": [r"\bai healthcare\b", r"\bmedical ai\b"],
        "AI Automation": [r"\bai automation\b", r"\bintelligent automation\b"],
        "Computer Vision AI": [r"\bcomputer vision\b", r"\bvisual ai\b"],
        "AI Voice & Audio": [r"\bai voice\b", r"\bai audio\b", r"\bspeech synthesis\b"],
    },
    "cryptocurrency": {
        "Bitcoin & Bitcoin Ecosystem": [r"\bbitcoin\b", r"\bbtc\b"],
        "Ethereum & Layer 2": [r"\bethereum\b", r"\blayer.?2\b", r"\brollups?\b"],
        "Decentralized Finance (DeFi)": [r"\bdefi\b", r"\bdecentralized finance\b"],
        "Stablecoins": [r"\bstablecoins?\b"],
        "Crypto Regulation": [r"\bcrypto regulation\b", r"\bcrypto legislation\b"],
        "Crypto Exchanges": [r"\bcrypto exchanges?\b"],
        "Crypto Mining": [r"\bcrypto mining\b", r"\bbitcoin mining\b"],
        "Meme Coins": [r"\bmeme coins?\b"],
        "Tokenization & Real-World Assets": [r"\btokenization\b", r"\breal.world assets?\b", r"\brwa\b"],
        "Web3 & Decentralized Applications": [r"\bweb3\b", r"\bdapps?\b"],
    },
    "mining": {
        "Bitcoin & Cryptocurrency Mining": [r"\bbitcoin mining\b", r"\bcrypto mining\b"],
        "ASIC Mining Hardware": [r"\basi[c]? miners?\b", r"\bmining hardware\b"],
        "Mining Pools": [r"\bmining pools?\b"],
        "Cloud Mining": [r"\bcloud mining\b"],
        "Proof of Work Networks": [r"\bproof.of.work\b"],
        "Mining Energy & Electricity": [r"\bmining energy\b", r"\bmining electricity\b"],
        "Hashrate & Mining Difficulty": [r"\bhashrate\b", r"\bmining difficulty\b"],
        "Gold & Precious Metals Mining": [r"\bgold mining\b", r"\bprecious metals mining\b"],
        "Mineral Exploration": [r"\bmineral exploration\b", r"\bmineral discovery\b"],
        "Mining Automation & Robotics": [r"\bmining automation\b", r"\bmining robotics\b"],
    },
    "finance": {
        "Stock Market & Equities": [r"\bstock market\b", r"\bequities\b", r"\bstocks\b"],
        "Forex & Currency Markets": [r"\bforex\b", r"\bcurrency markets?\b"],
        "Commodities & Gold": [r"\bcommodit(y|ies)\b", r"\bgold prices?\b"],
        "Personal Finance": [r"\bpersonal finance\b", r"\bfinancial planning\b"],
        "Investment & Asset Management": [r"\binvestment management\b", r"\bportfolio management\b"],
        "Central Banks & Interest Rates": [r"\bcentral banks?\b", r"\binterest rates?\b"],
        "Fintech & Digital Payments": [r"\bfintech\b", r"\bdigital payments?\b"],
        "Banking & Financial Technology": [r"\bbanking technology\b", r"\bdigital banking\b"],
    },
    "football": {
        "Football Transfers": [r"\btransfers?\b", r"\btransfer window\b"],
        "Football Tactics & Analysis": [r"\btactics\b", r"\bmatch analysis\b"],
        "Football Business & Finance": [r"\bfootball finance\b", r"\bclub revenues?\b"],
        "Football Youth Development": [r"\byouth academ(y|ies)\b", r"\byouth development\b"],
        "Women's Football": [r"\bwomen.s football\b", r"\bwomen.s soccer\b"],
        "Football Technology & VAR": [r"\bvar\b", r"\bgoal.line technology\b"],
        "Football Competitions": [r"\bchampions league\b", r"\bpremier league\b", r"\bworld cup\b"],
    },
    "basketball": {
        "NBA News & Analysis": [r"\bnba\b"],
        "Basketball Transfers & Trades": [r"\btrade rumors?\b", r"\bbasketball transfers?\b"],
        "Basketball Analytics": [r"\bbasketball analytics\b", r"\bplayer efficiency\b"],
        "Women's Basketball": [r"\bwomen.s basketball\b", r"\bwnba\b"],
        "College Basketball": [r"\bcollege basketball\b", r"\bncaa basketball\b"],
        "Basketball Training": [r"\bbasketball training\b", r"\bskills development\b"],
    },
    "engineering": {
        "Robotics & Automation": [r"\brobotics?\b", r"\bindustrial automation\b"],
        "Civil & Structural Engineering": [r"\bcivil engineering\b", r"\bstructural engineering\b"],
        "Mechanical Engineering": [r"\bmechanical engineering\b"],
        "Electrical & Electronics Engineering": [r"\belectrical engineering\b", r"\belectronics engineering\b"],
        "Aerospace Engineering": [r"\baerospace engineering\b"],
        "Renewable Energy Engineering": [r"\brenewable energy\b", r"\bsolar engineering\b"],
        "Materials Science": [r"\bmaterials science\b", r"\badvanced materials\b"],
    },
    "technology": {
        "Semiconductors & Chips": [r"\bsemiconductors?\b", r"\bcomputer chips?\b"],
        "Cybersecurity": [r"\bcybersecurity\b", r"\bdata breaches?\b"],
        "Cloud Computing": [r"\bcloud computing\b"],
        "Quantum Computing": [r"\bquantum computing\b"],
        "Consumer Electronics": [r"\bconsumer electronics\b"],
        "Internet of Things": [r"\binternet of things\b", r"\biot\b"],
        "Software Development": [r"\bsoftware development\b"],
    },
    "politics": {
        "Elections & Campaigns": [r"\belections?\b", r"\bcampaigns?\b"],
        "Government Policy": [r"\bgovernment polic(y|ies)\b", r"\bpublic polic(y|ies)\b"],
        "International Relations": [r"\binternational relations\b", r"\bdiplomacy\b"],
        "Geopolitics": [r"\bgeopolitics\b", r"\bgeopolitical\b"],
        "Political Economy": [r"\bpolitical economy\b"],
        "Legislation & Governance": [r"\blegislation\b", r"\bgovernance\b"],
    },
    "business": {
        "Startups & Entrepreneurship": [r"\bstartups?\b", r"\bentrepreneurship\b"],
        "E-commerce": [r"\be.commerce\b", r"\bonline retail\b"],
        "Marketing & Advertising": [r"\bdigital marketing\b", r"\badvertising\b"],
        "Business Strategy": [r"\bbusiness strategy\b", r"\bcorporate strategy\b"],
        "Small Business": [r"\bsmall businesses?\b"],
        "Mergers & Acquisitions": [r"\bmergers?\b", r"\bacquisitions?\b"],
        "Business Automation": [r"\bbusiness automation\b"],
    },
}


def extract_topics(text, niche):
    combined = f"{niche} {text}".lower()
    root = niche.lower().strip()

    patterns = None
    for domain, topics in DOMAIN_PATTERNS.items():
        if domain in root or root in domain:
            patterns = topics
            break

    if patterns is None:
        patterns = {}

    return [
        topic for topic, expressions in patterns.items()
        if any(re.search(expression, combined, re.IGNORECASE)
               for expression in expressions)
    ]


async def expand_subniches(niche, max_results=6):
    if not isinstance(niche, str) or not niche.strip():
        return {"status": "ERROR", "error": "Niche is required"}

    max_results = max(1, min(int(max_results), MAX_RESULTS))

    queries = [
        f"{niche} emerging specialized sub niches",
        f"{niche} new technologies trends developments",
        f"{niche} growing sectors industry applications",
    ]

    def search_all():
        results = []
        engine = DDGS()
        for query in queries:
            try:
                results.extend(list(engine.text(
                    query,
                    safesearch="moderate",
                    max_results=MAX_RESULTS,
                )))
            except Exception:
                continue
        return results

    try:
        results = await asyncio.to_thread(search_all)
        candidates = {}

        for item in results:
            title = (item.get("title") or "").strip()
            snippet = (item.get("body") or "").strip()
            url = (item.get("href") or "").strip()
            evidence_text = f"{title}. {snippet}"

            for topic in extract_topics(evidence_text, niche):
                if topic not in candidates:
                    candidates[topic] = {
                        "parent_niche": niche.strip(),
                        "subniche_candidate": topic,
                        "evidence": snippet[:1000],
                        "url": url,
                        "source": "web_search",
                        "status": "EVIDENCE_MATCHED",
                        "evidence_count": 0,
                    }
                candidates[topic]["evidence_count"] += 1

        output = sorted(
            candidates.values(),
            key=lambda item: item["evidence_count"],
            reverse=True,
        )[:max_results]

        return {
            "status": "SUCCESS",
            "parent_niche": niche.strip(),
            "subniches_found": len(output),
            "subniches": output,
        }

    except Exception as exc:
        return {
            "status": "ERROR",
            "parent_niche": niche,
            "error": str(exc)[:200],
        }
