from __future__ import annotations

import re
from collections import Counter
from typing import Dict, List, TypedDict

from app.domain.models import Conversation

STOPWORDS = {
    "de",
    "la",
    "que",
    "el",
    "en",
    "y",
    "a",
    "los",
    "del",
    "se",
    "las",
    "por",
    "un",
    "para",
    "con",
    "no",
    "una",
    "su",
    "al",
    "lo",
    "como",
    "más",
    "pero",
    "sus",
    "le",
    "ya",
    "o",
    "este",
    "sí",
    "porque",
    "esta",
    "entre",
    "cuando",
    "muy",
    "sin",
    "sobre",
    "también",
    "me",
    "hasta",
    "hay",
    "donde",
    "quien",
    "desde",
    "todo",
    "nos",
    "durante",
    "todos",
    "uno",
    "les",
    "ni",
    "contra",
    "otros",
    "ese",
    "eso",
    "ante",
    "ellos",
    "e",
    "esto",
    "mí",
    "antes",
    "algunos",
    "qué",
    "unos",
    "yo",
    "otro",
    "otras",
    "otra",
    "él",
    "tanto",
    "esa",
    "estos",
    "mucho",
    "quienes",
    "nada",
    "muchos",
    "cual",
    "poco",
    "ella",
    "estar",
    "estas",
    "algunas",
    "algo",
    "nosotros",
    "mi",
    "mis",
    "tú",
    "te",
    "ti",
    "tu",
    "tus",
    "ellas",
    "nosotras",
    "vosotros",
    "vosotras",
    "os",
    "mío",
    "mía",
    "míos",
    "mías",
    "tuyo",
    "tuya",
    "tuyos",
    "tuyas",
    "suyo",
    "suya",
    "suyos",
    "suyas",
    "nuestro",
    "nuestra",
    "nuestros",
    "nuestras",
    "vuestro",
    "vuestra",
    "vuestros",
    "vuestras",
    "esos",
    "esas",
    "estoy",
    "estás",
    "está",
    "estamos",
    "estáis",
    "están",
    "esté",
    "estés",
    "estemos",
    "estén",
    "estaré",
    "estarás",
    "estará",
    "estaremos",
    "estarán",
    "estaría",
    "estarías",
    "estaríamos",
    "estarían",
    "fue",
    "fueron",
    "fui",
    "fuimos",
    "son",
    "es",
    "ser",
    "era",
    "puede",
    "puedo",
    "the",
    "and",
    "for",
    "that",
    "this",
    "are",
    "was",
    "were",
    "will",
    "with",
    "you",
    "your",
    "they",
    "them",
    "have",
    "has",
    "had",
    "from",
    "not",
    "but",
    "about",
    "their",
    "there",
    "can",
    "could",
    "would",
    "should",
    "it's",
    "its",
    "i'm",
    "i'll",
    "i've",
    "we",
    "our",
    "ours",
    "be",
    "is",
    "to",
    "in",
    "of",
    "on",
    "as",
    "it",
    "at",
    "by",
    "or",
    "if",
    "so",
    "do",
    "did",
    "does",
    "am",
    "an",
    "a",
}


def tokenize(text: str) -> List[str]:
    cleaned = re.findall(r"[A-Za-z\u00C0-\u017F]+", text.lower())
    return [word for word in cleaned if word not in STOPWORDS and len(word) > 2]


class SummaryStats(TypedDict):
    total_messages: int
    messages_by_year: Dict[int, int]
    messages_by_person: Dict[str, int]
    voice_total: int
    voice_by_person: Dict[str, int]
    video_total: int
    video_by_person: Dict[str, int]
    video_note_total: int
    video_note_by_person: Dict[str, int]
    photo_total: int
    photo_by_person: Dict[str, int]
    sticker_total: int
    sticker_by_person: Dict[str, int]
    char_by_person: Dict[str, int]
    longest_text_by_person: Dict[str, int]
    longest_text_content: Dict[str, str]
    total_characters: int
    top_words: List[tuple[str, int]]
    export_format: str


class ConversationSummarizer:
    def summarize(self, conversation: Conversation, top_n: int = 20) -> SummaryStats:
        totals_by_year = conversation.year_counts
        participants = conversation.participants

        def collect(attr: str) -> Dict[str, int]:
            return {name: getattr(stats, attr) for name, stats in participants.items()}

        messages_by_person = {name: stats.message_count for name, stats in participants.items()}
        char_by_person = collect("characters")
        longest_text_by_person = collect("longest_text_length")
        longest_text_content = {name: stats.longest_text for name, stats in participants.items()}
        voice_by_person = collect("voice_notes")
        video_by_person = collect("videos")
        video_note_by_person = collect("video_notes")
        photo_by_person = collect("photos")
        sticker_by_person = collect("stickers")

        word_counter: Counter[str] = Counter()
        for text in conversation.text_messages:
            word_counter.update(tokenize(text))

        return {
            "total_messages": conversation.total_messages,
            "messages_by_year": dict(totals_by_year),
            "messages_by_person": messages_by_person,
            "voice_total": sum(voice_by_person.values()),
            "voice_by_person": voice_by_person,
            "video_total": sum(video_by_person.values()),
            "video_by_person": video_by_person,
            "video_note_total": sum(video_note_by_person.values()),
            "video_note_by_person": video_note_by_person,
            "photo_total": sum(photo_by_person.values()),
            "photo_by_person": photo_by_person,
            "sticker_total": sum(sticker_by_person.values()),
            "sticker_by_person": sticker_by_person,
            "char_by_person": char_by_person,
            "longest_text_by_person": longest_text_by_person,
            "longest_text_content": longest_text_content,
            "total_characters": sum(char_by_person.values()),
            "top_words": word_counter.most_common(top_n),
            "export_format": conversation.export_format,
        }
