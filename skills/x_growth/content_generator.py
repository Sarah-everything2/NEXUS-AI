import json
from brain.ollama_client import OllamaClient


class XContentGenerator:
    def __init__(self):
        self.ai = OllamaClient()

    async def _generate(self, prompt):
        result = await self.ai.generate([
            {"role": "user", "content": prompt}
        ])

        if not isinstance(result, str):
            raise ValueError("AI returned an invalid response.")

        return result.strip().strip('"').strip("'")

    async def generate_post(self, story, tone="engaging"):
        if not isinstance(story, dict) or not story.get("title"):
            raise ValueError("A story with a title is required.")

        prompt = f"""
Write ONE original X post.

TOPIC: {story.get("title")}
DETAILS: {story.get("description", "")}
SOURCE: {story.get("url", "")}
TONE: {tone}

STRICT OUTPUT RULES:
- Output only the finished post.
- Maximum 250 characters, including spaces.
- Use one or two short sentences.
- No explanation, introduction, headings or analysis.
- Do not copy the source.
- Do not invent facts, statistics or quotations.
- Do not present allegations as confirmed facts.
"""

        post = await self._generate(prompt)

        if len(post) > 280:
            retry_prompt = f"""
Rewrite this as ONE concise X post.

ABSOLUTE LIMIT: 250 characters including spaces.
Output only the post. No explanation.

TEXT:
{post[:2000]}
"""

            post = await self._generate(retry_prompt)

        if not post or len(post) > 280:
            raise ValueError(
                f"AI could not produce a valid X post "
                f"after retry ({len(post)} characters)."
            )

        return post

    async def generate_thread(self, story, tone="engaging", count=5):
        if not isinstance(story, dict) or not story.get("title"):
            raise ValueError("A story with a title is required.")

        if not isinstance(count, int) or not 2 <= count <= 10:
            raise ValueError("Thread count must be between 2 and 10.")

        prompt = f"""
Create an original X thread.

TOPIC: {story.get("title")}
DETAILS: {story.get("description", "")}
SOURCE: {story.get("url", "")}
TONE: {tone}
NUMBER OF POSTS: {count}

STRICT RULES:
- Return only a valid JSON array of strings.
- Exactly {count} posts.
- Each post must be 250 characters or fewer.
- No markdown fences or explanations.
- Each post must be informative and logically connected.
- Do not invent facts, statistics or quotations.
- Do not copy source wording.
"""

        result = await self._generate(prompt)

        try:
            posts = json.loads(result)
        except (json.JSONDecodeError, TypeError):
            raise ValueError("AI returned an invalid thread JSON format.")

        if not isinstance(posts, list) or len(posts) != count:
            raise ValueError("AI returned an incorrect number of posts.")

        if any(
            not isinstance(post, str)
            or not post.strip()
            or len(post.strip()) > 280
            for post in posts
        ):
            raise ValueError("Thread contains an invalid post.")

        return [post.strip() for post in posts]
