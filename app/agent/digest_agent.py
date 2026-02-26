import os
import json
from typing import Optional
from groq import Groq
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()


class DigestOutput(BaseModel):
    title: str
    summary: str


PROMPT = """You are an expert AI news analyst specializing in summarizing technical articles, research papers, and video content about artificial intelligence.

Guidelines:
- Create a compelling title (5-10 words)
- Write a 2-3 sentence summary with key points + why it matters
- Avoid marketing fluff

Return ONLY valid JSON: {"title":"...","summary":"..."}"""


class DigestAgent:
    def __init__(self):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = "llama-3.1-8b-instant"

    def generate_digest(self, title: str, content: str, article_type: str) -> Optional[DigestOutput]:
        try:
            user_prompt = f"Create a digest for this {article_type}.\nTitle: {title}\nContent:\n{content[:8000]}"

            resp = self.client.chat.completions.create(
                model=self.model,
                temperature=0.7,
                messages=[
                    {"role": "system", "content": PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            )

            text = (resp.choices[0].message.content or "").strip()
            return DigestOutput.model_validate_json(text)

        except Exception as e:
            print(f"Error generating digest (Groq): {e}")
            return None