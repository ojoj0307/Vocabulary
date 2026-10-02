import streamlit as st
import json
import random
import base64
import html
import requests

from datetime import datetime
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
GITHUB_REPO = "english-vocabulary"

VOCABULARY_PATH = "vocabulary.json"
NEW_WORDS_PATH = "new_words.json"
DAILY_STATS_PATH = "daily_stats.json"

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
    font-size: 15px;
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
# 默认每日统计
# ============================================================

def default_daily_stats():

    return {
        "date": get_today(),

        "cn_to_en_answered": 0,
        "cn_to_en_correct": 0,

        "en_to_cn_answered": 0,
        "en_to_cn_correct": 0
    }


# ============================================================
# 默认新词数据
#
# new_words.json 使用：
#
# {
#     "date": "2026-09-12",
#     "words": [...]
# }
#
# 这样可以判断是不是新的一天。
# ============================================================

def default_new_words():

    return {
        "date": get_today(),
        "words": []
    }


# ============================================================
# 标准化正式词库
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

        if "weight" not in word:
            word["weight"] = 3
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

        if "correct" not in word:
            word["correct"] = (
                int(
                    word.get(
                        "cn_to_en_correct",
                        0
                    )
                )
                +
                int(
                    word.get(
                        "en_to_cn_correct",
                        0
                    )
                )
            )
            changed = True

        if "wrong" not in word:
            word["wrong"] = (
                int(
                    word.get(
                        "cn_to_en_wrong",
                        0
                    )
                )
                +
                int(
                    word.get(
                        "en_to_cn_wrong",
                        0
                    )
                )
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

    # 新词拥有完全独立的权重
    if "weight" not in word:
        word["weight"] = 3
        changed = True

    return changed


# ============================================================
# 加载新词
# ============================================================

def load_new_words():

    content, sha = github_get_file(
        NEW_WORDS_PATH
    )

    # 如果 GitHub 没有 new_words.json
    # 自动创建
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

    # ========================================================
    # 兼容你如果之前创建的是 []
    # ========================================================

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

    # ========================================================
    # 确保结构正确
    # ========================================================

    if "date" not in data:

        data["date"] = get_today()
        changed = True

    if "words" not in data:

        data["words"] = []
        changed = True

    if not isinstance(data["words"], list):

        data["words"] = []
        changed = True

    # ========================================================
    # ★ 每天第一次访问时清空新词
    #
    # 不是退出 App 就清空
    #
    # 只比较 GitHub 保存的日期
    # ========================================================

    today = get_today()

    if data["date"] != today:

        data["date"] = today
        data["words"] = []

        changed = True

    # ========================================================
    # 标准化新词
    # ========================================================

    for word in data["words"]:

        if normalize_new_word(word):

            changed = True

    # ========================================================
    # 保存变化
    # ========================================================

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

        if github_save_file(
            DAILY_STATS_PATH,
            data,
            None,
            "Create daily statistics"
        ):

            _, sha = github_get_file(
                DAILY_STATS_PATH
            )

        return data, sha

    try:

        data = json.loads(content)

    except Exception:

        data = default_daily_stats()

    changed = False

    today = get_today()

    if data.get("date") != today:

        data = default_daily_stats()
        changed = True

    required_fields = [
        "cn_to_en_answered",
        "cn_to_en_correct",
        "en_to_cn_answered",
        "en_to_cn_correct"
    ]

    for field in required_fields:

        if field not in data:

            data[field] = 0
            changed = True

    if changed:

        _, new_sha = github_get_file(
            DAILY_STATS_PATH
        )

        if new_sha:

            if github_save_file(
                DAILY_STATS_PATH,
                data,
                new_sha,
                "Update daily statistics"
            ):

                _, sha = github_get_file(
                    DAILY_STATS_PATH
                )

    return data, sha


# ============================================================
# 加载全部数据
# ============================================================

words, vocabulary_sha = load_words()

new_words_data, new_words_sha = load_new_words()

daily_stats, daily_stats_sha = load_daily_stats()


# ============================================================
# 新词列表
# ============================================================

new_words = new_words_data["words"]


# ============================================================
# 保存正式词库
# ============================================================

def save_words():

    global vocabulary_sha

    latest_content, latest_sha = github_get_file(
        VOCABULARY_PATH
    )

    if latest_sha is None:
        return False

    success = github_save_file(
        VOCABULARY_PATH,
        words,
        latest_sha,
        "Update vocabulary"
    )

    if success:

        _, vocabulary_sha = github_get_file(
            VOCABULARY_PATH
        )

    return success


# ============================================================
# 保存新词
# ============================================================

def save_new_words():

    global new_words_sha

    new_words_data["date"] = get_today()
    new_words_data["words"] = new_words

    latest_content, latest_sha = github_get_file(
        NEW_WORDS_PATH
    )

    if latest_sha is None:
        return False

    success = github_save_file(
        NEW_WORDS_PATH,
        new_words_data,
        latest_sha,
        "Update daily new words"
    )

    if success:

        _, new_words_sha = github_get_file(
            NEW_WORDS_PATH
        )

    return success


# ============================================================
# 保存每日统计
# ============================================================

def save_daily_stats():

    global daily_stats_sha

    latest_content, latest_sha = github_get_file(
        DAILY_STATS_PATH
    )

    if latest_sha is None:
        return False

    success = github_save_file(
        DAILY_STATS_PATH,
        daily_stats,
        latest_sha,
        "Update daily statistics"
    )

    if success:

        _, daily_stats_sha = github_get_file(
            DAILY_STATS_PATH
        )

    return success


# ============================================================
# 正式词库概率
# ============================================================

def calculate_probability(word):

    if not words:
        return 0

    total_weight = sum(
        max(
            1,
            int(item.get("weight", 3))
        )
        for item in words
    )

    current_weight = max(
        1,
        int(word.get("weight", 3))
    )

    return (
        current_weight
        /
        total_weight
        *
        100
    )


# ============================================================
# 新词概率
#
# ★ 与正式词库完全独立
# ============================================================

def calculate_new_probability(word):

    if not new_words:
        return 0

    total_weight = sum(
        max(
            1,
            int(item.get("weight", 3))
        )
        for item in new_words
    )

    current_weight = max(
        1,
        int(word.get("weight", 3))
    )

    return (
        current_weight
        /
        total_weight
        *
        100
    )


# ============================================================
# 正式词库随机抽题
# ============================================================

def get_random_word():

    if not words:
        return None

    weights = [
        max(
            1,
            int(word.get("weight", 3))
        )
        for word in words
    ]

    return random.choices(
        words,
        weights=weights,
        k=1
    )[0]


# ============================================================
# 新词随机抽题
# ============================================================

def get_random_new_word():

    if not new_words:
        return None

    weights = [
        max(
            1,
            int(word.get("weight", 3))
        )
        for word in new_words
    ]

    return random.choices(
        new_words,
        weights=weights,
        k=1
    )[0]


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

    page = st.radio(
        "功能",
        [
            "🎓 学习模式",
            "🎯 练习模式",
            "📚 词库管理",
            "📖 查看词库"
        ]
    )


# ============================================================
# ============================================================
# 学习模式
# ============================================================
# ============================================================

if page == "🎓 学习模式":

    st.header("🎓 学习模式")

    # ========================================================
    # 添加新词
    # ========================================================

    st.subheader("➕ 添加新词")

    col1, col2 = st.columns(2)

    with col1:

        learning_english_text = st.text_area(
            "英文",
            height=100,
            placeholder="abandon\ncareer\nimprove"
        )

    with col2:

        learning_chinese_text = st.text_area(
            "中文",
            height=100,
            placeholder="放弃\n职业\n改善"
        )

    learning_category = st.selectbox(
        "词性",
        CATEGORIES,
        index=0,
        key="learning_add_category"
    )

    if st.button(
        "➕ 添加新词",
        use_container_width=True
    ):

        english_list = [
            x.strip()
            for x in learning_english_text.splitlines()
            if x.strip()
        ]

        chinese_list = [
            x.strip()
            for x in learning_chinese_text.splitlines()
            if x.strip()
        ]

        if not english_list:

            st.warning("请输入英文单词。")

        elif len(english_list) != len(chinese_list):

            st.error(
                "英文和中文的数量必须相同。"
            )

        else:

            added = 0
            duplicate = 0

            for english, chinese in zip(
                english_list,
                chinese_list
            ):

                # ------------------------------------------------
                # 检查今天新词是否已经存在
                # ------------------------------------------------

                exists_new = any(
                    item.get(
                        "english",
                        ""
                    ).strip().lower()
                    == english.lower()

                    and

                    item.get(
                        "chinese",
                        ""
                    ).strip()
                    == chinese

                    and

                    item.get(
                        "category",
                        "noun"
                    )
                    == learning_category

                    for item in new_words
                )

                if exists_new:

                    duplicate += 1
                    continue

                # ------------------------------------------------
                # 加入新词模式
                # ------------------------------------------------

                new_word = {
                    "english": english,
                    "chinese": chinese,
                    "category": learning_category,

                    # ★ 新词独立权重
                    "weight": 3
                }

                new_words.append(new_word)

                # ------------------------------------------------
                # 同时加入正式词库
                # ------------------------------------------------

                exists_vocabulary = any(
                    item.get(
                        "english",
                        ""
                    ).strip().lower()
                    == english.lower()

                    and

                    item.get(
                        "chinese",
                        ""
                    ).strip()
                    == chinese

                    and

                    item.get(
                        "category",
                        "noun"
                    )
                    == learning_category

                    for item in words
                )

                if not exists_vocabulary:

                    words.append(
                        {
                            "english": english,
                            "chinese": chinese,
                            "category": learning_category,

                            "weight": 3,

                            "cn_to_en_correct": 0,
                            "cn_to_en_wrong": 0,

                            "en_to_cn_correct": 0,
                            "en_to_cn_wrong": 0,

                            "correct": 0,
                            "wrong": 0
                        }
                    )

                added += 1

            if added > 0:

                new_success = save_new_words()
                vocab_success = save_words()

                if new_success and vocab_success:

                    st.success(
                        f"成功添加 {added} 个新词，"
                        f"并已同步到正式词库。"
                    )

                    st.rerun()

                else:

                    st.error(
                        "保存失败，请检查 GitHub Token。"
                    )

            if duplicate:

                st.info(
                    f"{duplicate} 个今天已经存在的新词没有重复添加。"
                )


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

            selected_new_word = get_random_new_word()

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

                        st.markdown(
                            f"""
                            <div class="previous-question">
                                {html.escape(last_word["chinese"])}
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

                        st.markdown(
                            f"""
                            <div class="previous-question">
                                {html.escape(last_word["english"])}
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

                    st.markdown(
                        f"""
                        <div class="question">
                            {html.escape(
                                learning_word["chinese"]
                            )}
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

                    st.markdown(
                        f"""
                        <div class="question">
                            {html.escape(
                                learning_word["english"]
                            )}
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
                    # ★ 新词独立概率机制
                    #
                    # 正确：
                    # weight -1
                    #
                    # 错误：
                    # weight +2
                    #
                    # 范围 1~20
                    #
                    # 不写 correct / wrong
                    # =========================================

                    if is_correct:

                        learning_word["weight"] = max(
                            1,
                            int(
                                learning_word.get(
                                    "weight",
                                    3
                                )
                            ) - 1
                        )

                    else:

                        learning_word["weight"] = min(
                            20,
                            int(
                                learning_word.get(
                                    "weight",
                                    3
                                )
                            ) + 2
                        )


                    # =========================================
                    # 保存新词
                    # =========================================

                    save_success = save_new_words()


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

                    next_new_word = get_random_new_word()

                    if next_new_word is not None:

                        st.session_state.learning_word_index = (
                            new_words.index(
                                next_new_word
                            )
                        )

                    if not save_success:

                        st.error(
                            "⚠️ 新词数据保存失败，请检查 GitHub Token 权限。"
                        )

                    st.rerun()


    # ========================================================
    # ★ 学习模式最底部：编辑列表
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
                f"{word['english']} → "
                f"{word['chinese']} "
                f"({word.get('category', 'noun')})"
            ):

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

                st.caption(
                    f"独立权重："
                    f"{word.get('weight', 3)}"
                )

                st.caption(
                    f"抽题概率："
                    f"{calculate_new_probability(word):.2f}%"
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

                            old_english = (
                                word["english"]
                            )

                            old_chinese = (
                                word["chinese"]
                            )

                            old_category = (
                                word.get(
                                    "category",
                                    "noun"
                                )
                            )

                            word["english"] = (
                                edit_new_english
                            )

                            word["chinese"] = (
                                edit_new_chinese
                            )

                            word["category"] = (
                                edit_new_category
                            )

                            # =================================
                            # 同步修改正式词库中对应词汇
                            # =================================

                            for vocabulary_word in words:

                                if (
                                    vocabulary_word.get(
                                        "english",
                                        ""
                                    ).strip().lower()
                                    ==
                                    old_english.strip().lower()

                                    and

                                    vocabulary_word.get(
                                        "chinese",
                                        ""
                                    ).strip()
                                    ==
                                    old_chinese.strip()

                                    and

                                    vocabulary_word.get(
                                        "category",
                                        "noun"
                                    )
                                    ==
                                    old_category
                                ):

                                    vocabulary_word[
                                        "english"
                                    ] = edit_new_english

                                    vocabulary_word[
                                        "chinese"
                                    ] = edit_new_chinese

                                    vocabulary_word[
                                        "category"
                                    ] = edit_new_category

                                    break


                            new_success = (
                                save_new_words()
                            )

                            vocab_success = (
                                save_words()
                            )

                            if (
                                new_success
                                and
                                vocab_success
                            ):

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

                        deleted_word = new_words.pop(
                            index
                        )

                        # =================================
                        # 注意：
                        #
                        # 删除新词列表不会删除正式词库
                        #
                        # 因为这个词已经正式加入词库。
                        # =================================

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

    # ★ 恢复页面标题

    st.header("🎯 练习模式")

    if not words:

        st.warning(
            "词库为空，请先到「词库管理」添加单词。"
        )

    else:

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
            != st.session_state.question_type
        ):

            st.session_state.question_type = (
                question_type
            )

            st.session_state.current_word_index = None
            st.session_state.last_word_index = None
            st.session_state.last_answer = ""
            st.session_state.last_correct = None


        if (
            st.session_state.current_word_index is None
            or
            st.session_state.current_word_index >= len(words)
        ):

            selected_word = get_random_word()

            if selected_word is not None:

                st.session_state.current_word_index = (
                    words.index(selected_word)
                )


        current_index = (
            st.session_state.current_word_index
        )

        word = words[current_index]

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

                    st.markdown(
                        f"""
                        <div class="previous-question">
                            {html.escape(last_word["chinese"])}
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

                    st.markdown(
                        f"""
                        <div class="previous-question">
                            {html.escape(last_word["english"])}
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

                        last_word["weight"] = max(
                            1,
                            int(
                                last_word.get(
                                    "weight",
                                    3
                                )
                            ) - 2
                        )


                        save_words()


                        if question_type == "中译英":

                            daily_stats[
                                "cn_to_en_correct"
                            ] += 1

                        else:

                            daily_stats[
                                "en_to_cn_correct"
                            ] += 1


                        save_daily_stats()

                        st.session_state.last_correct = True

                        st.rerun()


        # ====================================================
        # 下一题
        # ====================================================

        with right:

            st.markdown("### 下一题")

            if question_type == "中译英":

                st.markdown(
                    f"""
                    <div class="question">
                        {html.escape(word["chinese"])}
                    </div>

                    <div class="question-category">
                        {html.escape(current_category)}
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            else:

                st.markdown(
                    f"""
                    <div class="question">
                        {html.escape(word["english"])}
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

                    if question_type == "中译英":

                        word["cn_to_en_correct"] += 1

                    else:

                        word["en_to_cn_correct"] += 1


                    word["correct"] = (
                        int(
                            word.get(
                                "correct",
                                0
                            )
                        ) + 1
                    )


                    word["weight"] = max(
                        1,
                        int(
                            word.get(
                                "weight",
                                3
                            )
                        ) - 1
                    )

                    is_correct = True


                else:

                    if question_type == "中译英":

                        word["cn_to_en_wrong"] += 1

                    else:

                        word["en_to_cn_wrong"] += 1


                    word["wrong"] = (
                        int(
                            word.get(
                                "wrong",
                                0
                            )
                        ) + 1
                    )


                    word["weight"] = min(
                        20,
                        int(
                            word.get(
                                "weight",
                                3
                            )
                        ) + 2
                    )

                    is_correct = False


                save_success = save_words()


                today = get_today()

                if daily_stats.get("date") != today:

                    daily_stats = default_daily_stats()


                if question_type == "中译英":

                    daily_stats[
                        "cn_to_en_answered"
                    ] += 1

                    if is_correct:

                        daily_stats[
                            "cn_to_en_correct"
                        ] += 1

                else:

                    daily_stats[
                        "en_to_cn_answered"
                    ] += 1

                    if is_correct:

                        daily_stats[
                            "en_to_cn_correct"
                        ] += 1


                save_daily_stats()


                st.session_state.last_word_index = (
                    current_index
                )

                st.session_state.last_answer = answer

                st.session_state.last_correct = is_correct


                next_word = get_random_word()

                if next_word is not None:

                    st.session_state.current_word_index = (
                        words.index(next_word)
                    )


                if not save_success:

                    st.error(
                        "⚠️ 数据保存失败，请检查 GitHub Token 权限。"
                    )

                st.rerun()


        # ====================================================
        # 今日统计
        # ====================================================

        st.divider()

        cn_answered = int(
            daily_stats.get(
                "cn_to_en_answered",
                0
            )
        )

        cn_correct = int(
            daily_stats.get(
                "cn_to_en_correct",
                0
            )
        )

        en_answered = int(
            daily_stats.get(
                "en_to_cn_answered",
                0
            )
        )

        en_correct = int(
            daily_stats.get(
                "en_to_cn_correct",
                0
            )
        )


        total_answered = (
            cn_answered + en_answered
        )

        total_correct = (
            cn_correct + en_correct
        )


        st.subheader("📊 今日统计")


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

            accuracy = (
                total_correct
                /
                total_answered
                *
                100
            )

            st.caption(
                f"今日总正确率：{accuracy:.1f}%"
            )


# ============================================================
# ============================================================
# 词库管理
# ============================================================
# ============================================================

elif page == "📚 词库管理":

    st.header("📚 词库管理")

    st.subheader("➕ 添加单词")

    col1, col2 = st.columns(2)

    with col1:

        english_text = st.text_area(
            "英文",
            height=100,
            placeholder="second\ncareer\nrun"
        )

    with col2:

        chinese_text = st.text_area(
            "中文",
            height=100,
            placeholder="秒\n职业\n跑"
        )

    category = st.selectbox(
        "词性",
        CATEGORIES,
        index=0,
        key="vocab_add_category"
    )

    if st.button(
        "➕ 添加",
        use_container_width=True
    ):

        english_list = [
            x.strip()
            for x in english_text.splitlines()
            if x.strip()
        ]

        chinese_list = [
            x.strip()
            for x in chinese_text.splitlines()
            if x.strip()
        ]

        if not english_list:

            st.warning("请输入英文单词。")

        elif len(english_list) != len(chinese_list):

            st.error(
                "英文和中文的数量必须相同。"
            )

        else:

            added = 0
            duplicate = 0

            for english, chinese in zip(
                english_list,
                chinese_list
            ):

                exists = any(
                    item.get("english", "").strip().lower()
                    == english.strip().lower()

                    and

                    item.get("chinese", "").strip()
                    == chinese.strip()

                    and

                    item.get("category", "noun")
                    == category

                    for item in words
                )

                if exists:

                    duplicate += 1

                else:

                    words.append(
                        {
                            "english": english,
                            "chinese": chinese,
                            "category": category,

                            "weight": 3,

                            "cn_to_en_correct": 0,
                            "cn_to_en_wrong": 0,

                            "en_to_cn_correct": 0,
                            "en_to_cn_wrong": 0,

                            "correct": 0,
                            "wrong": 0
                        }
                    )

                    added += 1

            if added > 0:

                if save_words():

                    st.success(
                        f"成功添加 {added} 个单词，并已同步到 GitHub。"
                    )

            if duplicate:

                st.info(
                    f"{duplicate} 个完全相同的单词没有添加。"
                )

    st.divider()

    st.subheader("✏️ 编辑词库")

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

        with st.expander(
            f"{word['english']} → "
            f"{word['chinese']} "
            f"({word.get('category', 'noun')})"
        ):

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
                f"权重：{word.get('weight', 3)}"
            )

            st.caption(
                f"中译英："
                f"✓ {word.get('cn_to_en_correct', 0)} "
                f"/ "
                f"✗ {word.get('cn_to_en_wrong', 0)}"
            )

            st.caption(
                f"英译中："
                f"✓ {word.get('en_to_cn_correct', 0)} "
                f"/ "
                f"✗ {word.get('en_to_cn_wrong', 0)}"
            )

            st.caption(
                f"抽题概率："
                f"{calculate_probability(word):.2f}%"
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

                        if save_words():

                            st.success(
                                "修改成功，并已同步到 GitHub。"
                            )

                            st.rerun()

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

        search = st.text_input(
            "🔍 搜索词库",
            placeholder="输入英文或中文",
            key="view_vocab_search"
        )

        category_filter = st.selectbox(
            "词性筛选",
            [
                "全部",
                "noun",
                "verb",
                "adjective",
                "adverb"
            ],
            key="view_category_filter"
        )

        filtered_words = []

        for word in words:

            if search:

                if (
                    search.lower()
                    not in word["english"].lower()

                    and

                    search
                    not in word["chinese"]
                ):

                    continue

            if (
                category_filter != "全部"

                and

                word.get("category", "noun")
                != category_filter
            ):

                continue

            filtered_words.append(word)


        st.caption(
            f"找到 {len(filtered_words)} 个单词"
        )


        # ====================================================
        # 排序
        # ====================================================

        sort_field = st.session_state.vocab_sort_field
        reverse = st.session_state.vocab_sort_reverse

        if sort_field == "english":

            filtered_words.sort(
                key=lambda x: x.get(
                    "english",
                    ""
                ).lower(),
                reverse=reverse
            )

        elif sort_field == "chinese":

            filtered_words.sort(
                key=lambda x: x.get(
                    "chinese",
                    ""
                ),
                reverse=reverse
            )

        elif sort_field == "category":

            filtered_words.sort(
                key=lambda x: x.get(
                    "category",
                    ""
                ),
                reverse=reverse
            )

        elif sort_field == "weight":

            filtered_words.sort(
                key=lambda x: int(
                    x.get(
                        "weight",
                        3
                    )
                ),
                reverse=reverse
            )

        elif sort_field == "probability":

            filtered_words.sort(
                key=lambda x: calculate_probability(x),
                reverse=reverse
            )

        elif sort_field == "correct":

            filtered_words.sort(
                key=lambda x:
                int(x.get("cn_to_en_correct", 0))
                +
                int(x.get("en_to_cn_correct", 0)),
                reverse=reverse
            )

        elif sort_field == "wrong":

            filtered_words.sort(
                key=lambda x:
                int(x.get("cn_to_en_wrong", 0))
                +
                int(x.get("en_to_cn_wrong", 0)),
                reverse=reverse
            )


        st.markdown(
            '<div class="mobile-hint">'
            '📱 手机可以左右滑动查看完整词库；点击表头按钮排序'
            '</div>',
            unsafe_allow_html=True
        )


        cols = st.columns(
            [2, 2, 1.2, 0.9, 1.2, 0.8, 0.8]
        )


        def sort_label(field, text):

            if st.session_state.vocab_sort_field != field:

                return text

            if st.session_state.vocab_sort_reverse:

                return text + " ↓"

            return text + " ↑"


        with cols[0]:

            if st.button(
                sort_label("english", "英文"),
                key="sort_english",
                use_container_width=True
            ):

                set_sort("english")
                st.rerun()


        with cols[1]:

            if st.button(
                sort_label("chinese", "中文"),
                key="sort_chinese",
                use_container_width=True
            ):

                set_sort("chinese")
                st.rerun()


        with cols[2]:

            if st.button(
                sort_label("category", "词性"),
                key="sort_category",
                use_container_width=True
            ):

                set_sort("category")
                st.rerun()


        with cols[3]:

            if st.button(
                sort_label("weight", "权重"),
                key="sort_weight",
                use_container_width=True
            ):

                set_sort("weight")
                st.rerun()


        with cols[4]:

            if st.button(
                sort_label("probability", "概率"),
                key="sort_probability",
                use_container_width=True
            ):

                set_sort("probability")
                st.rerun()


        with cols[5]:

            if st.button(
                sort_label("correct", "✓"),
                key="sort_correct",
                use_container_width=True
            ):

                set_sort("correct")
                st.rerun()


        with cols[6]:

            if st.button(
                sort_label("wrong", "✗"),
                key="sort_wrong",
                use_container_width=True
            ):

                set_sort("wrong")
                st.rerun()


        # ====================================================
        # HTML 表格
        # ====================================================

        rows = ""

        for word in filtered_words:

            english = html.escape(
                str(word.get("english", ""))
            )

            chinese = html.escape(
                str(word.get("chinese", ""))
            )

            category = html.escape(
                str(
                    word.get(
                        "category",
                        "noun"
                    )
                )
            )

            weight = int(
                word.get(
                    "weight",
                    3
                )
            )

            probability = calculate_probability(
                word
            )

            total_correct = (
                int(
                    word.get(
                        "cn_to_en_correct",
                        0
                    )
                )
                +
                int(
                    word.get(
                        "en_to_cn_correct",
                        0
                    )
                )
            )

            total_wrong = (
                int(
                    word.get(
                        "cn_to_en_wrong",
                        0
                    )
                )
                +
                int(
                    word.get(
                        "en_to_cn_wrong",
                        0
                    )
                )
            )

            rows += f"""
            <tr>

                <td class="english">
                    {english}
                </td>

                <td>
                    {chinese}
                </td>

                <td>
                    {category}
                </td>

                <td>
                    {weight}
                </td>

                <td class="probability">
                    {probability:.2f}%
                </td>

                <td>
                    {total_correct}
                </td>

                <td>
                    {total_wrong}
                </td>

            </tr>
            """


        table_html = f"""
        <!DOCTYPE html>

        <html>

        <head>

        <meta charset="UTF-8">

        <meta name="viewport"
              content="width=device-width,
                       initial-scale=1.0">

        <style>

        * {{
            box-sizing: border-box;
        }}

        html,
        body {{
            margin: 0;
            padding: 0;
            width: 100%;
        }}

        body {{

            font-family:
                -apple-system,
                BlinkMacSystemFont,
                "Segoe UI",
                Arial,
                sans-serif;

            font-size: 14px;

            background-color: #ffffff;

            color: #1f1f1f;

        }}

        .table-wrapper {{

            width: 100%;

            overflow-x: auto;

            -webkit-overflow-scrolling: touch;

            border: 1px solid #d9d9d9;

            border-radius: 10px;

            background-color: #ffffff;

        }}

        table {{

            width: 100%;

            min-width: 720px;

            border-collapse: collapse;

            background-color: #ffffff;

            color: #1f1f1f;

        }}

        th {{

            padding: 10px 8px;

            text-align: left;

            font-weight: 700;

            color: #1f1f1f;

            background-color: #f3f4f6;

            border-bottom:
                2px solid
                #cfcfcf;

            white-space: nowrap;

        }}

        td {{

            padding: 9px 8px;

            color: #1f1f1f;

            background-color: #ffffff;

            border-bottom:
                1px solid
                #e5e5e5;

            white-space: nowrap;

        }}

        tr:last-child td {{

            border-bottom: none;

        }}

        tbody tr:hover td {{

            background-color: #f5f5f5;

        }}

        .english {{

            font-weight: 600;

            color: #111111;

        }}

        .probability {{

            font-size: 13px;

            color: #444444;

        }}

        @media (prefers-color-scheme: dark) {{

            body {{

                background-color: #0e1117;

                color: #f1f1f1;

            }}

            .table-wrapper {{

                background-color: #0e1117;

                border-color: #3a3f47;

            }}

            table {{

                background-color: #0e1117;

                color: #f1f1f1;

            }}

            th {{

                color: #ffffff;

                background-color: #262b33;

                border-bottom-color: #4a5059;

            }}

            td {{

                color: #f1f1f1;

                background-color: #0e1117;

                border-bottom-color: #30353d;

            }}

            tbody tr:hover td {{

                background-color: #1c2128;

            }}

            .english {{

                color: #ffffff;

            }}

            .probability {{

                color: #d0d0d0;

            }}

        }}

        @media (max-width: 700px) {{

            th,
            td {{

                padding: 8px 7px;

                font-size: 13px;

            }}

        }}

        </style>

        </head>

        <body>

        <div class="table-wrapper">

        <table>

            <thead>

                <tr>

                    <th>英文</th>

                    <th>中文</th>

                    <th>词性</th>

                    <th>权重</th>

                    <th>概率</th>

                    <th>✓</th>

                    <th>✗</th>

                </tr>

            </thead>

            <tbody>

                {rows}

            </tbody>

        </table>

        </div>

        </body>

        </html>
        """


        st.components.v1.html(
            table_html,
            height=max(
                120,
                min(
                    800,
                    65 + len(filtered_words) * 44
                )
            ),
            scrolling=True
        )
