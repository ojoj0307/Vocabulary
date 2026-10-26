import streamlit as st
import json
import random
import base64
import html
import requests
import pandas as pd

from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo


# ============================================================
# 页面设置
# ============================================================

st.set_page_config(
    page_title="English Vocabulary",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ============================================================
# GitHub 设置
# ============================================================


GITHUB_OWNER = "ojoj0307"
GITHUB_REPO = "Vocabulary"

VOCABULARY_PATH = "vocabulary.json"
NEW_WORDS_PATH = "new_words.json"
DAILY_STATS_PATH = "daily_stats.json"
REVIEW_SETTINGS_PATH = "review_settings.json"

try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
except Exception:
    GITHUB_TOKEN = ""

GITHUB_API_BASE = (
    f"https://api.github.com/repos/"
    f"{GITHUB_OWNER}/{GITHUB_REPO}/contents/"
)


# ============================================================
# 马来西亚时间
# ============================================================

MALAYSIA_TZ = ZoneInfo("Asia/Kuala_Lumpur")


# ============================================================
# 词性
# ============================================================

CATEGORIES = [
    "noun",
    "verb",
    "phrasal verb",
    "adjective",
    "adverb"
]


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
<style>

.block-container {
    padding-top: 2.5rem;
    padding-bottom: 0.5rem;
    max-width: 1150px;
}

h1 {
    font-size: 26px !important;
    margin-bottom: 5px !important;
}

h2 {
    font-size: 21px !important;
}

h3 {
    font-size: 18px !important;
}

section[data-testid="stSidebar"] div[role="radiogroup"] label {
    font-size: 19px !important;
    font-weight: 600 !important;
    padding-top: 8px !important;
    padding-bottom: 8px !important;
}

section[data-testid="stSidebar"] p {
    font-size: 18px !important;
    font-weight: 600 !important;
}

.question {
    font-size: 30px;
    font-weight: 600;
    text-align: center;
    margin: 8px 0 6px 0;
    word-break: break-word;
}

.question-category {
    font-size: 17px;
    font-weight: 500;
    text-align: center;
    margin-bottom: 12px;
    opacity: 0.75;
}

.previous-question {
    font-size: 24px;
    font-weight: 600;
    text-align: center;
    margin: 8px 0 6px 0;
    word-break: break-word;
}

.previous-category {
    font-size: 16px;
    font-weight: 500;
    text-align: center;
    margin-bottom: 12px;
    opacity: 0.75;
}

.answer-text {
    font-size: 16px;
    margin: 5px 0;
    word-break: break-word;
}

div[data-testid="stTextInput"] input {
    font-size: 18px;
    height: 42px;
}

div.stButton > button {
    min-height: 38px;
    font-size: 13px !important;
    padding-left: 2px !important;
    padding-right: 2px !important;
}

.mobile-hint {
    font-size: 13px;
    opacity: 0.65;
    margin-bottom: 8px;
}

@media (max-width: 700px) {

    .block-container {
        padding-top: 2.5rem;
        padding-left: 0.7rem;
        padding-right: 0.7rem;
    }

    .question {
        font-size: 25px;
    }

    .question-category {
        font-size: 16px;
    }

    .previous-question {
        font-size: 21px;
    }

    .previous-category {
        font-size: 15px;
    }

    section[data-testid="stSidebar"]
    div[role="radiogroup"] label {
        font-size: 18px !important;
    }

}

</style>
""",
    unsafe_allow_html=True
)


# ============================================================
# GitHub Header
# ============================================================

def github_headers():

    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }


# ============================================================
# 检查 Token
# ============================================================

def check_github_token():

    if not GITHUB_TOKEN:

        st.error("没有找到 GITHUB_TOKEN。")

        st.info(
            "请在 Streamlit Cloud → Settings → Secrets "
            "添加 GITHUB_TOKEN。"
        )

        return False

    return True


# ============================================================
# GitHub 读取
# ============================================================

def github_get_file(path):

    if not check_github_token():
        return None, None

    url = GITHUB_API_BASE + path

    try:

        response = requests.get(
            url,
            headers=github_headers(),
            timeout=15
        )

        if response.status_code == 200:

            result = response.json()

            content = result.get("content", "")
            sha = result.get("sha")

            content = content.replace("\n", "")

            decoded = base64.b64decode(
                content
            ).decode("utf-8")

            return decoded, sha

        elif response.status_code == 404:

            return None, None

        else:

            st.error(
                f"GitHub API 错误："
                f"{response.status_code} "
                f"{response.text}"
            )

            return None, None

    except Exception as e:

        st.error(
            f"无法连接 GitHub：{e}"
        )

        return None, None


# ============================================================
# GitHub 保存
# ============================================================

def github_save_file(
    path,
    data,
    sha=None,
    message="Update file"
):

    if not check_github_token():
        return False

    url = GITHUB_API_BASE + path

    try:

        json_text = json.dumps(
            data,
            ensure_ascii=False,
            indent=4
        )

        encoded = base64.b64encode(
            json_text.encode("utf-8")
        ).decode("utf-8")

        payload = {
            "message": message,
            "content": encoded
        }

        if sha:
            payload["sha"] = sha

        response = requests.put(
            url,
            headers=github_headers(),
            json=payload,
            timeout=15
        )

        if response.status_code in [200, 201]:
            # GitHub returns the new SHA in the PUT response. Keep it in the
            # session so saving does not need another GET request just for SHA.
            try:
                saved_sha = response.json().get("content", {}).get("sha")
                if saved_sha:
                    st.session_state[f"_github_sha_{path}"] = saved_sha
            except Exception:
                pass
            return True

        st.error(
            f"GitHub API 错误："
            f"{response.status_code} "
            f"{response.text}"
        )

        return False

    except Exception as e:

        st.error(
            f"保存到 GitHub 失败：{e}"
        )

        return False


# ============================================================
# 今日日期
# ============================================================

def get_today():

    return datetime.now(
        MALAYSIA_TZ
    ).strftime("%Y-%m-%d")


# ============================================================
# 未熟练模式：间隔复习
# ============================================================

REVIEW_INTERVALS = [1, 3, 7, 14, 28]


def normalize_review_date(value):
    try:
        return date.fromisoformat(str(value)).isoformat()
    except (TypeError, ValueError):
        return get_today()


def initialize_review_fields(word):
    """补齐旧词的间隔复习字段；旧词默认今天到期，避免被漏掉。"""
    changed = False
    for direction in ("cn_to_en", "en_to_cn"):
        stage_key = f"{direction}_stage"
        next_key = f"{direction}_next_review"
        last_key = f"{direction}_last_review"

        try:
            stage = max(0, min(4, int(word.get(stage_key, 0))))
        except (TypeError, ValueError):
            stage = 0
        if word.get(stage_key) != stage:
            word[stage_key] = stage
            changed = True

        if not word.get(next_key):
            word[next_key] = get_today()
            changed = True
        else:
            normalized = normalize_review_date(word[next_key])
            if word[next_key] != normalized:
                word[next_key] = normalized
                changed = True

        if last_key not in word:
            word[last_key] = None
            changed = True
    return changed


def update_unmastered_review(word, q_type, is_correct):
    """独立更新一个方向的复习阶段和下次复习日期。"""
    direction = "cn_to_en" if q_type == "中译英" else "en_to_cn"
    stage_key = f"{direction}_stage"
    next_key = f"{direction}_next_review"
    last_key = f"{direction}_last_review"
    prof_key = f"{direction}_proficient"

    try:
        stage = max(0, min(4, int(word.get(stage_key, 0))))
    except (TypeError, ValueError):
        stage = 0

    today = datetime.now(MALAYSIA_TZ).date()
    word[last_key] = today.isoformat()

    if is_correct:
        if stage >= 4:
            word[prof_key] = True
            word[next_key] = None
            word[stage_key] = 4
            return
        stage += 1

    word[stage_key] = stage
    word[next_key] = (today + timedelta(days=REVIEW_INTERVALS[stage])).isoformat()


def get_due_normal_words(q_type="中译英"):
    prof_key = "cn_to_en_proficient" if q_type == "中译英" else "en_to_cn_proficient"
    next_key = "cn_to_en_next_review" if q_type == "中译英" else "en_to_cn_next_review"
    today = get_today()
    return [
        word for word in words
        if not word.get(prof_key, False)
        and normalize_review_date(word.get(next_key) or today) <= today
    ]


# ============================================================
# 全局复习计划设置（暂停状态）
# ============================================================

def default_review_settings():
    return {"paused": False, "paused_since": None}


def load_review_settings():
    global review_settings_sha
    content, sha = github_get_file(REVIEW_SETTINGS_PATH)
    if content is None:
        data = default_review_settings()
        if github_save_file(REVIEW_SETTINGS_PATH, data, None, "Create review schedule settings"):
            _, sha = github_get_file(REVIEW_SETTINGS_PATH)
        review_settings_sha = sha
        return data

    try:
        data = json.loads(content)
    except Exception:
        data = default_review_settings()
    if not isinstance(data, dict):
        data = default_review_settings()
    for key, value in default_review_settings().items():
        data.setdefault(key, value)
    review_settings_sha = sha
    return data


def save_review_settings():
    global review_settings_sha
    _, latest_sha = github_get_file(REVIEW_SETTINGS_PATH)
    if latest_sha is None:
        return False
    success = github_save_file(
        REVIEW_SETTINGS_PATH, review_settings, latest_sha,
        "Update review schedule settings"
    )
    if success:
        _, review_settings_sha = github_get_file(REVIEW_SETTINGS_PATH)
    return success


# ============================================================
# 默认每日统计
# ============================================================

def default_daily_stats():
    return {
        "date": get_today(),

        # 原有统计：所有复习模式
        "cn_to_en_answered": 0,
        "cn_to_en_correct": 0,
        "en_to_cn_answered": 0,
        "en_to_cn_correct": 0,

        # 新增统计：仅未熟练模式
        "normal_cn_to_en_answered": 0,
        "normal_en_to_cn_answered": 0,
    }


# ============================================================
# 默认新词数据
# ============================================================

def default_new_words():

    return {
        "date": get_today(),
        "words": []
    }


# ============================================================
# 标准化正式词库（中译英与英译中独立掌握状态）
# ============================================================

def normalize_vocabulary(data):

    changed = False

    for word in data:

        if "english" not in word:
            word["english"] = ""
            changed = True

        if "chinese" not in word:
            word["chinese"] = ""
            changed = True

        if "category" not in word:
            word["category"] = "noun"
            changed = True

        if word.get("category") not in CATEGORIES:
            word["category"] = "noun"
            changed = True

        if "cn_note" not in word:
            word["cn_note"] = ""
            changed = True

        if "en_note" not in word:
            word["en_note"] = ""
            changed = True

        # 独立方向的掌握状态
        if "cn_to_en_proficient" not in word:
            old_prof = word.get("proficient", False)
            word["cn_to_en_proficient"] = old_prof
            changed = True

        if "en_to_cn_proficient" not in word:
            old_prof = word.get("proficient", False)
            word["en_to_cn_proficient"] = old_prof
            changed = True

        if "cn_to_en_priority" not in word:
            word["cn_to_en_priority"] = 12
            changed = True

        if "en_to_cn_priority" not in word:
            word["en_to_cn_priority"] = 12
            changed = True

        if "cn_to_en_streak" not in word:
            word["cn_to_en_streak"] = 0
            changed = True

        if "en_to_cn_streak" not in word:
            word["en_to_cn_streak"] = 0
            changed = True

        if initialize_review_fields(word):
            changed = True

        default_w = word.get("weight", 3)
        if "cn_to_en_weight" not in word:
            word["cn_to_en_weight"] = int(default_w)
            changed = True

        if "en_to_cn_weight" not in word:
            word["en_to_cn_weight"] = int(default_w)
            changed = True

        if "cn_to_en_correct" not in word:
            word["cn_to_en_correct"] = int(
                word.get("correct", 0)
            )
            changed = True

        if "cn_to_en_wrong" not in word:
            word["cn_to_en_wrong"] = int(
                word.get("wrong", 0)
            )
            changed = True

        if "en_to_cn_correct" not in word:
            word["en_to_cn_correct"] = 0
            changed = True

        if "en_to_cn_wrong" not in word:
            word["en_to_cn_wrong"] = 0
            changed = True

        if "cn_to_en_not_seen" not in word:
            word["cn_to_en_not_seen"] = 0
            changed = True

        if "en_to_cn_not_seen" not in word:
            word["en_to_cn_not_seen"] = 0
            changed = True

        if "correct" not in word:
            word["correct"] = (
                int(word.get("cn_to_en_correct", 0)) +
                int(word.get("en_to_cn_correct", 0))
            )
            changed = True

        if "wrong" not in word:
            word["wrong"] = (
                int(word.get("cn_to_en_wrong", 0)) +
                int(word.get("en_to_cn_wrong", 0))
            )
            changed = True

    return changed


# ============================================================
# 加载正式词库
# ============================================================

def load_words():

    content, sha = github_get_file(
        VOCABULARY_PATH
    )

    if content is None:

        st.error(
            "无法读取 GitHub 上的 vocabulary.json"
        )

        return [], None

    try:

        data = json.loads(content)

    except Exception as e:

        st.error(
            f"vocabulary.json 格式错误：{e}"
        )

        return [], sha

    if not isinstance(data, list):

        st.error(
            "vocabulary.json 必须是数组。"
        )

        return [], sha

    changed = normalize_vocabulary(data)

    if changed:

        latest_content, latest_sha = github_get_file(
            VOCABULARY_PATH
        )

        if latest_sha:

            if github_save_file(
                VOCABULARY_PATH,
                data,
                latest_sha,
                "Update vocabulary data structure"
            ):

                _, sha = github_get_file(
                    VOCABULARY_PATH
                )

    return data, sha


# ============================================================
# 标准化新词
# ============================================================

def normalize_new_word(word):

    changed = False

    if "english" not in word:
        word["english"] = ""
        changed = True

    if "chinese" not in word:
        word["chinese"] = ""
        changed = True

    if "category" not in word:
        word["category"] = "noun"
        changed = True

    if word.get("category") not in CATEGORIES:
        word["category"] = "noun"
        changed = True

    if "cn_note" not in word:
        word["cn_note"] = ""
        changed = True

    if "en_note" not in word:
        word["en_note"] = ""
        changed = True

    if "cn_to_en_proficient" not in word:
        word["cn_to_en_proficient"] = word.get("proficient", False)
        changed = True

    if "en_to_cn_proficient" not in word:
        word["en_to_cn_proficient"] = word.get("proficient", False)
        changed = True

    if "cn_to_en_round_done" not in word:
        word["cn_to_en_round_done"] = False
        changed = True

    if "en_to_cn_round_done" not in word:
        word["en_to_cn_round_done"] = False
        changed = True

    default_w = word.get("weight", 3)
    if "cn_to_en_weight" not in word:
        word["cn_to_en_weight"] = int(default_w)
        changed = True

    if "en_to_cn_weight" not in word:
        word["en_to_cn_weight"] = int(default_w)
        changed = True

    if "cn_to_en_not_seen" not in word:
        word["cn_to_en_not_seen"] = 0
        changed = True

    if "en_to_cn_not_seen" not in word:
        word["en_to_cn_not_seen"] = 0
        changed = True

    return changed


# ============================================================
# 将昨天的新词迁移到正式词库
# ============================================================

new_word_migration_blocked = False


def promote_previous_new_words(pending_words):

    global vocabulary_sha

    # 获取 GitHub 上最新的正式词库
    latest_content, latest_sha = github_get_file(
        VOCABULARY_PATH
    )

    if latest_content is None or latest_sha is None:
        return False

    try:
        latest_words = json.loads(latest_content)

    except Exception:
        st.error("正式词库 JSON 格式错误，无法迁移新词。")
        return False

    if not isinstance(latest_words, list):
        st.error("正式词库必须是数组，无法迁移新词。")
        return False

    changed = False

    for new_word in pending_words:

        english = str(
            new_word.get("english", "")
        ).strip()

        chinese = str(
            new_word.get("chinese", "")
        ).strip()

        category = new_word.get("category", "noun")

        if not english or not chinese:
            continue

        # 检查正式词库中是否已有相同单词
        exists = any(
            str(item.get("english", "")).strip().lower()
            == english.lower()
            and str(item.get("chinese", "")).strip()
            == chinese
            and item.get("category", "noun") == category
            for item in latest_words
        )

        if exists:
            continue

        # 正式词库只继承单词内容，不继承学习模式记录
        word = {
            "english": english,
            "chinese": chinese,
            "category": category,
            "cn_note": new_word.get("cn_note", ""),
            "en_note": new_word.get("en_note", ""),

            # 两个方向都从未掌握开始
            "cn_to_en_proficient": False,
            "en_to_cn_proficient": False,

            # 间隔复习状态：加入正式词库当天到期
            "cn_to_en_stage": 0,
            "en_to_cn_stage": 0,
            "cn_to_en_next_review": get_today(),
            "en_to_cn_next_review": get_today(),
            "cn_to_en_last_review": None,
            "en_to_cn_last_review": None,

            # 普通模式的初始权重
            "cn_to_en_weight": 3,
            "en_to_cn_weight": 3,

            # 普通模式答题统计
            "cn_to_en_correct": 0,
            "cn_to_en_wrong": 0,
            "en_to_cn_correct": 0,
            "en_to_cn_wrong": 0,

            # 普通模式未出现次数
            "cn_to_en_not_seen": 0,
            "en_to_cn_not_seen": 0,

            # 兼容现有统计字段
            "correct": 0,
            "wrong": 0
        }

        latest_words.append(word)
        changed = True

    # 补齐正式词库需要的数据字段
    normalize_vocabulary(latest_words)

    # 只有新增了单词，才保存正式词库
    if changed:

        success = github_save_file(
            VOCABULARY_PATH,
            latest_words,
            latest_sha,
            "Promote yesterday's new words"
        )

        if not success:
            return False

        _, vocabulary_sha = github_get_file(
            VOCABULARY_PATH
        )

    # 更新当前程序内存中的正式词库
    words[:] = latest_words

    return True


# ============================================================
# 加载新词
# ============================================================

def load_new_words():

    global new_word_migration_blocked

    content, sha = github_get_file(
        NEW_WORDS_PATH
    )

    if content is None:

        data = default_new_words()

        success = github_save_file(
            NEW_WORDS_PATH,
            data,
            None,
            "Create new words"
        )

        if success:

            _, sha = github_get_file(
                NEW_WORDS_PATH
            )

        return data, sha

    try:

        raw_data = json.loads(content)

    except Exception:

        raw_data = default_new_words()

    if isinstance(raw_data, list):

        data = {
            "date": get_today(),
            "words": raw_data
        }

        changed = True

    elif isinstance(raw_data, dict):

        data = raw_data
        changed = False

    else:

        data = default_new_words()
        changed = True

    if "date" not in data:

        data["date"] = get_today()
        changed = True

    if "words" not in data:

        data["words"] = []
        changed = True

    if not isinstance(data["words"], list):

        data["words"] = []
        changed = True


    today = get_today()

    # 暂停期间不自动迁移昨天的新词。
    if review_settings.get("paused", False):
        pass
    elif data["date"] != today:

        previous_words = list(data["words"])

        migration_success = promote_previous_new_words(
            previous_words
        )

        if migration_success:
            data["date"] = today
            data["words"] = []
            changed = True

        else:
            new_word_migration_blocked = True

            st.error(
                "昨天的新词尚未成功加入正式词库。"
                "原有新词数据已保留，请检查 GitHub 保存权限后重试。"
            )

    for word in data["words"]:

        if normalize_new_word(word):
            changed = True

    if changed:

        latest_content, latest_sha = github_get_file(
            NEW_WORDS_PATH
        )

        if latest_sha:

            if github_save_file(
                NEW_WORDS_PATH,
                data,
                latest_sha,
                "Update daily new words"
            ):

                _, sha = github_get_file(
                    NEW_WORDS_PATH
                )

    return data, sha

# ============================================================
# 每日统计
# ============================================================


def load_daily_stats():

    content, sha = github_get_file(
        DAILY_STATS_PATH
    )

    if content is None:

        data = default_daily_stats()

        success = github_save_file(
            DAILY_STATS_PATH,
            data,
            None,
            "Create daily statistics"
        )

        if success:
            _, sha = github_get_file(
                DAILY_STATS_PATH
            )

        return data, sha

    try:
        data = json.loads(content)

    except Exception:
        data = default_daily_stats()

    # 确保每日统计数据是字典
    if not isinstance(data, dict):
        data = default_daily_stats()

    changed = False
    today = get_today()

    # 日期改变时，重置当天的统计
    if data.get("date") != today:
        data = default_daily_stats()
        changed = True

    else:
        # 补齐缺失的统计字段
        defaults = default_daily_stats()

        for key, value in defaults.items():
            if key not in data:
                data[key] = value
                changed = True

    # 保存发生变化的每日统计数据
    if changed:

        latest_content, latest_sha = github_get_file(
            DAILY_STATS_PATH
        )

        if latest_sha:

            success = github_save_file(
                DAILY_STATS_PATH,
                data,
                latest_sha,
                "Update daily statistics"
            )

            if success:
                _, sha = github_get_file(
                    DAILY_STATS_PATH
                )

    return data, sha




# ============================================================
# 加载全部数据
# ============================================================

# Keep the loaded data in Streamlit session state. Streamlit reruns the whole
# script after every interaction; re-downloading all four JSON files on every
# answer adds avoidable latency. Reload once per session and again after the
# Malaysia-local date changes (needed for daily stats and new-word migration).
_app_data_date = get_today()
if (
    st.session_state.get("_vocab_app_data_initialized", False)
    and st.session_state.get("_vocab_app_data_date") == _app_data_date
):
    review_settings = st.session_state["_vocab_review_settings"]
    review_settings_sha = st.session_state.get("_vocab_review_settings_sha")
    words = st.session_state["_vocab_words"]
    vocabulary_sha = st.session_state.get("_vocab_vocabulary_sha")
    new_words_data = st.session_state["_vocab_new_words_data"]
    new_words_sha = st.session_state.get("_vocab_new_words_sha")
    daily_stats = st.session_state["_vocab_daily_stats"]
    daily_stats_sha = st.session_state.get("_vocab_daily_stats_sha")
    new_word_migration_blocked = st.session_state.get("_vocab_migration_blocked", False)
else:
    review_settings_sha = None
    review_settings = load_review_settings()
    words, vocabulary_sha = load_words()
    new_word_migration_blocked = False
    new_words_data, new_words_sha = load_new_words()
    daily_stats, daily_stats_sha = load_daily_stats()
    st.session_state["_vocab_app_data_initialized"] = True
    st.session_state["_vocab_app_data_date"] = _app_data_date
    st.session_state["_vocab_review_settings"] = review_settings
    st.session_state["_vocab_review_settings_sha"] = review_settings_sha
    st.session_state["_vocab_words"] = words
    st.session_state["_vocab_vocabulary_sha"] = vocabulary_sha
    st.session_state["_vocab_new_words_data"] = new_words_data
    st.session_state["_vocab_new_words_sha"] = new_words_sha
    st.session_state["_vocab_daily_stats"] = daily_stats
    st.session_state["_vocab_daily_stats_sha"] = daily_stats_sha
    st.session_state["_vocab_migration_blocked"] = new_word_migration_blocked

new_words = new_words_data["words"]


# ============================================================
# 保存正式词库
# ============================================================

def save_words():
    global vocabulary_sha

    current_sha = vocabulary_sha or st.session_state.get(f"_github_sha_{VOCABULARY_PATH}")
    if current_sha is None:
        _, current_sha = github_get_file(VOCABULARY_PATH)
    if current_sha is None:
        return False

    success = github_save_file(
        VOCABULARY_PATH, words, current_sha, "Update vocabulary"
    )
    if success:
        vocabulary_sha = st.session_state.get(f"_github_sha_{VOCABULARY_PATH}", current_sha)
        st.session_state["_vocab_vocabulary_sha"] = vocabulary_sha
        st.session_state["_vocab_words"] = words
    return success


# ============================================================
# 保存新词
# ============================================================


def save_new_words():
    global new_words_sha

    # 如果昨天的新词迁移失败，不要提前更新日期
    if not new_word_migration_blocked:
        new_words_data["date"] = get_today()
    new_words_data["words"] = new_words

    current_sha = new_words_sha or st.session_state.get(f"_github_sha_{NEW_WORDS_PATH}")
    if current_sha is None:
        _, current_sha = github_get_file(NEW_WORDS_PATH)
    if current_sha is None:
        return False

    success = github_save_file(
        NEW_WORDS_PATH, new_words_data, current_sha, "Update daily new words"
    )
    if success:
        new_words_sha = st.session_state.get(f"_github_sha_{NEW_WORDS_PATH}", current_sha)
        st.session_state["_vocab_new_words_sha"] = new_words_sha
        st.session_state["_vocab_new_words_data"] = new_words_data
        st.session_state["_vocab_migration_blocked"] = new_word_migration_blocked
    return success


# ============================================================
# 保存每日统计
# ============================================================

def save_daily_stats():
    global daily_stats_sha

    current_sha = daily_stats_sha or st.session_state.get(f"_github_sha_{DAILY_STATS_PATH}")
    if current_sha is None:
        _, current_sha = github_get_file(DAILY_STATS_PATH)
    if current_sha is None:
        return False

    success = github_save_file(
        DAILY_STATS_PATH, daily_stats, current_sha, "Update daily statistics"
    )
    if success:
        daily_stats_sha = st.session_state.get(f"_github_sha_{DAILY_STATS_PATH}", current_sha)
        st.session_state["_vocab_daily_stats_sha"] = daily_stats_sha
        st.session_state["_vocab_daily_stats"] = daily_stats
    return success


# ============================================================
# 抽题权重计算
# ============================================================

def calculate_sampling_weight(word, q_type="中译英"):

    if q_type == "中译英":

        weight_key = "cn_to_en_weight"
        not_seen_key = "cn_to_en_not_seen"

    else:

        weight_key = "en_to_cn_weight"
        not_seen_key = "en_to_cn_not_seen"

    try:

        base_weight = max(
            1,
            int(word.get(weight_key, 3))
        )

    except (ValueError, TypeError):

        base_weight = 3

    try:

        not_seen = max(
            0,
            int(word.get(not_seen_key, 0))
        )

    except (ValueError, TypeError):

        not_seen = 0

    if not_seen < 3:

        forget_bonus = 0

    elif not_seen < 6:

        forget_bonus = 0.5

    elif not_seen < 11:

        forget_bonus = 1

    elif not_seen < 21:

        forget_bonus = 2

    elif not_seen < 31:

        forget_bonus = 3

    else:

        forget_bonus = 4

    return base_weight + forget_bonus


# ============================================================
# 正式词库概率计算（根据方向判断已掌握状态）
# ============================================================

def calculate_probability(word, q_type="中译英"):

    prof_key = "cn_to_en_proficient" if q_type == "中译英" else "en_to_cn_proficient"
    proficient_words = [item for item in words if item.get(prof_key, False)]
    if not proficient_words:
        return 0

    total_weight = sum(
        calculate_sampling_weight(
            item,
            q_type
        )
        for item in proficient_words
    )

    current_weight = calculate_sampling_weight(
        word,
        q_type
    )

    return (
        current_weight / total_weight * 100
        if total_weight > 0
        else 0
    )


# ============================================================
# 新词概率计算
# ============================================================

def calculate_new_probability(word, q_type="中译英"):

    if not new_words:
        return 0

    total_weight = sum(
        calculate_sampling_weight(
            item,
            q_type
        )
        for item in new_words
    )

    current_weight = calculate_sampling_weight(
        word,
        q_type
    )

    return (
        current_weight / total_weight * 100
        if total_weight > 0
        else 0
    )


# ============================================================
# 新词随机抽题（必须答对一轮才能重复）
# ============================================================

def get_random_new_word(q_type="中译英"):

    if not new_words:
        return None

    done_key = "cn_to_en_round_done" if q_type == "中译英" else "en_to_cn_round_done"

    available_words = [w for w in new_words if not w.get(done_key, False)]

    if not available_words:
        for w in new_words:
            w[done_key] = False
        available_words = new_words
        save_new_words()

    weights = [
        calculate_sampling_weight(
            word,
            q_type
        )
        for word in available_words
    ]

    selected_word = random.choices(
        available_words,
        weights=weights,
        k=1
    )[0]

    return selected_word


# ============================================================
# 练习模式 - 未掌握单词随机抽题（依方向优先级）
# ============================================================

def get_random_normal_word(q_type="中译英"):
    due_words = get_due_normal_words(q_type)
    if not due_words:
        return None
    return random.choice(due_words)


# ============================================================
# 练习模式 - 已掌握单词随机抽题（依方向原概率系统）
# ============================================================

def get_random_proficient_word(q_type="中译英"):

    prof_key = "cn_to_en_proficient" if q_type == "中译英" else "en_to_cn_proficient"
    prof_words = [w for w in words if w.get(prof_key, False)]
    if not prof_words:
        return None

    weights = [
        calculate_sampling_weight(
            word,
            q_type
        )
        for word in prof_words
    ]

    selected_word = random.choices(
        prof_words,
        weights=weights,
        k=1
    )[0]

    return selected_word


# ============================================================
# 发音
# ============================================================

def pronunciation_button(text, key):

    encoded = base64.b64encode(
        str(text).encode("utf-8")
    ).decode("ascii")

    html_code = f"""
    <html>

    <head>

    <meta charset="UTF-8">

    <style>

    body {{
        margin: 0;
        background: transparent;
    }}

    button {{
        border: none;
        background: transparent;
        cursor: pointer;
        font-size: 21px;
        padding: 2px 6px;
    }}

    </style>

    </head>

    <body>

    <button onclick="speak()" title="British English">
        🔊
    </button>

    <script>

    function speak() {{

        const encoded = "{encoded}";

        const text =
            decodeURIComponent(
                escape(
                    atob(encoded)
                )
            );

        window.speechSynthesis.cancel();

        const speech =
            new SpeechSynthesisUtterance(text);

        speech.lang = "en-GB";
        speech.rate = 0.85;

        window.speechSynthesis.speak(speech);
    }}

    </script>

    </body>

    </html>
    """

    st.components.v1.html(
        html_code,
        height=35,
        width=50,
        scrolling=False
    )


# ============================================================
# Session State
# ============================================================

if "current_word_index" not in st.session_state:
    st.session_state.current_word_index = None

if "question_type" not in st.session_state:
    st.session_state.question_type = "中译英"

if "last_word_index" not in st.session_state:
    st.session_state.last_word_index = None

if "last_answer" not in st.session_state:
    st.session_state.last_answer = ""

if "last_correct" not in st.session_state:
    st.session_state.last_correct = None


# ============================================================
# 学习模式 Session State
# ============================================================

if "learning_word_index" not in st.session_state:
    st.session_state.learning_word_index = None

if "learning_question_type" not in st.session_state:
    st.session_state.learning_question_type = "中译英"

if "learning_last_word_index" not in st.session_state:
    st.session_state.learning_last_word_index = None

if "learning_last_answer" not in st.session_state:
    st.session_state.learning_last_answer = ""

if "learning_last_correct" not in st.session_state:
    st.session_state.learning_last_correct = None


# ============================================================
# 查看词库排序状态
# ============================================================

if "vocab_sort_field" not in st.session_state:
    st.session_state.vocab_sort_field = None

if "vocab_sort_reverse" not in st.session_state:
    st.session_state.vocab_sort_reverse = False


def set_sort(field):

    if st.session_state.vocab_sort_field == field:

        st.session_state.vocab_sort_reverse = (
            not st.session_state.vocab_sort_reverse
        )

    else:

        st.session_state.vocab_sort_field = field
        st.session_state.vocab_sort_reverse = False


# ============================================================
# 标题
# ============================================================

st.title("📚 English Vocabulary")


# ============================================================
# Sidebar
# ============================================================

with st.sidebar:

    if review_settings.get("paused", False):
        st.warning("⏸️ 学习计划已暂停")
        if st.button("▶️ 恢复学习计划", use_container_width=True):
            paused_since = review_settings.get("paused_since") or get_today()
            try:
                paused_date = date.fromisoformat(str(paused_since))
            except (TypeError, ValueError):
                paused_date = datetime.now(MALAYSIA_TZ).date()
            today_date = datetime.now(MALAYSIA_TZ).date()
            paused_days = max(0, (today_date - paused_date).days)

            if paused_days:
                for vocabulary_word in words:
                    for direction in ("cn_to_en", "en_to_cn"):
                        key = f"{direction}_next_review"
                        value = vocabulary_word.get(key)
                        if value:
                            try:
                                vocabulary_word[key] = (
                                    date.fromisoformat(str(value))
                                    + timedelta(days=paused_days)
                                ).isoformat()
                            except (TypeError, ValueError):
                                vocabulary_word[key] = get_today()

            # 暂停期间不迁移新词；恢复后从今天继续，不补算暂停天数的新词任务。
            new_words_data["date"] = get_today()
            review_settings["paused"] = False
            review_settings["paused_since"] = None

            results = [save_words(), save_new_words(), save_review_settings()]
            if all(results):
                st.success("学习计划已恢复，复习日期已按暂停天数顺延。")
            else:
                st.error("恢复时有数据保存失败，请检查 GitHub Token 和文件权限。")
            st.session_state.current_word_index = None
            st.session_state.learning_word_index = None
            st.rerun()
    else:
        if st.button("⏸️ 暂停学习计划", use_container_width=True):
            review_settings["paused"] = True
            review_settings["paused_since"] = get_today()
            if save_review_settings():
                st.session_state.current_word_index = None
                st.session_state.learning_word_index = None
                st.rerun()
            else:
                st.error("暂停状态保存失败，请检查 GitHub Token。")

    page = st.radio(
        "功能",
        [
            "🎓 学习模式",
            "🎯 练习模式",
            "📚 词库管理",
            "📖 查看词库"
        ]
    )

    if st.button("🔄 从 GitHub 刷新数据", use_container_width=True):
        # Clear only the app's data cache; the next rerun fetches the latest JSON.
        for cache_key in (
            "_vocab_app_data_initialized",
            "_vocab_app_data_date",
            "_vocab_review_settings",
            "_vocab_review_settings_sha",
            "_vocab_words",
            "_vocab_vocabulary_sha",
            "_vocab_new_words_data",
            "_vocab_new_words_sha",
            "_vocab_daily_stats",
            "_vocab_daily_stats_sha",
            "_vocab_migration_blocked",
        ):
            st.session_state.pop(cache_key, None)
        st.rerun()


# ============================================================
# ============================================================
# 学习模式
# ============================================================
# ============================================================

if page == "🎓 学习模式":

    st.header("🎓 学习模式")

    # ========================================================
    # 添加新词 (表格模式)
    # ========================================================

    st.subheader("➕ 添加新词")

    init_learning_df = pd.DataFrame(
        [{"english": "", "chinese": "", "category": "noun", "cn_note": "", "en_note": ""}]
    )

    edited_learning_df = st.data_editor(
        init_learning_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "english": st.column_config.TextColumn("英文", required=True),
            "chinese": st.column_config.TextColumn("中文", required=True),
            "category": st.column_config.SelectboxColumn("词性", options=CATEGORIES, default="noun", required=True),
            "cn_note": st.column_config.TextColumn("中文备注"),
            "en_note": st.column_config.TextColumn("英文备注"),
        },
        key="learning_batch_editor"
    )

    if st.button("➕ 批量添加新词", use_container_width=True):

        rows_to_add = []
        for idx, row in edited_learning_df.iterrows():
            en = str(row.get("english") or "").strip()
            cn = str(row.get("chinese") or "").strip()
            cat = str(row.get("category") or "noun").strip()
            cn_n = "" if pd.isna(row.get("cn_note")) else str(row.get("cn_note")).strip()
            en_n = "" if pd.isna(row.get("en_note")) else str(row.get("en_note")).strip()

            if cat not in CATEGORIES:
                cat = "noun"

            if en and cn:
                rows_to_add.append({
                    "english": en,
                    "chinese": cn,
                    "category": cat,
                    "cn_note": cn_n,
                    "en_note": en_n
                })

        if not rows_to_add:
            st.warning("表格中没有有效的单词输入，请确保英文和中文非空。")
        else:
            added = 0
            duplicate = 0

            for item in rows_to_add:
                english = item["english"]
                chinese = item["chinese"]
                category = item["category"]
                cn_note = item["cn_note"]
                en_note = item["en_note"]

                exists_new = any(
                    it.get("english", "").strip().lower() == english.lower() and
                    it.get("chinese", "").strip() == chinese and
                    it.get("category", "noun") == category
                    for it in new_words
                )

                if exists_new:
                    duplicate += 1
                    continue

                new_word = {
                    "english": english,
                    "chinese": chinese,
                    "category": category,
                    "cn_note": cn_note,
                    "en_note": en_note,
                    "cn_to_en_proficient": False,
                    "en_to_cn_proficient": False,
                    "cn_to_en_weight": 3,
                    "en_to_cn_weight": 3,
                    "cn_to_en_round_done": False,
                    "en_to_cn_round_done": False
                }
                new_words.append(new_word)
                added += 1

            # Save only after all pasted rows have been processed. Saving and
            # rerunning inside the loop interrupted the loop after row one.
            if added > 0:
                new_success = save_new_words()
                if new_success:
                    st.success(
                        f"成功添加 {added} 个新词。"
                        "今天可以练习，明天自动加入正式词库。"
                    )
                    if duplicate:
                        st.info(f"{duplicate} 个今天已经存在的新词没有重复添加。")
                    st.rerun()
                else:
                    st.error("新词保存失败，请检查 GitHub Token。")

            if duplicate:
                st.info(f"{duplicate} 个今天已经存在的新词没有重复添加。")


    if review_settings.get("paused", False):
        st.info("⏸️ 学习计划已暂停。你仍然可以添加、编辑或删除新词；恢复后才能继续新词练习。")
    else:
        # ========================================================
        # 新词数量
        # ========================================================

        st.divider()

        if not new_words:

            st.info(
                "今天还没有新词，请先添加新词。"
            )

        else:

            st.caption(
                f"今天共有 {len(new_words)} 个新词"
            )

            # ====================================================
            # 题型
            # ====================================================

            learning_question_type = st.radio(
                "题型",
                [
                    "中译英",
                    "英译中"
                ],
                horizontal=True,
                key="learning_question_type_radio"
            )

            if (
                learning_question_type
                != st.session_state.learning_question_type
            ):

                st.session_state.learning_question_type = (
                    learning_question_type
                )

                st.session_state.learning_word_index = None
                st.session_state.learning_last_word_index = None
                st.session_state.learning_last_answer = ""
                st.session_state.learning_last_correct = None


            # ====================================================
            # 随机选择第一题
            # ====================================================

            if (
                st.session_state.learning_word_index is None
                or
                st.session_state.learning_word_index >= len(new_words)
            ):

                selected_new_word = get_random_new_word(learning_question_type)

                if selected_new_word is not None:

                    st.session_state.learning_word_index = (
                        new_words.index(
                            selected_new_word
                        )
                    )


            learning_current_index = (
                st.session_state.learning_word_index
            )

            if learning_current_index is not None:

                learning_word = new_words[
                    learning_current_index
                ]

                learning_category = learning_word.get(
                    "category",
                    "noun"
                )


                # =================================================
                # 左右两栏
                # =================================================

                left, right = st.columns(
                    [1, 1],
                    gap="large"
                )


                # =================================================
                # 上一题
                # =================================================

                with left:

                    st.markdown("### 上一题")

                    last_index = (
                        st.session_state.learning_last_word_index
                    )

                    if last_index is None:

                        st.caption(
                            "开始答题后显示上一题"
                        )

                    elif last_index >= len(new_words):

                        st.caption(
                            "上一题不存在"
                        )

                    else:

                        last_word = new_words[last_index]

                        last_category = last_word.get(
                            "category",
                            "noun"
                        )

                        if learning_question_type == "中译英":

                            note_display = f"<br/><small style='opacity:0.8;'>📝 备注：{html.escape(last_word.get('cn_note', ''))}</small>" if last_word.get('cn_note') else ""

                            st.markdown(
                                f"""
                                <div class="previous-question">
                                    {html.escape(last_word["chinese"])}
                                    {note_display}
                                </div>

                                <div class="previous-category">
                                    {html.escape(last_category)}
                                </div>
                                """,
                                unsafe_allow_html=True
                            )

                            st.markdown(
                                f"""
                                <div class="answer-text">
                                    你的答案：
                                    <b>
                                    {html.escape(
                                        st.session_state.learning_last_answer
                                    )}
                                    </b>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )

                            st.markdown(
                                f"""
                                <div class="answer-text">
                                    正确答案：
                                    <b>
                                    {html.escape(last_word["english"])}
                                    </b>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )

                            pronunciation_button(
                                last_word["english"],
                                "learning_last_cn_en"
                            )

                        else:

                            note_display = f"<br/><small style='opacity:0.8;'>📝 备注：{html.escape(last_word.get('en_note', ''))}</small>" if last_word.get('en_note') else ""

                            st.markdown(
                                f"""
                                <div class="previous-question">
                                    {html.escape(last_word["english"])}
                                    {note_display}
                                </div>

                                <div class="previous-category">
                                    {html.escape(last_category)}
                                </div>
                                """,
                                unsafe_allow_html=True
                            )

                            pronunciation_button(
                                last_word["english"],
                                "learning_last_en_cn"
                            )

                            st.markdown(
                                f"""
                                <div class="answer-text">
                                    你的答案：
                                    <b>
                                    {html.escape(
                                        st.session_state.learning_last_answer
                                    )}
                                    </b>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )

                            st.markdown(
                                f"""
                                <div class="answer-text">
                                    正确答案：
                                    <b>
                                    {html.escape(last_word["chinese"])}
                                    </b>
                                </div>
                                """,
                                unsafe_allow_html=True
                            )


                        if st.session_state.learning_last_correct:

                            st.success(
                                "正确",
                                icon="✅"
                            )

                        else:

                            st.error(
                                "错误",
                                icon="❌"
                            )


                # =================================================
                # 下一题
                # =================================================

                with right:

                    st.markdown("### 下一题")

                    if learning_question_type == "中译英":

                        note_display = f"<br/><small style='opacity:0.8; font-size:16px;'>📝 备注：{html.escape(learning_word.get('cn_note', ''))}</small>" if learning_word.get('cn_note') else ""

                        st.markdown(
                            f"""
                            <div class="question">
                                {html.escape(
                                    learning_word["chinese"]
                                )}
                                {note_display}
                            </div>

                            <div class="question-category">
                                {html.escape(
                                    learning_category
                                )}
                            </div>
                            """,
                            unsafe_allow_html=True
                        )

                    else:

                        note_display = f"<br/><small style='opacity:0.8; font-size:16px;'>📝 备注：{html.escape(learning_word.get('en_note', ''))}</small>" if learning_word.get('en_note') else ""

                        st.markdown(
                            f"""
                            <div class="question">
                                {html.escape(
                                    learning_word["english"]
                                )}
                                {note_display}
                            </div>

                            <div class="question-category">
                                {html.escape(
                                    learning_category
                                )}
                            </div>
                            """,
                            unsafe_allow_html=True
                        )

                        pronunciation_button(
                            learning_word["english"],
                            "learning_current_sound"
                        )


                    with st.form(
                        key="learning_answer_form",
                        clear_on_submit=True
                    ):

                        learning_answer = st.text_input(
                            "答案",
                            label_visibility="collapsed",
                            placeholder="输入答案后按 Enter",
                            autocomplete="off"
                        )

                        learning_submitted = (
                            st.form_submit_button(
                                "提交",
                                use_container_width=True
                            )
                        )


                    if learning_submitted:

                        learning_answer = (
                            learning_answer.strip()
                        )

                        if not learning_answer:

                            st.warning(
                                "请输入答案后再提交。"
                            )

                            st.stop()


                        # =========================================
                        # 判断答案
                        # =========================================

                        if learning_question_type == "中译英":

                            correct_answer = (
                                learning_word["english"]
                                .strip()
                                .lower()
                            )

                            user_answer = (
                                learning_answer
                                .strip()
                                .lower()
                            )

                        else:

                            correct_answer = (
                                learning_word["chinese"]
                                .strip()
                            )

                            user_answer = (
                                learning_answer
                                .strip()
                            )


                        is_correct = (
                            user_answer
                            ==
                            correct_answer
                        )


                        # =========================================
                        # 新词独立概率机制与轮次更新
                        # =========================================

                        weight_key = "cn_to_en_weight" if learning_question_type == "中译英" else "en_to_cn_weight"
                        done_key = "cn_to_en_round_done" if learning_question_type == "中译英" else "en_to_cn_round_done"

                        if is_correct:

                            learning_word[weight_key] = max(
                                1,
                                int(
                                    learning_word.get(
                                        weight_key,
                                        3
                                    )
                                ) - 1
                            )
                            learning_word[done_key] = True

                        else:

                            learning_word[weight_key] = min(
                                20,
                                int(
                                    learning_word.get(
                                        weight_key,
                                        3
                                    )
                                ) + 2
                            )


                        # =========================================
                        # 显示上一题
                        # =========================================

                        st.session_state.learning_last_word_index = (
                            learning_current_index
                        )

                        st.session_state.learning_last_answer = (
                            learning_answer
                        )

                        st.session_state.learning_last_correct = (
                            is_correct
                        )


                        # =========================================
                        # 下一题
                        # =========================================

                        next_new_word = get_random_new_word(learning_question_type)

                        if next_new_word is not None:

                            st.session_state.learning_word_index = (
                                new_words.index(
                                    next_new_word
                                )
                            )
                        save_success = save_new_words()
                        if not save_success:

                            st.error(
                                "⚠️ 新词数据保存失败，请检查 GitHub Token 权限。"
                            )

                        st.rerun()


    # ========================================================
    # 学习模式最底部：编辑列表
    # ========================================================

    st.divider()

    st.subheader("✏️ 编辑列表")

    if not new_words:

        st.caption(
            "今天没有新词可以编辑。"
        )

    else:

        new_word_search = st.text_input(
            "🔍 搜索新词",
            placeholder="输入英文或中文",
            key="new_word_edit_search"
        )

        for index, word in enumerate(new_words):

            if new_word_search:

                if (
                    new_word_search.lower()
                    not in word["english"].lower()

                    and

                    new_word_search
                    not in word["chinese"]
                ):

                    continue

            with st.expander(
                f"{word['english']} → {word['chinese']} （{word.get('category', 'noun')}）"
            ):
                
                pronunciation_button(word["english"], f"new_word_pron_{index}")

                col1, col2 = st.columns(2)

                with col1:

                    edit_new_english = st.text_input(
                        "英文",
                        value=word["english"],
                        key=f"new_edit_en_{index}"
                    )

                with col2:

                    edit_new_chinese = st.text_input(
                        "中文",
                        value=word["chinese"],
                        key=f"new_edit_cn_{index}"
                    )

                col_n1, col_n2 = st.columns(2)

                with col_n1:
                    edit_new_cn_note = st.text_input(
                        "中文备注",
                        value=word.get("cn_note", ""),
                        key=f"new_edit_cn_note_{index}"
                    )

                with col_n2:
                    edit_new_en_note = st.text_input(
                        "英文备注",
                        value=word.get("en_note", ""),
                        key=f"new_edit_en_note_{index}"
                    )

                current_category = word.get(
                    "category",
                    "noun"
                )

                edit_new_category = st.selectbox(
                    "词性",
                    CATEGORIES,
                    index=(
                        CATEGORIES.index(
                            current_category
                        )
                        if current_category in CATEGORIES
                        else 0
                    ),
                    key=f"new_edit_category_{index}"
                )

                col_p1, col_p2 = st.columns(2)
                with col_p1:
                    edit_new_cn_prof = st.checkbox(
                        "中译英已熟练",
                        value=word.get("cn_to_en_proficient", False),
                        key=f"new_edit_cn_prof_{index}"
                    )
                with col_p2:
                    edit_new_en_prof = st.checkbox(
                        "英译中已熟练",
                        value=word.get("en_to_cn_proficient", False),
                        key=f"new_edit_en_prof_{index}"
                    )

                st.caption(
                    f"中译英权重：{word.get('cn_to_en_weight', 3)} | 概率：{calculate_new_probability(word, '中译英'):.2f}%"
                )
                st.caption(
                    f"英译中权重：{word.get('en_to_cn_weight', 3)} | 概率：{calculate_new_probability(word, '英译中'):.2f}%"
                )

                col1, col2 = st.columns(2)

                with col1:

                    if st.button(
                        "💾 保存",
                        key=f"new_save_{index}",
                        use_container_width=True
                    ):

                        edit_new_english = (
                            edit_new_english.strip()
                        )

                        edit_new_chinese = (
                            edit_new_chinese.strip()
                        )

                        if not edit_new_english:

                            st.warning(
                                "英文不能为空。"
                            )

                        elif not edit_new_chinese:

                            st.warning(
                                "中文不能为空。"
                            )

                        else:

                            old_english = word["english"]
                            old_chinese = word["chinese"]
                            old_category = word.get("category", "noun")

                            word["english"] = edit_new_english
                            word["chinese"] = edit_new_chinese
                            word["category"] = edit_new_category
                            word["cn_note"] = edit_new_cn_note.strip()
                            word["en_note"] = edit_new_en_note.strip()
                            word["cn_to_en_proficient"] = edit_new_cn_prof
                            word["en_to_cn_proficient"] = edit_new_en_prof

                            for vocabulary_word in words:

                                if (
                                    vocabulary_word.get("english", "").strip().lower() == old_english.strip().lower() and
                                    vocabulary_word.get("chinese", "").strip() == old_chinese.strip() and
                                    vocabulary_word.get("category", "noun") == old_category
                                ):

                                    vocabulary_word["english"] = edit_new_english
                                    vocabulary_word["chinese"] = edit_new_chinese
                                    vocabulary_word["category"] = edit_new_category
                                    vocabulary_word["cn_note"] = edit_new_cn_note.strip()
                                    vocabulary_word["en_note"] = edit_new_en_note.strip()
                                    vocabulary_word["cn_to_en_proficient"] = edit_new_cn_prof
                                    vocabulary_word["en_to_cn_proficient"] = edit_new_en_prof
                                    break

                            new_success = save_new_words()
                            vocab_success = save_words()

                            if new_success and vocab_success:

                                st.success(
                                    "修改成功，并已同步到正式词库。"
                                )

                                st.rerun()

                with col2:

                    if st.button(
                        "🗑️ 删除",
                        key=f"new_delete_{index}",
                        use_container_width=True
                    ):

                        new_words.pop(index)

                        if save_new_words():

                            st.success(
                                "已从今天的新词列表删除。"
                            )

                            st.rerun()


# ============================================================
# ============================================================
# 练习模式
# ============================================================
# ============================================================

elif page == "🎯 练习模式":

    st.header("🎯 练习模式")

    if review_settings.get("paused", False):
        st.info("⏸️ 学习计划已暂停。恢复后才能继续间隔复习或已熟练单词复习。")
        st.stop()

    if not words:

        st.warning(
            "词库为空，请先到「词库管理」添加单词。"
        )

    else:

        practice_sub_mode = st.radio(
            "复习分类",
            ["未熟练", "已熟练"],
            horizontal=True,
            key="practice_sub_mode_radio"
        )

        question_type = st.radio(
            "题型",
            [
                "中译英",
                "英译中"
            ],
            horizontal=True
        )

        if (
            question_type
            != st.session_state.get("practice_question_type", "")
        ):
            st.session_state.practice_question_type = question_type
            st.session_state.current_word_index = None
            st.session_state.last_word_index = None
            st.session_state.last_answer = ""
            st.session_state.last_correct = None

        if (
            st.session_state.get("current_practice_sub_mode", "")
            != practice_sub_mode
        ):
            st.session_state.current_practice_sub_mode = practice_sub_mode
            st.session_state.current_word_index = None
            st.session_state.last_word_index = None
            st.session_state.last_answer = ""
            st.session_state.last_correct = None

        prof_key = "cn_to_en_proficient" if question_type == "中译英" else "en_to_cn_proficient"

        if practice_sub_mode == "未熟练":
            if not any(not w.get(prof_key, False) for w in words):
                st.info(f"🎉 太棒了！当前【{question_type}】方向所有单词都已进入已熟练状态！您可以切换到「已熟练」子页面进行复习。")
                st.stop()
        else:
            if not any(w.get(prof_key, False) for w in words):
                st.info(f"💡 当前【{question_type}】方向还没有已熟练的单词，请先在「未熟练」模式中完成间隔复习，或手动勾选已熟练。")
                st.stop()


        if practice_sub_mode == "未熟练" and not get_due_normal_words(question_type):
            st.success(f"🎉【{question_type}】今天到期的未熟练复习任务已全部完成。")
            st.caption("未来到期的单词不会提前出现；逾期单词会一直保留到完成复习。")
            st.stop()

        if (
            st.session_state.current_word_index is None
            or
            st.session_state.current_word_index >= len(words)
        ):

            if practice_sub_mode == "未熟练":
                selected_word = get_random_normal_word(question_type)
            else:
                selected_word = get_random_proficient_word(question_type)

            if selected_word is not None:

                st.session_state.current_word_index = (
                    words.index(selected_word)
                )


        current_index = (
            st.session_state.current_word_index
        )

        if current_index is not None and current_index < len(words):
            word = words[current_index]
        else:
            if practice_sub_mode == "未熟练":
                selected_word = get_random_normal_word(question_type)
            else:
                selected_word = get_random_proficient_word(question_type)
            if selected_word:
                current_index = words.index(selected_word)
                st.session_state.current_word_index = current_index
                word = words[current_index]
            else:
                st.stop()

        current_category = word.get(
            "category",
            "noun"
        )


        left, right = st.columns(
            [1, 1],
            gap="large"
        )


        # ====================================================
        # 上一题
        # ====================================================

        with left:

            st.markdown("### 上一题")

            last_index = (
                st.session_state.last_word_index
            )

            if last_index is None:

                st.caption(
                    "开始答题后显示上一题"
                )

            elif last_index >= len(words):

                st.caption(
                    "上一题不存在"
                )

            else:

                last_word = words[last_index]

                last_category = last_word.get(
                    "category",
                    "noun"
                )


                if question_type == "中译英":

                    note_display = f"<br/><small style='opacity:0.8;'>📝 备注：{html.escape(last_word.get('cn_note', ''))}</small>" if last_word.get('cn_note') else ""

                    st.markdown(
                        f"""
                        <div class="previous-question">
                            {html.escape(last_word["chinese"])}
                            {note_display}
                        </div>

                        <div class="previous-category">
                            {html.escape(last_category)}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                    st.markdown(
                        f"""
                        <div class="answer-text">
                            你的答案：
                            <b>
                            {html.escape(
                                st.session_state.last_answer
                            )}
                            </b>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                    st.markdown(
                        f"""
                        <div class="answer-text">
                            正确答案：
                            <b>
                            {html.escape(last_word["english"])}
                            </b>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                    pronunciation_button(
                        last_word["english"],
                        "last_cn_en"
                    )

                else:

                    note_display = f"<br/><small style='opacity:0.8;'>📝 备注：{html.escape(last_word.get('en_note', ''))}</small>" if last_word.get('en_note') else ""

                    st.markdown(
                        f"""
                        <div class="previous-question">
                            {html.escape(last_word["english"])}
                            {note_display}
                        </div>

                        <div class="previous-category">
                            {html.escape(last_category)}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                    pronunciation_button(
                        last_word["english"],
                        "last_en_cn"
                    )

                    st.markdown(
                        f"""
                        <div class="answer-text">
                            你的答案：
                            <b>
                            {html.escape(
                                st.session_state.last_answer
                            )}
                            </b>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                    st.markdown(
                        f"""
                        <div class="answer-text">
                            正确答案：
                            <b>
                            {html.escape(last_word["chinese"])}
                            </b>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )


                if st.session_state.last_correct:

                    st.success(
                        "正确",
                        icon="✅"
                    )

                else:

                    st.error(
                        "错误",
                        icon="❌"
                    )

                    if st.button(
                        "我的答案也是近义词 ✓",
                        key="similar_answer",
                        use_container_width=True
                    ):

                        if question_type == "中译英":

                            last_word["cn_to_en_wrong"] = max(
                                0,
                                int(
                                    last_word.get(
                                        "cn_to_en_wrong",
                                        0
                                    )
                                ) - 1
                            )

                            last_word["cn_to_en_correct"] = (
                                int(
                                    last_word.get(
                                        "cn_to_en_correct",
                                        0
                                    )
                                ) + 1
                            )

                            last_word["cn_to_en_weight"] = max(
                                1,
                                int(last_word.get("cn_to_en_weight", 3)) - 2
                            )

                        else:

                            last_word["en_to_cn_wrong"] = max(
                                0,
                                int(
                                    last_word.get(
                                        "en_to_cn_wrong",
                                        0
                                    )
                                ) - 1
                            )

                            last_word["en_to_cn_correct"] = (
                                int(
                                    last_word.get(
                                        "en_to_cn_correct",
                                        0
                                    )
                                ) + 1
                            )

                            last_word["en_to_cn_weight"] = max(
                                1,
                                int(last_word.get("en_to_cn_weight", 3)) - 2
                            )


                        last_word["correct"] = (
                            int(
                                last_word.get(
                                    "correct",
                                    0
                                )
                            ) + 1
                        )

                        last_word["wrong"] = max(
                            0,
                            int(
                                last_word.get(
                                    "wrong",
                                    0
                                )
                            ) - 1
                        )


                        save_words()


                        if practice_sub_mode == "已熟悉":
                            if question_type == "中译英":
                                daily_stats["cn_to_en_correct"] = int(daily_stats.get("cn_to_en_correct", 0)) + 1
                            else:
                                daily_stats["en_to_cn_correct"] = int(daily_stats.get("en_to_cn_correct", 0)) + 1
                            st.session_state["_vocab_daily_stats"] = daily_stats
                            save_daily_stats()

                        st.session_state.last_correct = True

                        st.rerun()


        # ====================================================
        # 下一题
        # ====================================================

        with right:

            st.markdown("### 下一题")

            if question_type == "中译英":

                note_display = f"<br/><small style='opacity:0.8; font-size:16px;'>📝 备注：{html.escape(word.get('cn_note', ''))}</small>" if word.get('cn_note') else ""

                st.markdown(
                    f"""
                    <div class="question">
                        {html.escape(word["chinese"])}
                        {note_display}
                    </div>

                    <div class="question-category">
                        {html.escape(current_category)}
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            else:

                note_display = f"<br/><small style='opacity:0.8; font-size:16px;'>📝 备注：{html.escape(word.get('en_note', ''))}</small>" if word.get('en_note') else ""

                st.markdown(
                    f"""
                    <div class="question">
                        {html.escape(word["english"])}
                        {note_display}
                    </div>

                    <div class="question-category">
                        {html.escape(current_category)}
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                pronunciation_button(
                    word["english"],
                    "current_sound"
                )


            with st.form(
                key="answer_form",
                clear_on_submit=True
            ):

                answer = st.text_input(
                    "答案",
                    label_visibility="collapsed",
                    placeholder="输入答案后按 Enter",
                    autocomplete="off"
                )

                submitted = st.form_submit_button(
                    "提交",
                    use_container_width=True
                )


            if submitted:

                answer = answer.strip()

                if not answer:

                    st.warning(
                        "请输入答案后再提交。"
                    )

                    st.stop()


                if question_type == "中译英":

                    correct_answer = (
                        word["english"]
                        .strip()
                        .lower()
                    )

                    user_answer = (
                        answer
                        .strip()
                        .lower()
                    )

                else:

                    correct_answer = (
                        word["chinese"]
                        .strip()
                    )

                    user_answer = (
                        answer
                        .strip()
                    )


                if user_answer == correct_answer:

                    is_correct = True

                    if practice_sub_mode == "未熟练":
                        update_unmastered_review(word, question_type, True)
                        if question_type == "中译英":
                            word["cn_to_en_correct"] = int(word.get("cn_to_en_correct", 0)) + 1
                        else:
                            word["en_to_cn_correct"] = int(word.get("en_to_cn_correct", 0)) + 1

                    else:
                        if question_type == "中译英":
                            word["cn_to_en_correct"] += 1
                            word["cn_to_en_weight"] = max(
                                1,
                                int(word.get("cn_to_en_weight", 3)) - 1
                            )
                        else:
                            word["en_to_cn_correct"] += 1
                            word["en_to_cn_weight"] = max(
                                1,
                                int(word.get("en_to_cn_weight", 3)) - 1
                            )

                    word["correct"] = (
                        int(
                            word.get(
                                "correct",
                                0
                            )
                        ) + 1
                    )

                else:

                    is_correct = False

                    if practice_sub_mode == "未熟练":
                        update_unmastered_review(word, question_type, False)
                        if question_type == "中译英":
                            word["cn_to_en_wrong"] = int(word.get("cn_to_en_wrong", 0)) + 1
                        else:
                            word["en_to_cn_wrong"] = int(word.get("en_to_cn_wrong", 0)) + 1
                    else:
                        if question_type == "中译英":
                            word["cn_to_en_wrong"] += 1
                            word["cn_to_en_weight"] = min(
                                20,
                                int(word.get("cn_to_en_weight", 3)) + 2
                            )
                        else:
                            word["en_to_cn_wrong"] += 1
                            word["en_to_cn_weight"] = min(
                                20,
                                int(word.get("en_to_cn_weight", 3)) + 2
                            )

                    word["wrong"] = (
                        int(
                            word.get(
                                "wrong",
                                0
                            )
                        ) + 1
                    )



                today = get_today()

                if daily_stats.get("date") != today:
                    daily_stats = default_daily_stats()
                    st.session_state["_vocab_daily_stats"] = daily_stats

                # 仅记录「未熟练」模式的今日答题次数
                if practice_sub_mode == "未熟练":
                    if question_type == "中译英":
                        daily_stats["normal_cn_to_en_answered"] = (
                            int(daily_stats.get("normal_cn_to_en_answered", 0)) + 1
                        )
                    else:
                        daily_stats["normal_en_to_cn_answered"] = (
                            int(daily_stats.get("normal_en_to_cn_answered", 0)) + 1
                        )

                # These four counters belong exclusively to 已熟悉 mode.
                # 未熟悉 mode has its own normal_*_answered counters above.
                if practice_sub_mode == "已熟悉":
                    if question_type == "中译英":
                        daily_stats["cn_to_en_answered"] = int(daily_stats.get("cn_to_en_answered", 0)) + 1
                        if is_correct:
                            daily_stats["cn_to_en_correct"] = int(daily_stats.get("cn_to_en_correct", 0)) + 1
                    else:
                        daily_stats["en_to_cn_answered"] = int(daily_stats.get("en_to_cn_answered", 0)) + 1
                        if is_correct:
                            daily_stats["en_to_cn_correct"] = int(daily_stats.get("en_to_cn_correct", 0)) + 1

                st.session_state["_vocab_daily_stats"] = daily_stats
                save_daily_stats()



                st.session_state.last_word_index = (
                    current_index
                )

                st.session_state.last_answer = answer

                st.session_state.last_correct = is_correct


                if practice_sub_mode == "未熟练":
                    next_word = get_random_normal_word(question_type)
                else:
                    next_word = get_random_proficient_word(question_type)

                if next_word is not None:
                    st.session_state.current_word_index = words.index(next_word)
                else:
                    st.session_state.current_word_index = None

                save_success = save_words()


                if not save_success:

                    st.error(
                        "⚠️ 数据保存失败，请检查 GitHub Token 权限。"
                    )

                st.rerun()



        # ====================================================
        # 今日统计
        # ====================================================

        st.divider()
        st.subheader("📊 今日统计")

        if practice_sub_mode == "未熟练":
            # 当前题型今天已经回答的未熟练题数
            if question_type == "中译英":
                answered_today = int(
                    daily_stats.get("normal_cn_to_en_answered", 0)
                )
            else:
                answered_today = int(
                    daily_stats.get("normal_en_to_cn_answered", 0)
                )

            # 当前题型仍然到期、尚未完成的任务数
            remaining_due = len(get_due_normal_words(question_type))

            # 今日所需总答题数 = 已回答 + 尚未完成
            required_today = answered_today + remaining_due

            col1, col2 = st.columns(2)

            col1.metric(
                "今日所需答题数",
                required_today
            )

            col2.metric(
                "今日已回答",
                answered_today
            )

            st.progress(
                min(1.0, answered_today / required_today)
                if required_today > 0 else 1.0
            )

            if required_today > 0:
                st.caption(
                    f"完成进度：{answered_today} / {required_today}"
                )
            else:
                st.caption("当前没有需要完成的未熟练复习任务。")

        else:
            # 已掌握模式：保留原本统计方式
            cn_answered = int(
                daily_stats.get("cn_to_en_answered", 0)
            )
            cn_correct = int(
                daily_stats.get("cn_to_en_correct", 0)
            )
            en_answered = int(
                daily_stats.get("en_to_cn_answered", 0)
            )
            en_correct = int(
                daily_stats.get("en_to_cn_correct", 0)
            )

            total_answered = cn_answered + en_answered
            total_correct = cn_correct + en_correct

            col1, col2, col3 = st.columns(3)

            col1.metric(
                "今日总答数",
                total_answered
            )

            col2.metric(
                "中译英",
                f"{cn_correct} / {cn_answered}"
            )

            col3.metric(
                "英译中",
                f"{en_correct} / {en_answered}"
            )

            if total_answered > 0:
                accuracy = total_correct / total_answered * 100
                st.caption(f"今日总正确率：{accuracy:.1f}%")

# ============================================================
# ============================================================
# 词库管理
# ============================================================
# ============================================================

elif page == "📚 词库管理":

    st.header("📚 词库管理")

    st.subheader("➕ 添加单词")

    init_df = pd.DataFrame(
        [{"english": "", "chinese": "", "category": "noun", "cn_note": "", "en_note": ""}]
    )

    edited_df = st.data_editor(
        init_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "english": st.column_config.TextColumn("英文", required=True),
            "chinese": st.column_config.TextColumn("中文", required=True),
            "category": st.column_config.SelectboxColumn("词性", options=CATEGORIES, default="noun", required=True),
            "cn_note": st.column_config.TextColumn("中文备注"),
            "en_note": st.column_config.TextColumn("英文备注"),
        },
        key="vocab_batch_editor"
    )

    if st.button("➕ 批量添加单词", use_container_width=True):

        rows_to_add = []
        for idx, row in edited_df.iterrows():
            en = str(row.get("english") or "").strip()
            cn = str(row.get("chinese") or "").strip()
            cat = str(row.get("category") or "noun").strip()
            cn_n = "" if pd.isna(row.get("cn_note")) else str(row.get("cn_note")).strip()
            en_n = "" if pd.isna(row.get("en_note")) else str(row.get("en_note")).strip()

            if cat not in CATEGORIES:
                cat = "noun"

            if en and cn:
                rows_to_add.append({
                    "english": en,
                    "chinese": cn,
                    "category": cat,
                    "cn_note": cn_n,
                    "en_note": en_n
                })

        if not rows_to_add:
            st.warning("表格中没有有效的单词输入，请确保英文和中文非空。")
        else:
            added = 0
            duplicate = 0

            for item in rows_to_add:
                english = item["english"]
                chinese = item["chinese"]
                category = item["category"]
                cn_note = item["cn_note"]
                en_note = item["en_note"]

                exists = any(
                    it.get("english", "").strip().lower() == english.lower() and
                    it.get("chinese", "").strip() == chinese and
                    it.get("category", "noun") == category
                    for it in words
                )

                if exists:
                    duplicate += 1
                else:
                    words.append({
                        "english": english,
                        "chinese": chinese,
                        "category": category,
                        "cn_note": cn_note,
                        "en_note": en_note,
                        "cn_to_en_proficient": False,
                        "en_to_cn_proficient": False,
                        "cn_to_en_priority": 12,
                        "en_to_cn_priority": 12,
                        "cn_to_en_streak": 0,
                        "en_to_cn_streak": 0,
                        "cn_to_en_weight": 3,
                        "en_to_cn_weight": 3,
                        "cn_to_en_correct": 0,
                        "cn_to_en_wrong": 0,
                        "en_to_cn_correct": 0,
                        "en_to_cn_wrong": 0,
                        "correct": 0,
                        "wrong": 0
                    })
                    added += 1

            if added > 0:
                if save_words():
                    st.success(f"成功添加 {added} 个单词，并已同步到 GitHub。")
                    st.rerun()

            if duplicate:
                st.info(f"{duplicate} 个完全相同的单词没有重复添加。")

    st.divider()

    st.subheader("✏️ 编辑词库")

    # 编辑页面增加分类与熟练状态筛选功能
    f_col1, f_col2 = st.columns(2)
    with f_col1:
        edit_cat_filter = st.selectbox(
            "词性分类筛选",
            ["全部"] + CATEGORIES,
            key="edit_category_filter_box"
        )
    with f_col2:
        edit_stat_filter = st.selectbox(
            "熟练状态筛选",
            ["全部", "中译英未熟练", "中译英已熟练", "英译中未熟练", "英译中已熟练"],
            key="edit_status_filter_box"
        )

    search = st.text_input(
        "🔍 搜索",
        placeholder="输入英文或中文",
        key="vocabulary_edit_search"
    )

    for index, word in enumerate(words):

        if search:

            if (
                search.lower()
                not in word["english"].lower()

                and

                search
                not in word["chinese"]
            ):

                continue

        if edit_cat_filter != "全部" and word.get("category", "noun") != edit_cat_filter:
            continue

        if edit_stat_filter == "中译英未熟练" and word.get("cn_to_en_proficient", False):
            continue
        if edit_stat_filter == "中译英已熟练" and not word.get("cn_to_en_proficient", False):
            continue
        if edit_stat_filter == "英译中未熟练" and word.get("en_to_cn_proficient", False):
            continue
        if edit_stat_filter == "英译中已熟练" and not word.get("en_to_cn_proficient", False):
            continue

        with st.expander(
            f"{word['english']} → {word['chinese']} （{word.get('category', 'noun')}）"
        ):

            top_col1, top_col2, top_col3 = st.columns([1, 2, 2])
            with top_col1:
                pronunciation_button(word["english"], f"vocab_pron_{index}")
            with top_col2:
                new_cn_prof = st.checkbox(
                    "中译英已熟练",
                    value=word.get("cn_to_en_proficient", False),
                    key=f"edit_cn_prof_{index}"
                )
            with top_col3:
                new_en_prof = st.checkbox(
                    "英译中已熟练",
                    value=word.get("en_to_cn_proficient", False),
                    key=f"edit_en_prof_{index}"
                )

            col1, col2 = st.columns(2)

            with col1:

                new_english = st.text_input(
                    "英文",
                    value=word["english"],
                    key=f"edit_en_{index}"
                )

            with col2:

                new_chinese = st.text_input(
                    "中文",
                    value=word["chinese"],
                    key=f"edit_cn_{index}"
                )

            col_n1, col_n2 = st.columns(2)

            with col_n1:
                new_cn_note = st.text_input(
                    "中文备注",
                    value=word.get("cn_note", ""),
                    key=f"edit_cn_note_{index}"
                )

            with col_n2:
                new_en_note = st.text_input(
                    "英文备注",
                    value=word.get("en_note", ""),
                    key=f"edit_en_note_{index}"
                )

            current_category = word.get(
                "category",
                "noun"
            )

            new_category = st.selectbox(
                "词性",
                CATEGORIES,
                index=(
                    CATEGORIES.index(current_category)
                    if current_category in CATEGORIES
                    else 0
                ),
                key=f"edit_category_{index}"
            )

            st.caption(
                f"中译英：优先级 {word.get('cn_to_en_priority', 12)} | 权重 {calculate_sampling_weight(word, '中译英')} | "
                f"✓ {word.get('cn_to_en_correct', 0)} / ✗ {word.get('cn_to_en_wrong', 0)}"
            )

            st.caption(
                f"英译中：优先级 {word.get('en_to_cn_priority', 12)} | 权重 {calculate_sampling_weight(word, '英译中')} | "
                f"✓ {word.get('en_to_cn_correct', 0)} / ✗ {word.get('en_to_cn_wrong', 0)}"
            )

            col1, col2 = st.columns(2)

            with col1:

                if st.button(
                    "💾 保存",
                    key=f"save_{index}",
                    use_container_width=True
                ):

                    new_english = new_english.strip()
                    new_chinese = new_chinese.strip()

                    if not new_english:

                        st.warning("英文不能为空。")

                    elif not new_chinese:

                        st.warning("中文不能为空。")

                    else:

                        word["english"] = new_english
                        word["chinese"] = new_chinese
                        word["category"] = new_category
                        word["cn_note"] = new_cn_note.strip()
                        word["en_note"] = new_en_note.strip()

                        # 读取两个熟练复选框的当前状态
                        word["cn_to_en_proficient"] = st.session_state[
                            f"edit_cn_prof_{index}"
                        ]

                        word["en_to_cn_proficient"] = st.session_state[
                            f"edit_en_prof_{index}"
                        ]

                        # 保存到 GitHub
                        if save_words():
                            st.success(
                                f"修改成功！中译英已熟练："
                                f"{word['cn_to_en_proficient']}；"
                                f"英译中已熟练："
                                f"{word['en_to_cn_proficient']}。"
                                "已同步到 GitHub。"
                            )
                            st.rerun()

                        else:
                            st.error(
                                "保存失败！请检查 GitHub Token、"
                                "仓库设置及保存错误信息。"
                            )


            with col2:

                if st.button(
                    "🗑️ 删除",
                    key=f"delete_{index}",
                    use_container_width=True
                ):

                    words.pop(index)

                    if save_words():

                        st.success(
                            "删除成功，并已同步到 GitHub。"
                        )

                        st.rerun()


# ============================================================
# ============================================================
# 查看词库
# ============================================================
# ============================================================

elif page == "📖 查看词库":
    st.header("📖 我的词库")

    if not words:
        st.info("目前没有单词。")
    else:
        filter_col1, filter_col2 = st.columns([2, 1])
        with filter_col1:
            search = st.text_input(
                "🔍 搜索词库", placeholder="输入英文或中文", key="view_vocab_search"
            )
        with filter_col2:
            category_filter = st.selectbox(
                "词性筛选", ["全部"] + CATEGORIES, key="view_category_filter"
            )

        status_filter = st.selectbox(
            "熟悉状态筛选",
            ["全部", "中译英未熟练", "中译英已熟练", "英译中未熟练", "英译中已熟练"],
            key="view_status_filter",
        )

        filtered_words = []
        search_text = search.strip().casefold()
        for word in words:
            english = str(word.get("english", ""))
            chinese = str(word.get("chinese", ""))
            if search_text and search_text not in english.casefold() and search_text not in chinese:
                continue
            if category_filter != "全部" and word.get("category", "noun") != category_filter:
                continue
            cn_prof = bool(word.get("cn_to_en_proficient", False))
            en_prof = bool(word.get("en_to_cn_proficient", False))
            if status_filter == "中译英未熟练" and cn_prof:
                continue
            if status_filter == "中译英已熟练" and not cn_prof:
                continue
            if status_filter == "英译中未熟练" and en_prof:
                continue
            if status_filter == "英译中已熟练" and not en_prof:
                continue
            filtered_words.append(word)

        st.caption(f"找到 {len(filtered_words)} 个单词")

        def familiarity_level(word, direction):
            # Stage is stored as 0–4 internally; present the requested 1–5 level.
            proficient_key = f"{direction}_proficient"
            stage_key = f"{direction}_stage"
            if word.get(proficient_key, False):
                return 5
            try:
                stage = int(word.get(stage_key, 0))
            except (TypeError, ValueError):
                stage = 0
            return max(1, min(5, stage + 1))

        table_rows = []
        for word in filtered_words:
            cn_prof = bool(word.get("cn_to_en_proficient", False))
            en_prof = bool(word.get("en_to_cn_proficient", False))
            table_rows.append({
                "中文": str(word.get("chinese", "")),
                "English": str(word.get("english", "")),
                "词性": str(word.get("category", "noun")),
                "中译英熟悉状态": familiarity_level(word, "cn_to_en"),
                "英译中熟悉状态": familiarity_level(word, "en_to_cn"),
                "中译英概率": f"{calculate_probability(word, '中译英'):.2f}%" if cn_prof else "—",
                "英译中概率": f"{calculate_probability(word, '英译中'):.2f}%" if en_prof else "—",
            })

        table_df = pd.DataFrame(table_rows, columns=[
            "中文", "English", "词性", "中译英熟悉状态", "英译中熟悉状态", "中译英概率", "英译中概率"
        ])
        st.dataframe(
            table_df,
            use_container_width=True,
            hide_index=True,
            height=min(680, max(180, 38 * (len(table_df) + 1))),
            column_config={
                "中文": st.column_config.TextColumn("中文", width="medium"),
                "English": st.column_config.TextColumn("English", width="medium"),
                "词性": st.column_config.TextColumn("词性", width="small"),
                "中译英熟悉状态": st.column_config.NumberColumn("中译英熟悉状态", format="%d", width="medium"),
                "英译中熟悉状态": st.column_config.NumberColumn("英译中熟悉状态", format="%d", width="medium"),
                "中译英概率": st.column_config.TextColumn("中译英概率", width="small"),
                "英译中概率": st.column_config.TextColumn("英译中概率", width="small"),
            },
        )
        st.caption("熟悉状态为 1–5；概率只对该方向已熟练的单词计算，未熟练单词显示 —。点击表头可排序。")
