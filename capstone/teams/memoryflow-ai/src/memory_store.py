"""JSON-backed long-term memory storage for MemoryFlow AI."""

import json
import os
import re
from datetime import datetime

from config import MEMORY_FILE
from conflict_resolver import ConflictResolver
from memory_lifecycle import MemoryLifecycleManager


class MemoryStore:
    """Save, update, summarize, search, and inspect memories."""

    IMPORTANCE = {
        "name": 10,
        "capstone_topic": 10,
        "project": 8,
        "conversation_summary": 7,
        "reflection": 7,
        "occupation": 7,
        "preference": 6,
        "interaction": 1,
    }

    def __init__(self, memory_file=MEMORY_FILE):
        self.memory_file = memory_file
        self.lifecycle = MemoryLifecycleManager()
        self.conflict_resolver = ConflictResolver()
        self.last_conflicts = []
        self.last_retrieval_scores = []
        self.evaluation_run_count = 0
        self._ensure_memory_file()

    def save_interaction(self, user_input, ai_response, replayed_memories=None, judge_result=None):
        """Save an interaction and upsert extracted facts."""
        memories = self.load_memories()
        timestamp = self._now()
        self.last_conflicts = []

        interaction = self.lifecycle.ensure_metadata(
            {
                "type": "interaction",
                "timestamp": timestamp,
                "created_at": timestamp,
                "updated_at": timestamp,
                "last_accessed": None,
                "access_count": 0,
                "status": "active",
                "user_input": user_input,
                "ai_response": ai_response,
                "replayed_memories": replayed_memories or [],
                "judge_result": judge_result or {},
                "importance": self.IMPORTANCE["interaction"],
                "text": self._summarize_interaction(user_input),
                "history": [],
                "conflict_count": 0,
            }
        )
        memories.append(interaction)

        for fact in self.extract_facts(user_input):
            self._upsert_memory(memories, fact, timestamp, user_input)

        self.save_memories(memories)
        return self.last_conflicts

    def add_memory(self, memory):
        """Add or upsert a non-interaction memory such as reflection."""
        memories = self.load_memories()
        timestamp = self._now()
        if memory.get("type") == "reflection":
            stored = dict(memory)
            stored["created_at"] = stored.get("created_at", timestamp)
            stored["updated_at"] = timestamp
            stored["source"] = stored.get("source", "system")
            memories.append(self.lifecycle.ensure_metadata(stored))
        else:
            self._upsert_memory(memories, memory, timestamp, memory.get("source", "system"))
        self.save_memories(memories)

    def summarize_recent_interactions(self, limit=6):
        """Create or update summary memory from recent interactions and facts."""
        memories = self.load_memories()
        interactions = [memory for memory in memories if memory.get("type") == "interaction"][-limit:]
        if not interactions:
            return None

        facts = {memory.get("key"): memory for memory in memories if memory.get("type") == "fact"}
        topics = []
        if "project" in facts:
            topics.append(f"{facts['project']['value']} 프로젝트")
        if "capstone_topic" in facts:
            topics.append(f"{facts['capstone_topic']['value']} 캡스톤")
        if "preference" in facts:
            topics.append(f"{facts['preference']['value']} 선호")

        recent_text = ", ".join(memory.get("text", "") for memory in interactions[-3:] if memory.get("text"))
        text = f"사용자는 {', '.join(topics)}에 대해 대화했다." if topics else f"최근 대화 요약: {recent_text}"

        timestamp = self._now()
        summary = self.lifecycle.ensure_metadata(
            {
                "type": "summary",
                "key": "conversation_summary",
                "value": text,
                "text": text,
                "importance": self.IMPORTANCE["conversation_summary"],
                "created_at": timestamp,
                "updated_at": timestamp,
                "last_accessed": None,
                "access_count": 0,
                "status": "active",
                "history": [],
                "conflict_count": 0,
            }
        )
        self._upsert_memory(memories, summary, timestamp, "recent_interactions")
        self.save_memories(memories)
        return summary

    def load_memories(self):
        """Load memories from disk and backfill lifecycle metadata."""
        self._ensure_memory_file()
        try:
            with open(self.memory_file, "r", encoding="utf-8") as file:
                data = json.load(file)
        except json.JSONDecodeError:
            return []

        memories = data if isinstance(data, list) else []
        changed = False
        for memory in memories:
            before = dict(memory)
            self.lifecycle.ensure_metadata(memory)
            if before != memory:
                changed = True
        if changed:
            self.save_memories(memories)
        return memories

    def save_memories(self, memories):
        """Apply lifecycle rules and persist a memory list."""
        self.lifecycle.apply_lifecycle_rules(memories)
        self._write_memories(memories)

    def record_replay_access(self, replayed_memories):
        """Increase access metadata for memories used by replay."""
        if not replayed_memories:
            return 0

        memories = self.load_memories()
        updated = 0
        for replayed in replayed_memories:
            for memory in memories:
                if self._same_memory(memory, replayed):
                    self.lifecycle.update_access_metadata(memory)
                    updated += 1
                    break
        self.save_memories(memories)
        return updated

    def record_retrieval_scores(self, scored_memories):
        """Store latest retrieval scores for stats and display."""
        self.last_retrieval_scores = scored_memories or []

    def record_evaluation_run(self):
        """Increase in-memory eval run counter."""
        self.evaluation_run_count += 1

    def search_memories(self, query, limit=5, include_summary=True):
        """Search active/protected memories by keyword overlap and importance."""
        query_keywords = set(self._extract_keywords(query))
        scored = []
        for index, memory in enumerate(self.load_memories()):
            if memory.get("status") == "archived":
                continue
            if memory.get("type") == "summary" and not include_summary:
                continue
            memory_keywords = set(self._extract_keywords(self._memory_to_text(memory)))
            overlap = len(query_keywords.intersection(memory_keywords))
            if overlap > 0:
                scored.append((overlap, int(memory.get("importance", 1)), int(memory.get("access_count", 0)), index, memory))
        scored.sort(key=lambda item: (item[0], item[1], item[2], item[3]), reverse=True)
        return [memory for _, _, _, _, memory in scored[:limit]]

    def candidate_memories(self, include_archived=False):
        """Return replay candidates for retrieval scoring."""
        memories = []
        for memory in self.load_memories():
            if not include_archived and memory.get("status") == "archived":
                continue
            if memory.get("type") in {"fact", "summary", "reflection", "interaction"}:
                memories.append(memory)
        return memories

    def get_fact(self, key):
        facts = [
            memory
            for memory in self.load_memories()
            if memory.get("type") == "fact" and memory.get("key") == key and memory.get("status") != "archived"
        ]
        return facts[-1] if facts else None

    def get_summary(self):
        summaries = [
            memory
            for memory in self.load_memories()
            if memory.get("type") == "summary" and memory.get("status") != "archived"
        ]
        return summaries[-1] if summaries else None

    def get_facts_by_keys(self, keys):
        facts = []
        for key in keys:
            fact = self.get_fact(key)
            if fact:
                facts.append(fact)
        return facts

    def get_important_memories(self, min_importance=8):
        memories = [
            memory
            for memory in self.load_memories()
            if memory.get("status") == "protected" or int(memory.get("importance", 1)) >= min_importance
        ]
        memories.sort(key=lambda memory: (int(memory.get("importance", 1)), int(memory.get("access_count", 0))), reverse=True)
        return memories

    def get_statistics(self):
        """Return memory counts for stats output."""
        memories = self.load_memories()
        retrieval_scores = [item.get("score", 0) for item in self.last_retrieval_scores]
        return {
            "total": len(memories),
            "fact": sum(1 for memory in memories if memory.get("type") == "fact"),
            "interaction": sum(1 for memory in memories if memory.get("type") == "interaction"),
            "summary": sum(1 for memory in memories if memory.get("type") == "summary"),
            "reflection": sum(1 for memory in memories if memory.get("type") == "reflection"),
            "protected": sum(1 for memory in memories if memory.get("status") == "protected"),
            "active": sum(1 for memory in memories if memory.get("status") == "active"),
            "archived": sum(1 for memory in memories if memory.get("status") == "archived"),
            "compressed": sum(1 for memory in memories if memory.get("status") == "compressed"),
            "total_replay_access_count": sum(int(memory.get("access_count", 0)) for memory in memories),
            "conflict_count": sum(int(memory.get("conflict_count", 0)) for memory in memories),
            "average_retrieval_score": round(sum(retrieval_scores) / len(retrieval_scores), 2) if retrieval_scores else 0,
            "replay_success_count": sum(1 for memory in memories if memory.get("type") == "interaction" and memory.get("replayed_memories")),
            "evaluation_run_count": self.evaluation_run_count,
        }

    def format_all_memories(self):
        """Return all memories formatted for show memory."""
        memories = self.load_memories()
        sections = [
            ("[FACT MEMORY]", [memory for memory in memories if memory.get("type") == "fact"]),
            ("[SUMMARY MEMORY]", [memory for memory in memories if memory.get("type") == "summary"]),
            ("[REFLECTION MEMORY]", [memory for memory in memories if memory.get("type") == "reflection"]),
            ("[INTERACTION MEMORY]", [memory for memory in memories if memory.get("type") == "interaction"]),
        ]
        lines = []
        for title, items in sections:
            lines.append(title)
            if not items:
                lines.append("* 저장된 memory가 없습니다.")
            else:
                for memory in items:
                    lines.append(f"- {memory.get('text', '')}")
                    lines.append(
                        "  "
                        f"key={memory.get('key', '-')}, "
                        f"importance={memory.get('importance', 1)}, "
                        f"status={memory.get('status', 'active')}, "
                        f"access_count={memory.get('access_count', 0)}, "
                        f"conflict_count={memory.get('conflict_count', 0)}"
                    )
                    if memory.get("history"):
                        lines.append(f"  history={memory.get('history')}")
            lines.append("")
        return "\n".join(lines).rstrip()

    def extract_facts(self, user_input):
        text = self._normalize_text(user_input)
        facts = []
        for key, extractor in [
            ("name", self._extract_name),
            ("capstone_topic", self._extract_capstone_topic),
            ("project", self._extract_project),
            ("occupation", self._extract_occupation),
            ("preference", self._extract_preference),
        ]:
            value = extractor(text)
            if value:
                facts.append(self._build_fact(key, value))
        return facts

    def _build_fact(self, key, value):
        timestamp = self._now()
        templates = {
            "name": "사용자 이름은 {value}이다.",
            "capstone_topic": "사용자의 캡스톤 주제는 {value}이다.",
            "project": "사용자의 프로젝트는 {value}이다.",
            "occupation": "사용자의 직업은 {value}이다.",
            "preference": "사용자는 {value}을/를 선호한다.",
        }
        return self.lifecycle.ensure_metadata(
            {
                "type": "fact",
                "key": key,
                "value": value,
                "text": templates[key].format(value=value),
                "importance": self.IMPORTANCE[key],
                "created_at": timestamp,
                "updated_at": timestamp,
                "last_accessed": None,
                "access_count": 0,
                "status": "active",
                "history": [],
                "conflict_count": 0,
            }
        )

    def _extract_name(self, text):
        return self._first_match(text, [
            r"내\s*이름은\s*(.+?)(?:이야|야|입니다|이에요|예요|라고\s*해)?$",
            r"나는\s*(.+?)(?:이야|야|입니다|이에요|예요|라고\s*해)$",
            r"저는\s*(.+?)(?:입니다|이에요|예요|라고\s*합니다)$",
        ])

    def _extract_capstone_topic(self, text):
        return self._first_match(text, [
            r"내\s*캡스톤\s*주제는\s*(.+?)(?:이야|야|입니다|이에요|예요)?$",
            r"캡스톤\s*주제는\s*(.+?)(?:이야|야|입니다|이에요|예요)?$",
            r"나는\s*캡스톤으로\s*(.+?)(?:을|를)?\s*만들고\s*있어$",
        ])

    def _extract_project(self, text):
        if "캡스톤" in text:
            return ""
        return self._first_match(text, [
            r"내\s*프로젝트는\s*(.+?)(?:이야|야|입니다|이에요|예요)?$",
            r"나는\s*(.+?)(?:을|를)?\s*만들고\s*있어$",
            r"나는\s*(.+?)\s*프로젝트(?:를)?\s*진행\s*중(?:이야|입니다)?$",
        ])

    def _extract_occupation(self, text):
        return self._first_match(text, [
            r"내\s*직업은\s*(.+?)(?:이야|야|입니다|이에요|예요)?$",
            r"나는\s*(.+?)(?:로|으로)?\s*일하고\s*있어$",
        ])

    def _extract_preference(self, text):
        return self._first_match(text, [
            r"나는\s*(.+?)(?:을|를)?\s*좋아해$",
            r"나는\s*(.+?)(?:에)?\s*관심(?:이)?\s*있어$",
        ])

    def _first_match(self, text, patterns):
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return self._clean_fact_value(match.group(1))
        return ""

    def _upsert_memory(self, memories, memory, timestamp, source):
        stored = dict(memory)
        stored["updated_at"] = timestamp
        stored["source"] = source

        for index, old in enumerate(memories):
            if old.get("type") == stored.get("type") and old.get("key") == stored.get("key"):
                stored["created_at"] = old.get("created_at", timestamp)
                stored["access_count"] = old.get("access_count", 0)
                stored["last_accessed"] = old.get("last_accessed")
                if stored.get("type") == "fact":
                    resolved, conflict = self.conflict_resolver.resolve(old, stored)
                    if conflict:
                        self.last_conflicts.append(conflict)
                    memories[index] = self.lifecycle.ensure_metadata(resolved)
                else:
                    stored["history"] = old.get("history", [])
                    stored["conflict_count"] = old.get("conflict_count", 0)
                    memories[index] = self.lifecycle.ensure_metadata(stored)
                return
        memories.append(self.lifecycle.ensure_metadata(stored))

    def _same_memory(self, left, right):
        if left.get("type") == right.get("type") and left.get("key") and left.get("key") == right.get("key"):
            return True
        return left.get("created_at") == right.get("created_at") and left.get("text") == right.get("text")

    def _ensure_memory_file(self):
        directory = os.path.dirname(self.memory_file)
        if directory:
            os.makedirs(directory, exist_ok=True)
        if not os.path.exists(self.memory_file):
            with open(self.memory_file, "w", encoding="utf-8") as file:
                json.dump([], file, ensure_ascii=False, indent=2)

    def _write_memories(self, memories):
        with open(self.memory_file, "w", encoding="utf-8") as file:
            json.dump(memories, file, ensure_ascii=False, indent=2)

    def _memory_to_text(self, memory):
        if memory.get("type") in {"fact", "summary", "reflection"}:
            return f"{memory.get('key', '')} {memory.get('value', '')} {memory.get('text', '')}"
        return " ".join([str(memory.get("user_input", "")), str(memory.get("ai_response", "")), str(memory.get("text", ""))])

    def _extract_keywords(self, text):
        tokens = re.findall(r"[A-Za-z0-9_]+|[가-힣]+", str(text).lower())
        stopwords = {"내", "나는", "나", "뭐야", "뭐", "무엇", "이야", "야", "은", "는", "이", "가", "을", "를"}
        return [token for token in tokens if token not in stopwords and len(token) > 1]

    def _normalize_text(self, user_input):
        text = str(user_input).strip()
        text = re.sub(r"[.。!?！？]+$", "", text)
        return re.sub(r"\s+", " ", text)

    def _clean_fact_value(self, value):
        cleaned = str(value).strip()
        cleaned = re.sub(r"[.。!?！？]+$", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned)
        cleaned = re.sub(r"(이야|야|입니다|이에요|예요|라고 해)$", "", cleaned).strip()
        cleaned = re.sub(r"(을|를)$", "", cleaned).strip()
        return cleaned

    def _summarize_interaction(self, user_input):
        text = self._normalize_text(user_input)
        return text[:80] + "..." if len(text) > 80 else text

    def _now(self):
        return datetime.now().isoformat(timespec="seconds")
