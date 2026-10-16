import base64
import hashlib
import html
import json
import random
import re
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components


st.set_page_config(
    page_title="English Vocabulary",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# 基础配置
# ============================================================

GITHUB_OWNER = "ojoj0307"
GITHUB_REPO = "english-vocabulary"

VOCABULARY_PATH = "vocabulary.json"
NEW_WORDS_PATH = "new_words.json"
DAILY_STATS_PATH = "daily_stats.json"

GITHUB_API_BASE = (
    f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/"
)

MALAYSIA_TZ = ZoneInfo("Asia/Kuala_Lumpur")

CATEGORIES = ["noun", "verb", "adjective", "adverb"]
QUESTION_TYPES = ["中译英", "英译中"]

INITIAL_PRIORITY = 12
MIN_PRIORITY = 0
MAX_PRIORITY = 30

try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
except Exception:
    GITHUB_TOKEN = ""


# ============================================================
# GitHub 文件操作
# ============================================================

def github_enabled() -> bool:
    return bool(str(GITHUB_TOKEN).strip())


def github_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def github_get_file(path: str) -> Tuple[Optional[str], Optional[str]]:
    if not github_enabled():
        return None, None

    try:
        response = requests.get(
            GITHUB_API_BASE + path,
            headers=github_headers(),
            timeout=15,
        )

        if response.status_code == 404:
            return None, None

        response.raise_for_status()

        payload = response.json()
        content = payload.get("content", "").replace("\n", "")
        decoded = base64.b64decode(content).decode("utf-8")

        return decoded, payload.get("sha")

    except Exception as exc:
        st.error(f"读取 GitHub 文件失败：{path}\n\n{exc}")
        return None, None


def github_save_file(
    path: str,
    data: Any,
    sha: Optional[str],
    message: str,
) -> bool:
    if not github_enabled():
        st.warning("未配置 GITHUB_TOKEN，无法保存到 GitHub。")
        return False

    encoded = base64.b64encode(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=4,
        ).encode("utf-8")
    ).decode("utf-8")

    payload = {
        "message": message,
        "content": encoded,
    }

    if sha:
        payload["sha"] = sha

    try:
        response = requests.put(
            GITHUB_API_BASE + path,
            headers=github_headers(),
            json=payload,
            timeout=15,
        )
        response.raise_for_status()
        return True

    except Exception as exc:
        st.error(f"保存 GitHub 文件失败：{path}\n\n{exc}")
        return False


def save_remote_json(path: str, data: Any, message: str) -> bool:
    _, latest_sha = github_get_file(path)
    return github_save_file(path, data, latest_sha, message)


def get_today() -> str:
    return datetime.now(MALAYSIA_TZ).strftime("%Y-%m-%d")


# ============================================================
# 数据工具
# ============================================================

def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {
            "1",
            "true",
            "yes",
            "y",
            "熟练",
        }

    return bool(value)


def stable_word_id(word: Dict[str, Any], index: int) -> str:
    source = (
        f"{word.get('english', '')}"
        f"\x00"
        f"{word.get('chinese', '')}"
    )

    digest = hashlib.sha1(
        source.encode("utf-8")
    ).hexdigest()[:12]

    return f"word-{index}-{digest}"


def normalize_word(
    word: Dict[str, Any],
    index: int = 0,
) -> bool:
    changed = False

    if not isinstance(word, dict):
        return False

    defaults = {
        "english": "",
        "chinese": "",
        "category": "noun",
        "cn_note": "",
        "en_note": "",
        "proficient": False,
        "initial_priority": INITIAL_PRIORITY,
        "priority": INITIAL_PRIORITY,
        "correct_streak": 0,
        "wrong_streak": 0,
        "last_review_order": 0,
        "cn_to_en_weight": 3,
        "en_to_cn_weight": 3,
        "cn_to_en_correct": 0,
        "cn_to_en_wrong": 0,
        "en_to_cn_correct": 0,
        "en_to_cn_wrong": 0,
        "cn_to_en_not_seen": 0,
        "en_to_cn_not_seen": 0,
    }

    for key, value in defaults.items():
        if key not in word:
            word[key] = value
            changed = True

    if word.get("category") not in CATEGORIES:
        word["category"] = "noun"
        changed = True

    if not word.get("id"):
        word["id"] = stable_word_id(word, index)
        changed = True

    old_proficient = word.get(
        "proficient",
        word.get(
            "is_proficient",
            word.get("mastered", word.get("skilled", False)),
        ),
    )

    normalized_proficient = as_bool(old_proficient)

    if word.get("proficient") != normalized_proficient:
        word["proficient"] = normalized_proficient
        changed = True

    if "initial_priority" not in word:
        word["initial_priority"] = INITIAL_PRIORITY
        changed = True

    if "priority" not in word:
        word["priority"] = INITIAL_PRIORITY
        changed = True

    word["initial_priority"] = max(
        1,
        as_int(word.get("initial_priority"), INITIAL_PRIORITY),
    )

    word["priority"] = max(
        MIN_PRIORITY,
        min(
            MAX_PRIORITY,
            as_int(word.get("priority"), INITIAL_PRIORITY),
        ),
    )

    for key in (
        "cn_to_en_weight",
        "en_to_cn_weight",
    ):
        word[key] = max(
            1,
            as_int(word.get(key), 3),
        )

    for key in (
        "cn_to_en_correct",
        "cn_to_en_wrong",
        "en_to_cn_correct",
        "en_to_cn_wrong",
        "cn_to_en_not_seen",
        "en_to_cn_not_seen",
        "correct_streak",
        "wrong_streak",
        "last_review_order",
    ):
        word[key] = max(
            0,
            as_int(word.get(key), 0),
        )

    correct = (
        as_int(word.get("cn_to_en_correct"))
        + as_int(word.get("en_to_cn_correct"))
    )

    wrong = (
        as_int(word.get("cn_to_en_wrong"))
        + as_int(word.get("en_to_cn_wrong"))
    )

    if word.get("correct") != correct:
        word["correct"] = correct
        changed = True

    if word.get("wrong") != wrong:
        word["wrong"] = wrong
        changed = True

    return changed


def default_daily_stats() -> Dict[str, Any]:
    return {
        "date": get_today(),
        "cn_to_en_answered": 0,
        "cn_to_en_correct": 0,
        "en_to_cn_answered": 0,
        "en_to_cn_correct": 0,
    }


def default_new_words() -> Dict[str, Any]:
    return {
        "date": get_today(),
        "words": [],
        "rounds": {
            "中译英": [],
            "英译中": [],
        },
    }


# ============================================================
# 数据加载
# ============================================================

def load_words() -> Tuple[List[Dict[str, Any]], Optional[str]]:
    content, sha = github_get_file(VOCABULARY_PATH)

    if content is None:
        if github_enabled():
            st.error("无法读取 vocabulary.json")
        return [], None

    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        st.error(f"vocabulary.json 格式错误：{exc}")
        return [], sha

    if not isinstance(data, list):
        st.error("vocabulary.json 必须是数组。")
        return [], sha

    changed = False

    for index, word in enumerate(data):
        if normalize_word(word, index):
            changed = True

    if changed and github_enabled():
        save_remote_json(
            VOCABULARY_PATH,
            data,
            "Migrate vocabulary data structure",
        )
        _, sha = github_get_file(VOCABULARY_PATH)

    return data, sha


def load_new_words() -> Tuple[Dict[str, Any], Optional[str]]:
    content, sha = github_get_file(NEW_WORDS_PATH)

    if content is None:
        return default_new_words(), sha

    try:
        raw = json.loads(content)
    except json.JSONDecodeError:
        raw = default_new_words()

    if isinstance(raw, list):
        data = {
            "date": get_today(),
            "words": raw,
        }
    elif isinstance(raw, dict):
        data = raw
    else:
        data = default_new_words()

    changed = False

    if data.get("date") != get_today():
        data = default_new_words()
        changed = True

    if not isinstance(data.get("words"), list):
        data["words"] = []
        changed = True

    if not isinstance(data.get("rounds"), dict):
        data["rounds"] = {
            "中译英": [],
            "英译中": [],
        }
        changed = True

    for question_type in QUESTION_TYPES:
        if not isinstance(
            data["rounds"].get(question_type),
            list,
        ):
            data["rounds"][question_type] = []
            changed = True

    for index, word in enumerate(data["words"]):
        if normalize_word(word, index):
            changed = True

    valid_ids = {
        str(word.get("id"))
        for word in data["words"]
    }

    for question_type in QUESTION_TYPES:
        old_ids = data["rounds"].get(question_type, [])
        new_ids = [
            str(word_id)
            for word_id in old_ids
            if str(word_id) in valid_ids
        ]

        if old_ids != new_ids:
            data["rounds"][question_type] = new_ids
            changed = True

    if changed and sha and github_enabled():
        github_save_file(
            NEW_WORDS_PATH,
            data,
            sha,
            "Migrate new words data structure",
        )

    return data, sha


def load_daily_stats() -> Tuple[Dict[str, Any], Optional[str]]:
    content, sha = github_get_file(DAILY_STATS_PATH)

    if content is None:
        return default_daily_stats(), sha

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return default_daily_stats(), sha

    if not isinstance(data, dict):
        return default_daily_stats(), sha

    if data.get("date") != get_today():
        return default_daily_stats(), sha

    defaults = default_daily_stats()

    for key, value in defaults.items():
        data.setdefault(key, value)

    return data, sha


words, vocabulary_sha = load_words()
new_words_data, new_words_sha = load_new_words()
daily_stats, daily_stats_sha = load_daily_stats()


def save_words() -> bool:
    global vocabulary_sha

    success = save_remote_json(
        VOCABULARY_PATH,
        words,
        "Update vocabulary",
    )

    if success:
        _, vocabulary_sha = github_get_file(VOCABULARY_PATH)

    return success


def save_new_words() -> bool:
    global new_words_sha

    new_words_data["date"] = get_today()

    success = save_remote_json(
        NEW_WORDS_PATH,
        new_words_data,
        "Update daily new words",
    )

    if success:
        _, new_words_sha = github_get_file(NEW_WORDS_PATH)

    return success


def save_daily_stats() -> bool:
    global daily_stats_sha

    success = save_remote_json(
        DAILY_STATS_PATH,
        daily_stats,
        "Update daily statistics",
    )

    if success:
        _, daily_stats_sha = github_get_file(DAILY_STATS_PATH)

    return success


# ============================================================
# 词语查询
# ============================================================

def word_by_id(
    word_id: str,
    pool: Optional[Iterable[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    source = words if pool is None else pool

    for word in source:
        if str(word.get("id")) == str(word_id):
            return word

    return None


def sync_new_word(word_id: str) -> None:
    source = word_by_id(word_id)

    if source is None:
        return

    for word in new_words_data.get("words", []):
        if str(word.get("id")) == str(word_id):
            word.update(source)
            break


# ============================================================
# 原有概率系统
# ============================================================

def calculate_probability_weight(
    word: Dict[str, Any],
    question_type: str,
) -> float:
    if question_type == "中译英":
        weight_key = "cn_to_en_weight"
        unseen_key = "cn_to_en_not_seen"
    else:
        weight_key = "en_to_cn_weight"
        unseen_key = "en_to_cn_not_seen"

    base_weight = max(
        1,
        as_int(word.get(weight_key), 3),
    )

    not_seen = max(
        0,
        as_int(word.get(unseen_key), 0),
    )

    if not_seen < 3:
        bonus = 0
    elif not_seen < 6:
        bonus = 0.5
    elif not_seen < 11:
        bonus = 1
    elif not_seen < 21:
        bonus = 2
    elif not_seen < 31:
        bonus = 3
    else:
        bonus = 4

    return base_weight + bonus


def weighted_pick(
    candidates: List[Dict[str, Any]],
    weights: Iterable[float],
) -> Optional[Dict[str, Any]]:
    if not candidates:
        return None

    values = [
        max(0.01, float(weight))
        for weight in weights
    ]

    return random.choices(
        candidates,
        weights=values,
        k=1,
    )[0]


# ============================================================
# 普通复习优先级系统
# ============================================================

def draw_normal_review_word() -> Optional[Dict[str, Any]]:
    candidates = [
        word
        for word in words
        if not as_bool(word.get("proficient"))
    ]

    if not candidates:
        return None

    # 完全不使用随机概率。
    # 优先选择优先级最高的词；
    # 同优先级时，选择最久没有出现的词。
    candidates.sort(
        key=lambda word: (
            -as_int(word.get("priority"), INITIAL_PRIORITY),
            as_int(word.get("last_review_order"), 0),
        )
    )

    return candidates[0]


def update_normal_priority(
    word: Dict[str, Any],
    correct: bool,
) -> bool:
    """
    返回值表示本次是否刚好进入熟练状态。
    """

    promoted = False

    if correct:
        word["correct_streak"] = (
            as_int(word.get("correct_streak"), 0) + 1
        )
        word["wrong_streak"] = 0

        # 连续答对时，减少幅度逐步增大：
        # -1、-2、-3、-4、-4……
        decrease = min(
            4,
            word["correct_streak"],
        )

        old_priority = as_int(
            word.get("priority"),
            INITIAL_PRIORITY,
        )

        new_priority = max(
            MIN_PRIORITY,
            old_priority - decrease,
        )

        word["priority"] = new_priority

        if (
            old_priority > 0
            and new_priority == 0
        ):
            word["proficient"] = True
            promoted = True

    else:
        word["wrong_streak"] = (
            as_int(word.get("wrong_streak"), 0) + 1
        )
        word["correct_streak"] = 0

        # 连续答错时，增加幅度逐步增大：
        # +1、+2、+3、+4、+4……
        increase = min(
            4,
            word["wrong_streak"],
        )

        old_priority = as_int(
            word.get("priority"),
            INITIAL_PRIORITY,
        )

        word["priority"] = min(
            MAX_PRIORITY,
            old_priority + increase,
        )

    return promoted


# ============================================================
# 答题记录
# ============================================================

def normalize_answer(value: Any) -> str:
    text = str(value or "").strip().casefold()
    text = re.sub(r"[\u3000\s]+", " ", text)
    return text.strip(
        " .,!?;:，。！？；：、"
    )


def is_answer_correct(
    answer: str,
    expected: Any,
) -> bool:
    given = normalize_answer(answer)

    if not given:
        return False

    expected_text = normalize_answer(expected)

    if given == expected_text:
        return True

    options = re.split(
        r"[/／|｜;,；、]+",
        str(expected),
    )

    return given in {
        normalize_answer(option)
        for option in options
        if normalize_answer(option)
    }


def update_not_seen(
    pool: Iterable[Dict[str, Any]],
    question_type: str,
    selected_id: str,
) -> None:
    if question_type == "中译英":
        key = "cn_to_en_not_seen"
    else:
        key = "en_to_cn_not_seen"

    for word in pool:
        if str(word.get("id")) == str(selected_id):
            word[key] = 0
        else:
            word[key] = (
                as_int(word.get(key), 0) + 1
            )


def increment_daily_stats(
    question_type: str,
    correct: bool,
) -> None:
    if question_type == "中译英":
        prefix = "cn_to_en"
    else:
        prefix = "en_to_cn"

    answered_key = f"{prefix}_answered"
    correct_key = f"{prefix}_correct"

    daily_stats[answered_key] = (
        as_int(daily_stats.get(answered_key), 0) + 1
    )

    if correct:
        daily_stats[correct_key] = (
            as_int(daily_stats.get(correct_key), 0) + 1
        )


def record_answer(
    word: Dict[str, Any],
    question_type: str,
    correct: bool,
    mode: str,
) -> bool:
    if question_type == "中译英":
        prefix = "cn_to_en"
    else:
        prefix = "en_to_cn"

    if correct:
        result_key = f"{prefix}_correct"
    else:
        result_key = f"{prefix}_wrong"

    word[result_key] = (
        as_int(word.get(result_key), 0) + 1
    )

    promoted = False

    if mode == "普通":
        promoted = update_normal_priority(
            word,
            correct,
        )
    else:
        weight_key = f"{prefix}_weight"

        current_weight = max(
            1,
            as_int(word.get(weight_key), 3),
        )

        if correct:
            word[weight_key] = max(
                1,
                current_weight - 1,
            )
        else:
            word[weight_key] = current_weight + 1

    word["correct"] = (
        as_int(word.get("cn_to_en_correct"), 0)
        + as_int(word.get("en_to_cn_correct"), 0)
    )

    word["wrong"] = (
        as_int(word.get("cn_to_en_wrong"), 0)
        + as_int(word.get("en_to_cn_wrong"), 0)
    )

    if mode == "普通":
        review_counter = (
            as_int(
                st.session_state.get(
                    "review_counter",
                    0,
                )
            ) + 1
        )

        st.session_state.review_counter = review_counter
        word["last_review_order"] = review_counter

    return promoted


def question_prompt(
    word: Dict[str, Any],
    question_type: str,
) -> Tuple[str, str, str]:
    if question_type == "中译英":
        return (
            str(word.get("chinese", "")),
            str(word.get("english", "")),
            "请输入英文",
        )

    return (
        str(word.get("english", "")),
        str(word.get("chinese", "")),
        "请输入中文",
    )


# ============================================================
# 新词系统
# ============================================================

def new_word_pool() -> List[Dict[str, Any]]:
    return [
        word
        for word in new_words_data.get("words", [])
        if word.get("english")
    ]


def completed_new_word_ids(
    question_type: str,
) -> set:
    return {
        str(word_id)
        for word_id in new_words_data.setdefault(
            "rounds",
            {},
        ).setdefault(
            question_type,
            [],
        )
    }


def draw_new_question(
    question_type: str,
) -> Optional[Dict[str, str]]:
    pool = new_word_pool()

    if not pool:
        return None

    completed_ids = completed_new_word_ids(
        question_type
    )

    candidates = [
        word
        for word in pool
        if str(word.get("id")) not in completed_ids
    ]

    # 当前方向所有词都答对后，开启新一轮。
    if not candidates:
        new_words_data["rounds"][question_type] = []
        candidates = pool

    selected = weighted_pick(
        candidates,
        [
            calculate_probability_weight(
                word,
                question_type,
            )
            for word in candidates
        ],
    )

    if selected is None:
        return None

    return {
        "word_id": str(selected.get("id")),
        "question_type": question_type,
    }


def add_new_words(
    count: int,
    category: str,
) -> int:
    existing_ids = {
        str(word.get("id"))
        for word in new_word_pool()
    }

    candidates = [
        word
        for word in words
        if str(word.get("id")) not in existing_ids
        and word.get("english")
        and (
            category == "全部"
            or word.get("category") == category
        )
    ]

    if not candidates:
        return 0

    selected = random.sample(
        candidates,
        min(count, len(candidates)),
    )

    for word in selected:
        new_words_data["words"].append(
            dict(word)
        )

    return len(selected)


# ============================================================
# 新词发音列表
# ============================================================

def render_pronunciation_list(
    items: List[Dict[str, Any]],
) -> None:
    rows = []

    for index, word in enumerate(items):
        english = html.escape(
            str(word.get("english", ""))
        )
        chinese = html.escape(
            str(word.get("chinese", ""))
        )
        category = html.escape(
            str(word.get("category", ""))
        )

        speech_word = json.dumps(
            str(word.get("english", "")),
            ensure_ascii=False,
        )

        rows.append(
            f"""
            <tr>
                <td>{index + 1}</td>
                <td>
                    <strong>{english}</strong>
                    <button
                        class="speak"
                        onclick='speak({speech_word})'>
                        🔊
                    </button>
                </td>
                <td>{chinese}</td>
                <td>{category}</td>
            </tr>
            """
        )

    markup = f"""
    <style>
        body {{
            font-family: sans-serif;
            margin: 0;
            color: #222;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }}

        td {{
            padding: 8px 6px;
            border-bottom: 1px solid #e5e5e5;
        }}

        td:first-child {{
            width: 35px;
            color: #888;
        }}

        .speak {{
            border: none;
            border-radius: 6px;
            background: #eef4ff;
            padding: 3px 8px;
            cursor: pointer;
        }}

        .speak:hover {{
            background: #d5e5ff;
        }}
    </style>

    <table>
        <thead>
            <tr>
                <td>#</td>
                <td>English</td>
                <td>中文</td>
                <td>词性</td>
            </tr>
        </thead>
        <tbody>
            {"".join(rows)}
        </tbody>
    </table>

    <script>
        function speak(text) {{
            if (!("speechSynthesis" in window)) {{
                alert("当前浏览器不支持发音");
                return;
            }}

            window.speechSynthesis.cancel();

            const utterance =
                new SpeechSynthesisUtterance(text);

            utterance.lang = "en-US";
            utterance.rate = 0.85;

            window.speechSynthesis.speak(utterance);
        }}
    </script>
    """

    components.html(
        markup,
        height=max(
            100,
            min(650, 50 + len(items) * 43),
        ),
        scrolling=True,
    )


# ============================================================
# 新词页面
# ============================================================

def render_new_words_page() -> None:
    st.title("🆕 新词")

    st.caption(
        "中译英和英译中的轮次独立记录。"
        "只有当前方向的全部新词都答对一轮后，"
        "已经答对的词才会重新出现。"
    )

    with st.expander(
        "添加今日新词",
        expanded=not bool(new_word_pool()),
    ):
        col1, col2, col3 = st.columns(3)

        with col1:
            count = st.number_input(
                "添加数量",
                min_value=1,
                max_value=100,
                value=10,
                step=1,
            )

        with col2:
            category = st.selectbox(
                "词性",
                ["全部"] + CATEGORIES,
                key="new_category",
            )

        with col3:
            st.write("")

            if st.button(
                "从词库抽取",
                type="primary",
                use_container_width=True,
            ):
                added = add_new_words(
                    int(count),
                    category,
                )

                if added:
                    save_new_words()
                    st.success(f"已添加 {added} 个新词。")
                    st.rerun()
                else:
                    st.info(
                        "没有找到符合条件的新词。"
                    )

    items = new_word_pool()

    if not items:
        st.info("今日还没有新词。")
        return

    st.subheader(
        f"今日新词列表（{len(items)} 个）"
    )

    render_pronunciation_list(items)

    col1, col2 = st.columns(2)

    with col1:
        question_type = st.selectbox(
            "练习方向",
            QUESTION_TYPES,
            key="new_question_type",
        )

    with col2:
        completed = len(
            completed_new_word_ids(question_type)
        )

        st.metric(
            "当前方向已答对",
            f"{completed}/{len(items)}",
        )

    current = st.session_state.get(
        "new_current"
    )

    if (
        not current
        or current.get("question_type")
        != question_type
    ):
        current = draw_new_question(
            question_type
        )

        st.session_state.new_current = current
        st.session_state.new_feedback = None

    if not current:
        st.info("当前没有可练习的词。")
        return

    word = word_by_id(current["word_id"])

    if word is None:
        st.session_state.new_current = None
        st.rerun()

    prompt, expected, placeholder = question_prompt(
        word,
        question_type,
    )

    st.divider()
    st.markdown(f"### {html.escape(prompt)}")
    st.caption(
        f"词性：{word.get('category', 'noun')}"
    )

    with st.form(
        "new_answer_form",
        clear_on_submit=True,
    ):
        answer = st.text_input(placeholder)
        submitted = st.form_submit_button(
            "提交答案",
            type="primary",
        )

    feedback = st.session_state.get(
        "new_feedback"
    )

    if submitted and not feedback:
        correct = is_answer_correct(
            answer,
            expected,
        )

        record_answer(
            word,
            question_type,
            correct,
            "熟练",
        )

        update_not_seen(
            items,
            question_type,
            current["word_id"],
        )

        if correct:
            round_ids = new_words_data[
                "rounds"
            ].setdefault(
                question_type,
                [],
            )

            if current["word_id"] not in {
                str(value)
                for value in round_ids
            }:
                round_ids.append(
                    current["word_id"]
                )

        sync_new_word(
            current["word_id"]
        )

        increment_daily_stats(
            question_type,
            correct,
        )

        save_words()
        save_new_words()
        save_daily_stats()

        st.session_state.new_feedback = {
            "correct": correct,
            "expected": expected,
        }

        st.rerun()

    feedback = st.session_state.get(
        "new_feedback"
    )

    if feedback:
        if feedback["correct"]:
            st.success("回答正确！")
        else:
            st.error(
                f"回答不正确。正确答案："
                f"{feedback['expected']}"
            )

        if st.button(
            "下一题",
            type="primary",
            key="new_next",
        ):
            st.session_state.new_feedback = None
            st.session_state.new_current = (
                draw_new_question(question_type)
            )
            st.rerun()


# ============================================================
# 复习页面
# ============================================================

def review_pool(mode: str) -> List[Dict[str, Any]]:
    if mode == "普通":
        return [
            word
            for word in words
            if not as_bool(
                word.get("proficient")
            )
        ]

    return [
        word
        for word in words
        if as_bool(word.get("proficient"))
    ]


def draw_review_question(
    mode: str,
    question_type: str,
) -> Optional[Dict[str, str]]:
    pool = review_pool(mode)

    if not pool:
        return None

    if mode == "普通":
        selected = draw_normal_review_word()
    else:
        selected = weighted_pick(
            pool,
            [
                calculate_probability_weight(
                    word,
                    question_type,
                )
                for word in pool
            ],
        )

    if selected is None:
        return None

    return {
        "word_id": str(selected.get("id")),
        "mode": mode,
        "question_type": question_type,
    }


def render_review_page() -> None:
    st.title("🔁 复习")

    mode = st.radio(
        "复习子页面",
        ["普通", "熟练"],
        horizontal=True,
        key="review_mode",
    )

    if mode == "普通":
        st.caption(
            "普通复习完全使用优先级队列，"
            "不使用原有概率系统。"
            "优先级越高，越优先出现。"
        )
    else:
        st.caption(
            "熟练复习继续使用原有概率系统，"
            "仅复习已勾选为熟练的词。"
        )

    pool = review_pool(mode)

    if not pool:
        st.info(
            "当前页面没有可复习的词。"
        )
        return

    col1, col2, col3 = st.columns(3)

    with col1:
        question_type = st.selectbox(
            "练习方向",
            QUESTION_TYPES,
            key="review_question_type",
        )

    with col2:
        st.metric(
            "可复习词数",
            len(pool),
        )

    with col3:
        if mode == "普通":
            st.metric(
                "最高优先级",
                max(
                    as_int(
                        word.get(
                            "priority"
                        ),
                        INITIAL_PRIORITY,
                    )
                    for word in pool
                ),
            )
        else:
            st.metric(
                "熟练词数",
                len(pool),
            )

    current = st.session_state.get(
        "review_current"
    )

    if (
        not current
        or current.get("mode") != mode
        or current.get("question_type")
        != question_type
    ):
        current = draw_review_question(
            mode,
            question_type,
        )

        st.session_state.review_current = current
        st.session_state.review_feedback = None

    if not current:
        return

    word = word_by_id(
        current["word_id"]
    )

    if word is None:
        st.session_state.review_current = None
        st.rerun()

    prompt, expected, placeholder = question_prompt(
        word,
        question_type,
    )

    st.divider()
    st.markdown(f"### {html.escape(prompt)}")

    st.caption(
        f"词性：{word.get('category', 'noun')}  |  "
        f"当前优先级：{word.get('priority', INITIAL_PRIORITY)}"
    )

    if mode == "普通":
        st.caption(
            f"连续答对："
            f"{word.get('correct_streak', 0)}  |  "
            f"连续答错："
            f"{word.get('wrong_streak', 0)}"
        )

    with st.form(
        "review_answer_form",
        clear_on_submit=True,
    ):
        answer = st.text_input(placeholder)

        mark_proficient = st.checkbox(
            "本题后标记为熟练",
            value=as_bool(
                word.get("proficient")
            ),
        )

        submitted = st.form_submit_button(
            "提交答案",
            type="primary",
        )

    feedback = st.session_state.get(
        "review_feedback"
    )

    if submitted and not feedback:
        correct = is_answer_correct(
            answer,
            expected,
        )

        promoted = record_answer(
            word,
            question_type,
            correct,
            mode,
        )

        update_not_seen(
            pool,
            question_type,
            current["word_id"],
        )

        if mode == "普通":
            word["proficient"] = bool(
                mark_proficient or promoted
            )
        else:
            word["proficient"] = bool(
                mark_proficient
            )

        increment_daily_stats(
            question_type,
            correct,
        )

        save_words()
        save_daily_stats()

        st.session_state.review_feedback = {
            "correct": correct,
            "expected": expected,
            "promoted": promoted,
        }

        st.rerun()

    feedback = st.session_state.get(
        "review_feedback"
    )

    if feedback:
        if feedback["correct"]:
            st.success("回答正确！")
        else:
            st.error(
                f"回答不正确。正确答案："
                f"{feedback['expected']}"
            )

        if feedback.get("promoted"):
            st.success(
                f"🎉 {word.get('english', '')} "
                "已达到优先级 0，"
                "自动进入熟练词库。"
            )
            st.toast(
                f"{word.get('english', '')} "
                "已进入熟练词库"
            )

        if st.button(
            "下一题",
            type="primary",
            key="review_next",
        ):
            st.session_state.review_feedback = None
            st.session_state.review_current = (
                draw_review_question(
                    mode,
                    question_type,
                )
            )
            st.rerun()


# ============================================================
# 词库列表
# ============================================================

def vocabulary_dataframe(
    display_words: List[Dict[str, Any]],
) -> pd.DataFrame:
    rows = []

    for word in display_words:
        rows.append(
            {
                "_id": str(word.get("id")),
                "English": word.get("english", ""),
                "中文": word.get("chinese", ""),
                "词性": word.get("category", "noun"),
                "熟练": as_bool(
                    word.get("proficient")
                ),
                "优先级": as_int(
                    word.get("priority"),
                    INITIAL_PRIORITY,
                ),
                "中译英权重": as_int(
                    word.get("cn_to_en_weight"),
                    3,
                ),
                "英译中权重": as_int(
                    word.get("en_to_cn_weight"),
                    3,
                ),
                "中文备注": word.get(
                    "cn_note",
                    "",
                ),
                "英文备注": word.get(
                    "en_note",
                    "",
                ),
            }
        )

    return pd.DataFrame(rows)


def apply_dataframe_changes(
    edited: pd.DataFrame,
) -> int:
    changed_count = 0

    if edited.empty:
        return 0

    for _, row in edited.iterrows():
        word = word_by_id(
            str(row.get("_id"))
        )

        if word is None:
            continue

        before = json.dumps(
            word,
            ensure_ascii=False,
            sort_keys=True,
        )

        category = row.get(
            "词性",
            "noun",
        )

        if category not in CATEGORIES:
            category = "noun"

        word["category"] = category
        word["proficient"] = as_bool(
            row.get("熟练", False)
        )
        word["priority"] = max(
            MIN_PRIORITY,
            min(
                MAX_PRIORITY,
                as_int(
                    row.get("优先级"),
                    INITIAL_PRIORITY,
                ),
            ),
        )
        word["cn_to_en_weight"] = max(
            1,
            as_int(
                row.get("中译英权重"),
                3,
            ),
        )
        word["en_to_cn_weight"] = max(
            1,
            as_int(
                row.get("英译中权重"),
                3,
            ),
        )
        word["cn_note"] = str(
            row.get("中文备注", "")
        )
        word["en_note"] = str(
            row.get("英文备注", "")
        )

        normalize_word(word)

        after = json.dumps(
            word,
            ensure_ascii=False,
            sort_keys=True,
        )

        if before != after:
            changed_count += 1

    return changed_count


def render_vocabulary_page() -> None:
    st.title("📖 词库列表")

    st.caption(
        "可以直接编辑表格。"
        "也可以选择词性后，"
        "将当前筛选结果整列修改。"
    )

    if not words:
        st.info(
            "词库为空，或者尚未连接 GitHub。"
        )
        return

    col1, col2 = st.columns([2, 1])

    with col1:
        search = st.text_input(
            "搜索英文或中文",
            key="vocabulary_search",
        )

    with col2:
        category_filter = st.selectbox(
            "筛选词性",
            ["全部"] + CATEGORIES,
            key="vocabulary_category",
        )

    filtered = [
        word
        for word in words
        if (
            not search
            or search.casefold()
            in str(
                word.get("english", "")
            ).casefold()
            or search
            in str(
                word.get("chinese", "")
            )
        )
        and (
            category_filter == "全部"
            or word.get("category")
            == category_filter
        )
    ]

    st.subheader("批量修改词性")

    bulk_col1, bulk_col2, bulk_col3 = st.columns(
        [1, 1, 2]
    )

    with bulk_col1:
        bulk_category = st.selectbox(
            "整列改为",
            CATEGORIES,
            key="bulk_category",
        )

    with bulk_col2:
        st.write("")

        if st.button(
            "整列设置词性",
            use_container_width=True,
        ):
            for word in filtered:
                word["category"] = bulk_category

            if save_words():
                st.success(
                    f"已修改 {len(filtered)} 个词条。"
                )
                st.rerun()

    with bulk_col3:
        st.info(
            f"当前显示 {len(filtered)} / "
            f"{len(words)} 个词条。"
        )

    edited = st.data_editor(
        vocabulary_dataframe(filtered),
        key="vocabulary_editor",
        hide_index=True,
        use_container_width=True,
        num_rows="fixed",
        column_config={
            "_id": None,
            "English": st.column_config.TextColumn(
                "English",
                disabled=True,
            ),
            "中文": st.column_config.TextColumn(
                "中文",
                disabled=True,
            ),
            "词性": st.column_config.SelectboxColumn(
                "词性",
                options=CATEGORIES,
            ),
            "熟练": st.column_config.CheckboxColumn(
                "熟练",
            ),
            "优先级": st.column_config.NumberColumn(
                "优先级",
                min_value=0,
                max_value=MAX_PRIORITY,
                step=1,
            ),
            "中译英权重": st.column_config.NumberColumn(
                "中译英权重",
                min_value=1,
                step=1,
            ),
            "英译中权重": st.column_config.NumberColumn(
                "英译中权重",
                min_value=1,
                step=1,
            ),
        },
    )

    if st.button(
        "保存表格修改",
        type="primary",
    ):
        changed_count = apply_dataframe_changes(
            edited
        )

        if changed_count:
            if save_words():
                st.success(
                    f"已保存 {changed_count} 条词条。"
                )
                st.rerun()
        else:
            st.info("没有检测到修改。")

    with st.expander("添加词条"):
        with st.form(
            "add_word_form",
            clear_on_submit=True,
        ):
            col1, col2, col3 = st.columns(3)

            with col1:
                english = st.text_input("English")

            with col2:
                chinese = st.text_input("中文")

            with col3:
                category = st.selectbox(
                    "词性",
                    CATEGORIES,
                    key="add_category",
                )

            col4, col5 = st.columns(2)

            with col4:
                cn_note = st.text_input(
                    "中文备注"
                )

            with col5:
                en_note = st.text_input(
                    "英文备注"
                )

            add_submit = st.form_submit_button(
                "加入词库",
                type="primary",
            )

        if add_submit:
            if not english.strip() or not chinese.strip():
                st.error(
                    "English 和中文不能为空。"
                )
            else:
                new_word = {
                    "english": english.strip(),
                    "chinese": chinese.strip(),
                    "category": category,
                    "cn_note": cn_note.strip(),
                    "en_note": en_note.strip(),
                    "initial_priority": INITIAL_PRIORITY,
                    "priority": INITIAL_PRIORITY,
                }

                normalize_word(
                    new_word,
                    len(words),
                )

                words.append(new_word)

                if save_words():
                    st.success(
                        "词条已加入词库。"
                    )
                    st.rerun()


# ============================================================
# 统计页面
# ============================================================

def render_statistics_page() -> None:
    st.title("📊 今日统计")

    cn_answered = as_int(
        daily_stats.get(
            "cn_to_en_answered"
        )
    )

    cn_correct = as_int(
        daily_stats.get(
            "cn_to_en_correct"
        )
    )

    en_answered = as_int(
        daily_stats.get(
            "en_to_cn_answered"
        )
    )

    en_correct = as_int(
        daily_stats.get(
            "en_to_cn_correct"
        )
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "中译英答题",
        cn_answered,
    )

    col2.metric(
        "中译英正确率",
        (
            f"{cn_correct / cn_answered:.0%}"
            if cn_answered
            else "—"
        ),
    )

    col3.metric(
        "英译中答题",
        en_answered,
    )

    col4.metric(
        "英译中正确率",
        (
            f"{en_correct / en_answered:.0%}"
            if en_answered
            else "—"
        ),
    )

    st.divider()

    proficient_count = sum(
        as_bool(word.get("proficient"))
        for word in words
    )

    st.write(
        f"词库总数：{len(words)}　|　"
        f"熟练词数：{proficient_count}　|　"
        f"普通复习：{len(words) - proficient_count}"
    )


# ============================================================
# 页面入口
# ============================================================

def main() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            max-width: 1180px;
            padding-top: 2rem;
        }

        h1 {
            font-size: 28px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if not github_enabled():
        st.warning(
            "未检测到 GITHUB_TOKEN。"
            "页面可以打开，但无法保存数据。"
        )

    with st.sidebar:
        st.title("📚 Vocabulary")

        page = st.radio(
            "功能",
            ["新词", "复习", "词库", "统计"],
            key="page",
        )

        st.divider()
        st.caption(f"数据日期：{get_today()}")

    if page == "新词":
        render_new_words_page()
    elif page == "复习":
        render_review_page()
    elif page == "词库":
        render_vocabulary_page()
    else:
        render_statistics_page()


if __name__ == "__main__":
    main()
