"""
learning/trainer.py — JARVIS OMEGA V9
Self-improvement system: user corrections, skill learning, preference memory,
action success tracking, and automated fine-tuning data generation.
"""
from __future__ import annotations

import os, json, time, sqlite3, threading, hashlib
from pathlib import Path
from typing import Optional, List, Dict, Callable
from dataclasses import dataclass, asdict
from datetime import datetime

BASE = Path(__file__).resolve().parent.parent

# ═════════════════════════════════════════════════════════════════════════════
# DATA MODELS
# ═════════════════════════════════════════════════════════════════════════════
@dataclass
class UserCorrection:
    id: str
    original_command: str
    ai_response: str
    user_correction: str
    corrected_action: Optional[Dict]
    timestamp: str
    applied: bool = False

@dataclass
class LearnedSkill:
    id: str
    trigger_phrases: List[str]
    actions: List[Dict]
    description: str
    created_at: str
    usage_count: int = 0
    success_rate: float = 1.0

@dataclass
class ActionFeedback:
    action_type: str
    target: str
    success: bool
    context: str
    timestamp: str

# ═════════════════════════════════════════════════════════════════════════════
# LEARNING DATABASE
# ═════════════════════════════════════════════════════════════════════════════
class LearningDB:
    def __init__(self):
        db_path = BASE / "data" / "learning.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.lock = threading.Lock()
        self._init_tables()

    def _init_tables(self):
        with self.lock:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS corrections (
                    id TEXT PRIMARY KEY,
                    original_command TEXT,
                    ai_response TEXT,
                    user_correction TEXT,
                    corrected_action TEXT,
                    timestamp TEXT,
                    applied INTEGER DEFAULT 0
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS skills (
                    id TEXT PRIMARY KEY,
                    trigger_phrases TEXT,
                    actions TEXT,
                    description TEXT,
                    created_at TEXT,
                    usage_count INTEGER DEFAULT 0,
                    success_rate REAL DEFAULT 1.0
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS action_feedback (
                    id INTEGER PRIMARY KEY,
                    action_type TEXT,
                    target TEXT,
                    success INTEGER,
                    context TEXT,
                    timestamp TEXT
                )
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT
                )
            """)
            self.conn.commit()

    def save_correction(self, corr: UserCorrection):
        with self.lock:
            self.conn.execute(
                """INSERT OR REPLACE INTO corrections 
                   (id, original_command, ai_response, user_correction, corrected_action, timestamp, applied)
                   VALUES (?,?,?,?,?,?,?)""",
                (corr.id, corr.original_command, corr.ai_response, corr.user_correction,
                 json.dumps(corr.corrected_action) if corr.corrected_action else None,
                 corr.timestamp, int(corr.applied))
            )
            self.conn.commit()

    def get_corrections(self, limit: int = 50) -> List[UserCorrection]:
        with self.lock:
            cur = self.conn.execute(
                "SELECT * FROM corrections ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            )
            rows = cur.fetchall()
            return [self._row_to_correction(r) for r in rows]

    def _row_to_correction(self, row) -> UserCorrection:
        return UserCorrection(
            id=row[0], original_command=row[1], ai_response=row[2],
            user_correction=row[3],
            corrected_action=json.loads(row[4]) if row[4] else None,
            timestamp=row[5], applied=bool(row[6])
        )

    def save_skill(self, skill: LearnedSkill):
        with self.lock:
            self.conn.execute(
                """INSERT OR REPLACE INTO skills
                   (id, trigger_phrases, actions, description, created_at, usage_count, success_rate)
                   VALUES (?,?,?,?,?,?,?)""",
                (skill.id, json.dumps(skill.trigger_phrases), json.dumps(skill.actions),
                 skill.description, skill.created_at, skill.usage_count, skill.success_rate)
            )
            self.conn.commit()

    def get_skills(self) -> List[LearnedSkill]:
        with self.lock:
            cur = self.conn.execute("SELECT * FROM skills")
            rows = cur.fetchall()
            return [self._row_to_skill(r) for r in rows]

    def _row_to_skill(self, row) -> LearnedSkill:
        return LearnedSkill(
            id=row[0], trigger_phrases=json.loads(row[1]), actions=json.loads(row[2]),
            description=row[3], created_at=row[4], usage_count=row[5], success_rate=row[6]
        )

    def increment_skill_usage(self, skill_id: str, success: bool):
        with self.lock:
            cur = self.conn.execute(
                "SELECT usage_count, success_rate FROM skills WHERE id=?", (skill_id,)
            )
            row = cur.fetchone()
            if row:
                count, rate = row
                new_rate = (rate * count + (1.0 if success else 0.0)) / (count + 1)
                self.conn.execute(
                    "UPDATE skills SET usage_count=?, success_rate=? WHERE id=?",
                    (count + 1, new_rate, skill_id)
                )
                self.conn.commit()

    def log_feedback(self, feedback: ActionFeedback):
        with self.lock:
            self.conn.execute(
                """INSERT INTO action_feedback (action_type, target, success, context, timestamp)
                   VALUES (?,?,?,?,?)""",
                (feedback.action_type, feedback.target, int(feedback.success),
                 feedback.context, feedback.timestamp)
            )
            self.conn.commit()

    def get_action_success_rate(self, action_type: str, target: str = "") -> float:
        with self.lock:
            cur = self.conn.execute(
                """SELECT SUM(success), COUNT(*) FROM action_feedback 
                   WHERE action_type=? AND (target=? OR ?='')""",
                (action_type, target, target)
            )
            row = cur.fetchone()
            if row and row[1] > 0:
                return row[0] / row[1]
            return 0.5

    def set_preference(self, key: str, value: str):
        with self.lock:
            self.conn.execute(
                """INSERT OR REPLACE INTO preferences (key, value, updated_at)
                   VALUES (?,?,?)""",
                (key, value, datetime.now().isoformat())
            )
            self.conn.commit()

    def get_preference(self, key: str, default: str = "") -> str:
        with self.lock:
            cur = self.conn.execute("SELECT value FROM preferences WHERE key=?", (key,))
            row = cur.fetchone()
            return row[0] if row else default

# ═════════════════════════════════════════════════════════════════════════════
# SKILL LEARNING ENGINE
# ═════════════════════════════════════════════════════════════════════════════
class SkillLearner:
    def __init__(self, db: LearningDB):
        self.db = db

    def teach_skill(self, trigger: str, actions: List[Dict], description: str = ""):
        skill_id = hashlib.md5(trigger.encode()).hexdigest()[:12]
        skill = LearnedSkill(
            id=skill_id,
            trigger_phrases=[trigger.lower()],
            actions=actions,
            description=description or f"Skill: {trigger}",
            created_at=datetime.now().isoformat()
        )
        self.db.save_skill(skill)
        return skill_id

    def find_matching_skill(self, text: str) -> Optional[LearnedSkill]:
        skills = self.db.get_skills()
        text_lower = text.lower()
        for skill in skills:
            for trigger in skill.trigger_phrases:
                if trigger in text_lower or text_lower in trigger:
                    return skill
                from rapidfuzz import fuzz
                if fuzz.ratio(trigger, text_lower) > 85:
                    return skill
        return None

    def learn_from_correction(self, original_cmd: str, ai_response: str, user_correction: str,
                              corrected_action: Optional[Dict] = None):
        corr_id = hashlib.md5(f"{original_cmd}:{time.time()}".encode()).hexdigest()[:12]
        correction = UserCorrection(
            id=corr_id,
            original_command=original_cmd,
            ai_response=ai_response,
            user_correction=user_correction,
            corrected_action=corrected_action,
            timestamp=datetime.now().isoformat()
        )
        self.db.save_correction(correction)
        if corrected_action and "always" in user_correction.lower():
            self._auto_skill_from_correction(original_cmd, corrected_action)

    def _auto_skill_from_correction(self, trigger: str, action: Dict):
        generalized = self._generalize_trigger(trigger)
        self.teach_skill(generalized, [action], f"Auto-learned from correction: {trigger}")

    def _generalize_trigger(self, text: str) -> str:
        import re
        generalizations = [
            (r'\bchrome\b', 'browser'),
            (r'\bnotepad\b', 'text editor'),
            (r'\bspotify\b', 'music app'),
        ]
        result = text.lower()
        for pattern, replacement in generalizations:
            result = re.sub(pattern, replacement, result)
        return result

# ═════════════════════════════════════════════════════════════════════════════
# PREFERENCE LEARNER
# ═════════════════════════════════════════════════════════════════════════════
class PreferenceLearner:
    def __init__(self, db: LearningDB):
        self.db = db

    def learn_preference(self, category: str, value: str, confidence: float = 1.0):
        key = f"pref_{category}"
        current = self.db.get_preference(key)
        if current:
            current_val, current_conf = current.split('|') if '|' in current else (current, '1')
            new_conf = float(current_conf) + confidence
            if value == current_val:
                self.db.set_preference(key, f"{value}|{new_conf}")
            else:
                alt_key = f"pref_{category}_alt"
                alts = json.loads(self.db.get_preference(alt_key, '[]'))
                if value not in alts:
                    alts.append(value)
                    self.db.set_preference(alt_key, json.dumps(alts))
        else:
            self.db.set_preference(key, f"{value}|{confidence}")

    def get_preference(self, category: str, default: str = "") -> str:
        key = f"pref_{category}"
        val = self.db.get_preference(key, default)
        return val.split('|')[0] if '|' in val else val

# ═════════════════════════════════════════════════════════════════════════════
# FEEDBACK LOOP
# ═════════════════════════════════════════════════════════════════════════════
class FeedbackLoop:
    def __init__(self, db: LearningDB):
        self.db = db

    def report_action_result(self, action: Dict, context: str, success: bool):
        feedback = ActionFeedback(
            action_type=action.get("action", "unknown"),
            target=action.get("target", ""),
            success=success,
            context=context,
            timestamp=datetime.now().isoformat()
        )
        self.db.log_feedback(feedback)

    def should_attempt_action(self, action: Dict) -> Tuple[bool, str]:
        action_type = action.get("action", "")
        target = action.get("target", "")
        rate = self.db.get_action_success_rate(action_type, target)
        if rate < 0.3 and rate > 0:
            return False, f"Action '{action_type}' historically fails ({rate:.0%} success)."
        return True, "OK"

    def get_better_alternative(self, action: Dict) -> Optional[Dict]:
        action_type = action.get("action", "")
        alternatives = {
            "open_app": "search_web",
            "click_text": "type_text",
            "type_text": "hotkey",
        }
        if action_type in alternatives:
            return {"action": alternatives[action_type], "target": action.get("target", "")}
        return None

# ═════════════════════════════════════════════════════════════════════════════
# TRAINING DATA EXPORT
# ═════════════════════════════════════════════════════════════════════════════
class TrainingDataExporter:
    def __init__(self, db: LearningDB):
        self.db = db

    def export_conversations(self, output_path: Optional[Path] = None) -> Path:
        if output_path is None:
            output_path = BASE / "data" / "training" / "conversations.jsonl"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        corrections = self.db.get_corrections(limit=100)
        with open(output_path, 'w', encoding='utf-8') as f:
            for corr in corrections:
                if corr.applied and corr.corrected_action:
                    entry = {
                        "instruction": corr.original_command,
                        "input": "",
                        "output": json.dumps(corr.corrected_action),
                        "system": "You are JARVIS, a helpful AI assistant that controls the computer."
                    }
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return output_path

    def export_for_ollama(self) -> Path:
        export_path = BASE / "data" / "training" / "jarvis_training.json"
        export_path.parent.mkdir(parents=True, exist_ok=True)
        skills = self.db.get_skills()
        corrections = self.db.get_corrections(limit=200)
        training_data = []
        for skill in skills:
            for trigger in skill.trigger_phrases:
                training_data.append({
                    "messages": [
                        {"role": "system", "content": "You are JARVIS, an AI assistant."},
                        {"role": "user", "content": trigger},
                        {"role": "assistant", "content": json.dumps(skill.actions)}
                    ]
                })
        for corr in corrections:
            if corr.corrected_action:
                training_data.append({
                    "messages": [
                        {"role": "system", "content": "You are JARVIS, an AI assistant."},
                        {"role": "user", "content": corr.original_command},
                        {"role": "assistant", "content": f"{corr.user_correction}\n{json.dumps(corr.corrected_action)}"}
                    ]
                })
        with open(export_path, 'w', encoding='utf-8') as f:
            json.dump(training_data, f, ensure_ascii=False, indent=2)
        return export_path

# ═════════════════════════════════════════════════════════════════════════════
# MAIN LEARNING HUB
# ═════════════════════════════════════════════════════════════════════════════
class LearningHub:
    def __init__(self):
        self.db = LearningDB()
        self.skill_learner = SkillLearner(self.db)
        self.preference_learner = PreferenceLearner(self.db)
        self.feedback = FeedbackLoop(self.db)
        self.exporter = TrainingDataExporter(self.db)

    def process_user_input(self, text: str) -> Optional[List[Dict]]:
        skill = self.skill_learner.find_matching_skill(text)
        if skill:
            self.db.increment_skill_usage(skill.id, success=True)
            return skill.actions
        return None

    def correct(self, original: str, ai_response: str, user_correction: str,
                action: Optional[Dict] = None):
        self.skill_learner.learn_from_correction(original, ai_response, user_correction, action)

    def teach(self, trigger: str, actions: List[Dict], description: str = ""):
        return self.skill_learner.teach_skill(trigger, actions, description)

    def report_result(self, action: Dict, context: str, success: bool):
        self.feedback.report_action_result(action, context, success)

    def get_system_prompt_additions(self) -> str:
        prefs = []
        browser = self.preference_learner.get_preference("browser", "")
        if browser:
            prefs.append(f"- User prefers {browser} as default browser.")
        search = self.preference_learner.get_preference("search_engine", "")
        if search:
            prefs.append(f"- User prefers {search} for web search.")
        editor = self.preference_learner.get_preference("editor", "")
        if editor:
            prefs.append(f"- User prefers {editor} for text editing.")
        if prefs:
            return "\nLEARNED PREFERENCES:\n" + "\n".join(prefs)
        return ""

# Singleton
_hub: Optional[LearningHub] = None

def get_learning_hub() -> LearningHub:
    global _hub
    if _hub is None:
        _hub = LearningHub()
    return _hub
