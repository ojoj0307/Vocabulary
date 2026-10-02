import streamlit as st
import json
import random
import base64
import html
import requests
import pandas as pd

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

.attr-info {
    background-color: rgba(28, 131, 225, 0.1);
    border-radius: 6px;
    padding: 8px 12px;
    margin: 8px 0;
    font-size: 14px;
}

.note-info {
    background-color: rgba(255, 193, 7, 0.15);
    border-radius: 6px;
    padding: 8px 12px;
    margin: 8px 0;
    font-size: 14px;
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
        st.info("请在 Streamlit Cloud → Settings → Secrets 添加 GITHUB_TOKEN。")
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
            content = result.get("content", "").replace("\n", "")
            decoded = base64.b64decode(content).decode("utf-8")
            return decoded, result.get("sha")
        elif response.status_code == 404:
            return None, None
        else:
            st.error(f"GitHub API 错误：{response.status_code} {response.text}")
            return None, None
    except Exception as e:
        st.error(f"无法连接 GitHub：{e}")
        return None, None


# ============================================================
# GitHub 保存
# ============================================================

def github_save_file(path, data, sha=None, message="Update file"):
    if not check_github_token():
        return False

    url = GITHUB_API_BASE + path
    try:
        json_text = json.dumps(data, ensure_ascii=False, indent=4)
        encoded = base64.b64encode(json_text.encode("utf-8")).decode("utf-8")
        payload = {"message": message, "content": encoded}
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

        st.error(f"GitHub API 错误：{response.status_code} {response.text}")
        return False
    except Exception as e:
        st.error(f"保存到 GitHub 失败：{e}")
        return False


# ============================================================
# 今日日期
# ============================================================

def get_today():
    return datetime.now(MALAYSIA_TZ).strftime("%Y-%m-%d")


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
# ============================================================

def default_new_words():
    return {
        "date": get_today(),
        "words": []
    }


# ============================================================
# 标准化正式词库 & 新词
# ============================================================

def normalize_word_dict(word, is_new_word=False):
    changed = False

    if "english" not in word:
        word["english"] = ""
        changed = True
    if "chinese" not in word:
        word["chinese"] = ""
        changed = True
    if "category" not in word or word.get("category") not in CATEGORIES:
        word["category"] = "noun"
        changed = True

    # 独立权重支持
    old_weight = word.get("weight", 3)
    if "cn_to_en_weight" not in word:
        word["cn_to_en_weight"] = old_weight
        changed = True
    if "en_to_cn_weight" not in word:
        word["en_to_cn_weight"] = old_weight
        changed = True

    # 新词不记录做题统计
    if not is_new_word:
        if "cn_to_en_correct" not in word:
            word["cn_to_en_correct"] = int(word.get("correct", 0))
            changed = True
        if "cn_to_en_wrong" not in word:
            word["cn_to_en_wrong"] = int(word.get("wrong", 0))
            changed = True
        if "en_to_cn_correct" not in word:
            word["en_to_cn_correct"] = 0
            changed = True
        if "en_to_cn_wrong" not in word:
            word["en_to_cn_wrong"] = 0
            changed = True

    # 扩展属性
    # 名词
    if "is_countable" not in word:
        word["is_countable"] = True
        changed = True
    if "plural" not in word:
        word["plural"] = ""
        changed = True

    # 动词
    if "third_person" not in word:
        word["third_person"] = ""
        changed = True
    if "past_tense" not in word:
        word["past_tense"] = ""
        changed = True
    if "past_participle" not in word:
        word["past_participle"] = ""
        changed = True

    # 形容词
    if "comparative" not in word:
        word["comparative"] = ""
        changed = True
    if "superlative" not in word:
        word["superlative"] = ""
        changed = True

    # 备注
    if "cn_note" not in word:
        word["cn_note"] = ""
        changed = True
    if "en_note" not in word:
        word["en_note"] = ""
        changed = True

    return changed


def normalize_vocabulary(data):
    changed = False
    for word in data:
        if normalize_word_dict(word, is_new_word=False):
            changed = True
    return changed


def normalize_new_words_list(words_list):
    changed = False
    for word in words_list:
        if normalize_word_dict(word, is_new_word=True):
            changed = True
    return changed


# ============================================================
# 加载正式词库
# ============================================================

def load_words():
    content, sha = github_get_file(VOCABULARY_PATH)
    if content is None:
        st.error("无法读取 GitHub 上的 vocabulary.json")
        return [], None

    try:
        data = json.loads(content)
    except Exception as e:
        st.error(f"vocabulary.json 格式错误：{e}")
        return [], sha

    if not isinstance(data, list):
        st.error("vocabulary.json 必须是数组。")
        return [], sha

    changed = normalize_vocabulary(data)
    if changed:
        _, latest_sha = github_get_file(VOCABULARY_PATH)
        if latest_sha:
            if github_save_file(VOCABULARY_PATH, data, latest_sha, "Update vocabulary structure"):
                _, sha = github_get_file(VOCABULARY_PATH)

    return data, sha


# ============================================================
# 加载新词
# ============================================================

def load_new_words():
    content, sha = github_get_file(NEW_WORDS_PATH)
    if content is None:
        data = default_new_words()
        success = github_save_file(NEW_WORDS_PATH, data, None, "Create new words")
        if success:
            _, sha = github_get_file(NEW_WORDS_PATH)
        return data, sha

    try:
        raw_data = json.loads(content)
    except Exception:
        raw_data = default_new_words()

    if isinstance(raw_data, list):
        data = {"date": get_today(), "words": raw_data}
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

    if "words" not in data or not isinstance(data["words"], list):
        data["words"] = []
        changed = True

    today = get_today()
    if data["date"] != today:
        data["date"] = today
        data["words"] = []
        changed = True

    if normalize_new_words_list(data["words"]):
        changed = True

    if changed:
        _, latest_sha = github_get_file(NEW_WORDS_PATH)
        if latest_sha:
            if github_save_file(NEW_WORDS_PATH, data, latest_sha, "Update daily new words"):
                _, sha = github_get_file(NEW_WORDS_PATH)

    return data, sha


# ============================================================
# 每日统计
# ============================================================

def load_daily_stats():
    content, sha = github_get_file(DAILY_STATS_PATH)
    if content is None:
        data = default_daily_stats()
        if github_save_file(DAILY_STATS_PATH, data, None, "Create daily statistics"):
            _, sha = github_get_file(DAILY_STATS_PATH)
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

    for field in ["cn_to_en_answered", "cn_to_en_correct", "en_to_cn_answered", "en_to_cn_correct"]:
        if field not in data:
            data[field] = 0
            changed = True

    if changed:
        _, new_sha = github_get_file(DAILY_STATS_PATH)
        if new_sha:
            if github_save_file(DAILY_STATS_PATH, data, new_sha, "Update daily statistics"):
                _, sha = github_get_file(DAILY_STATS_PATH)

    return data, sha


# ============================================================
# 加载全部数据
# ============================================================

words, vocabulary_sha = load_words()
new_words_data, new_words_sha = load_new_words()
daily_stats, daily_stats_sha = load_daily_stats()

new_words = new_words_data["words"]


# ============================================================
# 保存函数
# ============================================================

def save_words():
    global vocabulary_sha
    _, latest_sha = github_get_file(VOCABULARY_PATH)
    if latest_sha is None:
        return False
    success = github_save_file(VOCABULARY_PATH, words, latest_sha, "Update vocabulary")
    if success:
        _, vocabulary_sha = github_get_file(VOCABULARY_PATH)
    return success


def save_new_words():
    global new_words_sha
    new_words_data["date"] = get_today()
    new_words_data["words"] = new_words
    _, latest_sha = github_get_file(NEW_WORDS_PATH)
    if latest_sha is None:
        return False
    success = github_save_file(NEW_WORDS_PATH, new_words_data, latest_sha, "Update daily new words")
    if success:
        _, new_words_sha = github_get_file(NEW_WORDS_PATH)
    return success


def save_daily_stats():
    global daily_stats_sha
    _, latest_sha = github_get_file(DAILY_STATS_PATH)
    if latest_sha is None:
        return False
    success = github_save_file(DAILY_STATS_PATH, daily_stats, latest_sha, "Update daily statistics")
    if success:
        _, daily_stats_sha = github_get_file(DAILY_STATS_PATH)
    return success


# ============================================================
# 计算概率 (支持中译英/英译中独立概率)
# ============================================================

def calculate_probability(word, q_type="中译英", is_new=False):
    target_list = new_words if is_new else words
    if not target_list:
        return 0.0

    weight_key = "cn_to_en_weight" if q_type == "中译英" else "en_to_cn_weight"

    total_weight = sum(max(1, int(item.get(weight_key, 3))) for item in target_list)
    current_weight = max(1, int(word.get(weight_key, 3)))

    return (current_weight / total_weight) * 100 if total_weight > 0 else 0.0


# ============================================================
# 随机抽题 (支持中译英/英译中独立抽题)
# ============================================================

def get_random_word(q_type="中译英"):
    if not words:
        return None
    weight_key = "cn_to_en_weight" if q_type == "中译英" else "en_to_cn_weight"
    weights = [max(1, int(word.get(weight_key, 3))) for word in words]
    return random.choices(words, weights=weights, k=1)[0]


def get_random_new_word(q_type="中译英"):
    if not new_words:
        return None
    weight_key = "cn_to_en_weight" if q_type == "中译英" else "en_to_cn_weight"
    weights = [max(1, int(word.get(weight_key, 3))) for word in new_words]
    return random.choices(new_words, weights=weights, k=1)[0]


# ============================================================
# 渲染单词特殊属性 HTML
# ============================================================

def render_word_attributes(word_dict):
    category = word_dict.get("category", "noun")
    attrs = []

    if category == "noun":
        if word_dict.get("is_countable", True):
            plural = word_dict.get("plural", "").strip()
            attrs.append(f"可数 (复数: <b>{html.escape(plural if plural else '规则变化')}</b>)")
        else:
            attrs.append("不可数名词")

    elif category == "verb":
        tp = word_dict.get("third_person", "").strip()
        pt = word_dict.get("past_tense", "").strip()
        pp = word_dict.get("past_participle", "").strip()
        if tp: attrs.append(f"三单: <b>{html.escape(tp)}</b>")
        if pt: attrs.append(f"过去式: <b>{html.escape(pt)}</b>")
        if pp: attrs.append(f"过去完成式: <b>{html.escape(pp)}</b>")

    elif category == "adjective":
        comp = word_dict.get("comparative", "").strip()
        sup = word_dict.get("superlative", "").strip()
        if comp: attrs.append(f"比较级: <b>{html.escape(comp)}</b>")
        if sup: attrs.append(f"最高级: <b>{html.escape(sup)}</b>")

    if attrs:
        return f"""<div class="attr-info">📌 <b>词性变形：</b> {' | '.join(attrs)}</div>"""
    return ""


# ============================================================
# 渲染备注 HTML
# ============================================================

def render_word_note(word_dict, q_type="中译英"):
    note = word_dict.get("cn_note", "").strip() if q_type == "中译英" else word_dict.get("en_note", "").strip()
    if note:
        return f"""<div class="note-info">📝 <b>备注：</b> {html.escape(note)}</div>"""
    return ""


# ============================================================
# 通用单词编辑组件 (Expander 内部使用)
# ============================================================

def render_word_edit_form(word, index, prefix="vocab", is_new_word=False):
    col1, col2 = st.columns(2)
    with col1:
        edit_english = st.text_input("英文", value=word.get("english", ""), key=f"{prefix}_en_{index}")
    with col2:
        edit_chinese = st.text_input("中文", value=word.get("chinese", ""), key=f"{prefix}_cn_{index}")

    current_cat = word.get("category", "noun")
    edit_category = st.selectbox(
        "词性",
        CATEGORIES,
        index=CATEGORIES.index(current_cat) if current_cat in CATEGORIES else 0,
        key=f"{prefix}_cat_{index}"
    )

    # 分词性属性编辑
    if edit_category == "noun":
        c_col1, c_col2 = st.columns(2)
        with c_col1:
            is_countable = st.checkbox("可数名词", value=word.get("is_countable", True), key=f"{prefix}_cnt_{index}")
        with c_col2:
            plural = st.text_input("复数形式 (留空默认规则变化)", value=word.get("plural", ""), key=f"{prefix}_pl_{index}")
        third_person, past_tense, past_participle, comparative, superlative = "", "", "", "", ""

    elif edit_category == "verb":
        v_col1, v_col2, v_col3 = st.columns(3)
        with v_col1:
            third_person = st.text_input("第三人称单数", value=word.get("third_person", ""), key=f"{prefix}_tp_{index}")
        with v_col2:
            past_tense = st.text_input("过去式", value=word.get("past_tense", ""), key=f"{prefix}_pt_{index}")
        with v_col3:
            past_participle = st.text_input("过去完成式", value=word.get("pp_{index}", word.get("past_participle", "")), key=f"{prefix}_pp_{index}")
        is_countable, plural, comparative, superlative = True, "", "", ""

    elif edit_category == "adjective":
        a_col1, a_col2 = st.columns(2)
        with a_col1:
            comparative = st.text_input("比较级", value=word.get("comparative", ""), key=f"{prefix}_comp_{index}")
        with a_col2:
            superlative = st.text_input("最高级", value=word.get("superlative", ""), key=f"{prefix}_sup_{index}")
        is_countable, plural, third_person, past_tense, past_participle = True, "", "", "", ""
    else:
        is_countable, plural, third_person, past_tense, past_participle, comparative, superlative = True, "", "", "", "", "", ""

    # 备注编辑
    n_col1, n_col2 = st.columns(2)
    with n_col1:
        cn_note = st.text_input("中文备注 (中译英显示)", value=word.get("cn_note", ""), key=f"{prefix}_cn_note_{index}")
    with n_col2:
        en_note = st.text_input("英文备注 (英译中显示)", value=word.get("en_note", ""), key=f"{prefix}_en_note_{index}")

    # 权重与概率显示
    cn_prob = calculate_probability(word, "中译英", is_new=is_new_word)
    en_prob = calculate_probability(word, "英译中", is_new=is_new_word)
    st.caption(f"📊 抽题概率 — 中译英: **{cn_prob:.2f}%** (权重 {word.get('cn_to_en_weight', 3)}) | 英译中: **{en_prob:.2f}%** (权重 {word.get('en_to_cn_weight', 3)})")

    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        if st.button("💾 保存", key=f"{prefix}_save_{index}", use_container_width=True):
            if not edit_english.strip() or not edit_chinese.strip():
                st.warning("英文和中文不能为空。")
            else:
                old_en, old_cn, old_cat = word["english"], word["chinese"], word["category"]

                # 更新属性
                word.update({
                    "english": edit_english.strip(),
                    "chinese": edit_chinese.strip(),
                    "category": edit_category,
                    "is_countable": is_countable,
                    "plural": plural.strip(),
                    "third_person": third_person.strip(),
                    "past_tense": past_tense.strip(),
                    "past_participle": past_participle.strip(),
                    "comparative": comparative.strip(),
                    "superlative": superlative.strip(),
                    "cn_note": cn_note.strip(),
                    "en_note": en_note.strip()
                })

                if is_new_word:
                    # 同步更新正式词库
                    for v_word in words:
                        if (v_word.get("english", "").lower() == old_en.lower() and 
                            v_word.get("chinese", "") == old_cn and 
                            v_word.get("category") == old_cat):
                            v_word.update(word)
                            break
                    save_new_words()
                    save_words()
                else:
                    save_words()

                st.success("修改成功！")
                st.rerun()

    with btn_col2:
        if st.button("🗑️ 删除", key=f"{prefix}_del_{index}", use_container_width=True):
            if is_new_word:
                new_words.pop(index)
                save_new_words()
            else:
                words.pop(index)
                save_words()
            st.success("已删除！")
            st.rerun()


# ============================================================
# 发音按钮
# ============================================================

def pronunciation_button(text, key):
    encoded = base64.b64encode(str(text).encode("utf-8")).decode("ascii")
    html_code = f"""
    <html>
    <head><meta charset="UTF-8"><style>
    body {{ margin: 0; background: transparent; }}
    button {{ border: none; background: transparent; cursor: pointer; font-size: 21px; padding: 2px 6px; }}
    </style></head>
    <body>
    <button onclick="speak()" title="British English">🔊</button>
    <script>
    function speak() {{
        const encoded = "{encoded}";
        const text = decodeURIComponent(escape(atob(encoded)));
        window.speechSynthesis.cancel();
        const speech = new SpeechSynthesisUtterance(text);
        speech.lang = "en-GB";
        speech.rate = 0.85;
        window.speechSynthesis.speak(speech);
    }}
    </script>
    </body>
    </html>
    """
    st.components.v1.html(html_code, height=35, width=50, scrolling=False)


# ============================================================
# Session State 初始化
# ============================================================

for key in ["current_word_index", "last_word_index", "learning_word_index", "learning_last_word_index"]:
    if key not in st.session_state:
        st.session_state[key] = None

for key in ["question_type", "learning_question_type"]:
    if key not in st.session_state:
        st.session_state[key] = "中译英"

for key in ["last_answer", "learning_last_answer"]:
    if key not in st.session_state:
        st.session_state[key] = ""

for key in ["last_correct", "learning_last_correct"]:
    if key not in st.session_state:
        st.session_state[key] = None

if "vocab_sort_field" not in st.session_state:
    st.session_state.vocab_sort_field = None
if "vocab_sort_reverse" not in st.session_state:
    st.session_state.vocab_sort_reverse = False


def set_sort(field):
    if st.session_state.vocab_sort_field == field:
        st.session_state.vocab_sort_reverse = not st.session_state.vocab_sort_reverse
    else:
        st.session_state.vocab_sort_field = field
        st.session_state.vocab_sort_reverse = False


# ============================================================
# Title & Sidebar
# ============================================================

st.title("📚 English Vocabulary")

with st.sidebar:
    page = st.radio("功能", ["🎓 学习模式", "🎯 练习模式", "📚 词库管理", "📖 查看词库"])


# ============================================================
# 🎓 学习模式
# ============================================================

if page == "🎓 学习模式":
    st.header("🎓 学习模式")

    # 1. 表格添加新词
    st.subheader("➕ 添加新词 (表格形式，支持从 Excel 直接复制粘贴)")
    st.caption("提示：在 Excel 中选中英文和中文列，按 Ctrl+C 复制后，点击下方表格首行按 Ctrl+V 粘贴。")

    df_template = pd.DataFrame([
        {"英文": "", "中文": "", "词性": "noun", "中文备注": "", "英文备注": ""}
    ])

    edited_df = st.data_editor(
        df_template,
        num_rows="dynamic",
        column_config={
            "英文": st.column_config.TextColumn("英文", required=True),
            "中文": st.column_config.TextColumn("中文", required=True),
            "词性": st.column_config.SelectboxColumn("词性", options=CATEGORIES, required=True),
            "中文备注": st.column_config.TextColumn("中文备注 (可选)"),
            "英文备注": st.column_config.TextColumn("英文备注 (可选)"),
        },
        use_container_width=True,
        key="learning_table_input"
    )

    if st.button("➕ 确认批量添加新词", use_container_width=True):
        added, duplicate = 0, 0
        for _, row in edited_df.iterrows():
            en = str(row.get("英文", "")).strip()
            cn = str(row.get("中文", "")).strip()
            cat = str(row.get("词性", "noun")).strip()
            cn_note = str(row.get("中文备注", "")).strip()
            en_note = str(row.get("英文备注", "")).strip()

            if not en or not cn:
                continue

            # 校验是否存在
            exists_new = any(
                item["english"].lower() == en.lower() and 
                item["chinese"] == cn and 
                item.get("category") == cat
                for item in new_words
            )

            if exists_new:
                duplicate += 1
                continue

            new_item = {
                "english": en,
                "chinese": cn,
                "category": cat if cat in CATEGORIES else "noun",
                "cn_to_en_weight": 3,
                "en_to_cn_weight": 3,
                "is_countable": True,
                "plural": "",
                "third_person": "",
                "past_tense": "",
                "past_participle": "",
                "comparative": "",
                "superlative": "",
                "cn_note": cn_note,
                "en_note": en_note
            }

            new_words.append(new_item)

            # 同步添加到正式词库
            exists_vocab = any(
                item["english"].lower() == en.lower() and 
                item["chinese"] == cn and 
                item.get("category") == cat
                for item in words
            )

            if not exists_vocab:
                vocab_item = dict(new_item)
                vocab_item.update({
                    "cn_to_en_correct": 0,
                    "cn_to_en_wrong": 0,
                    "en_to_cn_correct": 0,
                    "en_to_cn_wrong": 0
                })
                words.append(vocab_item)

            added += 1

        if added > 0:
            if save_new_words() and save_words():
                st.success(f"成功添加 {added} 个新词，并已同步到正式词库！")
                st.rerun()
            else:
                st.error("保存失败，请检查 GitHub Token。")
        if duplicate > 0:
            st.info(f"{duplicate} 个今日已存在的新词已被跳过。")

    st.divider()

    if not new_words:
        st.info("今天还没有新词，请先添加新词。")
    else:
        st.caption(f"今天共有 {len(new_words)} 个新词")

        learning_question_type = st.radio(
            "题型", ["中译英", "英译中"], horizontal=True, key="learning_question_type_radio"
        )

        if learning_question_type != st.session_state.learning_question_type:
            st.session_state.learning_question_type = learning_question_type
            st.session_state.learning_word_index = None
            st.session_state.learning_last_word_index = None
            st.session_state.learning_last_answer = ""
            st.session_state.learning_last_correct = None

        if (st.session_state.learning_word_index is None or 
            st.session_state.learning_word_index >= len(new_words)):
            selected_new = get_random_new_word(learning_question_type)
            if selected_new:
                st.session_state.learning_word_index = new_words.index(selected_new)

        learning_current_index = st.session_state.learning_word_index

        if learning_current_index is not None:
            learning_word = new_words[learning_current_index]
            learning_category = learning_word.get("category", "noun")

            left, right = st.columns([1, 1], gap="large")

            # 上一题
            with left:
                st.markdown("### 上一题")
                last_index = st.session_state.learning_last_word_index

                if last_index is None or last_index >= len(new_words):
                    st.caption("开始答题后显示上一题")
                else:
                    last_word = new_words[last_index]
                    last_cat = last_word.get("category", "noun")

                    if learning_question_type == "中译英":
                        st.markdown(f'<div class="previous-question">{html.escape(last_word["chinese"])}</div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="previous-category">{html.escape(last_cat)}</div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="answer-text">你的答案：<b>{html.escape(st.session_state.learning_last_answer)}</b></div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="answer-text">正确答案：<b>{html.escape(last_word["english"])}</b></div>', unsafe_allow_html=True)
                        pronunciation_button(last_word["english"], "learning_last_cn_en")
                    else:
                        st.markdown(f'<div class="previous-question">{html.escape(last_word["english"])}</div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="previous-category">{html.escape(last_cat)}</div>', unsafe_allow_html=True)
                        pronunciation_button(last_word["english"], "learning_last_en_cn")
                        st.markdown(f'<div class="answer-text">你的答案：<b>{html.escape(st.session_state.learning_last_answer)}</b></div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="answer-text">正确答案：<b>{html.escape(last_word["chinese"])}</b></div>', unsafe_allow_html=True)

                    st.markdown(render_word_attributes(last_word), unsafe_allow_html=True)
                    st.markdown(render_word_note(last_word, learning_question_type), unsafe_allow_html=True)

                    if st.session_state.learning_last_correct:
                        st.success("正确", icon="✅")
                    else:
                        st.error("错误", icon="❌")

            # 下一题
            with right:
                st.markdown("### 下一题")
                if learning_question_type == "中译英":
                    st.markdown(f'<div class="question">{html.escape(learning_word["chinese"])}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="question-category">{html.escape(learning_category)}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="question">{html.escape(learning_word["english"])}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="question-category">{html.escape(learning_category)}</div>', unsafe_allow_html=True)
                    pronunciation_button(learning_word["english"], "learning_current_sound")

                st.markdown(render_word_attributes(learning_word), unsafe_allow_html=True)
                st.markdown(render_word_note(learning_word, learning_question_type), unsafe_allow_html=True)

                with st.form(key="learning_answer_form", clear_on_submit=True):
                    learning_answer = st.text_input("答案", label_visibility="collapsed", placeholder="输入答案后按 Enter", autocomplete="off")
                    learning_submitted = st.form_submit_button("提交", use_container_width=True)

                if learning_submitted:
                    learning_answer = learning_answer.strip()
                    if not learning_answer:
                        st.warning("请输入答案后再提交。")
                        st.stop()

                    if learning_question_type == "中译英":
                        correct_ans = learning_word["english"].strip().lower()
                        user_ans = learning_answer.strip().lower()
                        weight_key = "cn_to_en_weight"
                    else:
                        correct_ans = learning_word["chinese"].strip()
                        user_ans = learning_answer.strip()
                        weight_key = "en_to_cn_weight"

                    is_correct = (user_ans == correct_ans)

                    # 独立调整权重
                    if is_correct:
                        learning_word[weight_key] = max(1, int(learning_word.get(weight_key, 3)) - 1)
                    else:
                        learning_word[weight_key] = min(20, int(learning_word.get(weight_key, 3)) + 2)

                    save_new_words()

                    st.session_state.learning_last_word_index = learning_current_index
                    st.session_state.learning_last_answer = learning_answer
                    st.session_state.learning_last_correct = is_correct

                    next_new = get_random_new_word(learning_question_type)
                    if next_new:
                        st.session_state.learning_word_index = new_words.index(next_new)

                    st.rerun()

    # 编辑新词列表
    st.divider()
    st.subheader("✏️ 编辑列表")

    if new_words:
        new_word_search = st.text_input("🔍 搜索新词", placeholder="输入英文或中文", key="new_word_edit_search")
        for index, word in enumerate(new_words):
            if new_word_search and (new_word_search.lower() not in word["english"].lower() and new_word_search not in word["chinese"]):
                continue
            with st.expander(f"{word['english']} → {word['chinese']} ({word.get('category', 'noun')})"):
                render_word_edit_form(word, index, prefix="new_edit", is_new_word=True)


# ============================================================
# 🎯 练习模式
# ============================================================

elif page == "🎯 练习模式":
    st.header("🎯 练习模式")

    if not words:
        st.warning("词库为空，请先到「词库管理」添加单词。")
    else:
        question_type = st.radio("题型", ["中译英", "英译中"], horizontal=True)

        if question_type != st.session_state.question_type:
            st.session_state.question_type = question_type
            st.session_state.current_word_index = None
            st.session_state.last_word_index = None
            st.session_state.last_answer = ""
            st.session_state.last_correct = None

        if (st.session_state.current_word_index is None or 
            st.session_state.current_word_index >= len(words)):
            selected_word = get_random_word(question_type)
            if selected_word:
                st.session_state.current_word_index = words.index(selected_word)

        current_index = st.session_state.current_word_index
        word = words[current_index]
        current_category = word.get("category", "noun")

        left, right = st.columns([1, 1], gap="large")

        # 上一题
        with left:
            st.markdown("### 上一题")
            last_index = st.session_state.last_word_index

            if last_index is None or last_index >= len(words):
                st.caption("开始答题后显示上一题")
            else:
                last_word = words[last_index]
                last_cat = last_word.get("category", "noun")

                if question_type == "中译英":
                    st.markdown(f'<div class="previous-question">{html.escape(last_word["chinese"])}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="previous-category">{html.escape(last_cat)}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="answer-text">你的答案：<b>{html.escape(st.session_state.last_answer)}</b></div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="answer-text">正确答案：<b>{html.escape(last_word["english"])}</b></div>', unsafe_allow_html=True)
                    pronunciation_button(last_word["english"], "last_cn_en")
                else:
                    st.markdown(f'<div class="previous-question">{html.escape(last_word["english"])}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="previous-category">{html.escape(last_cat)}</div>', unsafe_allow_html=True)
                    pronunciation_button(last_word["english"], "last_en_cn")
                    st.markdown(f'<div class="answer-text">你的答案：<b>{html.escape(st.session_state.last_answer)}</b></div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="answer-text">正确答案：<b>{html.escape(last_word["chinese"])}</b></div>', unsafe_allow_html=True)

                st.markdown(render_word_attributes(last_word), unsafe_allow_html=True)
                st.markdown(render_word_note(last_word, question_type), unsafe_allow_html=True)

                if st.session_state.last_correct:
                    st.success("正确", icon="✅")
                else:
                    st.error("错误", icon="❌")
                    if st.button("我的答案也是近义词 ✓", key="similar_answer", use_container_width=True):
                        if question_type == "中译英":
                            last_word["cn_to_en_wrong"] = max(0, int(last_word.get("cn_to_en_wrong", 0)) - 1)
                            last_word["cn_to_en_correct"] = int(last_word.get("cn_to_en_correct", 0)) + 1
                            last_word["cn_to_en_weight"] = max(1, int(last_word.get("cn_to_en_weight", 3)) - 2)
                            daily_stats["cn_to_en_correct"] += 1
                        else:
                            last_word["en_to_cn_wrong"] = max(0, int(last_word.get("en_to_cn_wrong", 0)) - 1)
                            last_word["en_to_cn_correct"] = int(last_word.get("en_to_cn_correct", 0)) + 1
                            last_word["en_to_cn_weight"] = max(1, int(last_word.get("en_to_cn_weight", 3)) - 2)
                            daily_stats["en_to_cn_correct"] += 1

                        save_words()
                        save_daily_stats()
                        st.session_state.last_correct = True
                        st.rerun()

        # 下一题
        with right:
            st.markdown("### 下一题")
            if question_type == "中译英":
                st.markdown(f'<div class="question">{html.escape(word["chinese"])}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="question-category">{html.escape(current_category)}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="question">{html.escape(word["english"])}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="question-category">{html.escape(current_category)}</div>', unsafe_allow_html=True)
                pronunciation_button(word["english"], "current_sound")

            st.markdown(render_word_attributes(word), unsafe_allow_html=True)
            st.markdown(render_word_note(word, question_type), unsafe_allow_html=True)

            with st.form(key="answer_form", clear_on_submit=True):
                answer = st.text_input("答案", label_visibility="collapsed", placeholder="输入答案后按 Enter", autocomplete="off")
                submitted = st.form_submit_button("提交", use_container_width=True)

            if submitted:
                answer = answer.strip()
                if not answer:
                    st.warning("请输入答案后再提交。")
                    st.stop()

                if question_type == "中译英":
                    correct_ans = word["english"].strip().lower()
                    user_ans = answer.strip().lower()
                    corr_key, wrong_key, weight_key = "cn_to_en_correct", "cn_to_en_wrong", "cn_to_en_weight"
                    stat_ans_key, stat_corr_key = "cn_to_en_answered", "cn_to_en_correct"
                else:
                    correct_ans = word["chinese"].strip()
                    user_ans = answer.strip()
                    corr_key, wrong_key, weight_key = "en_to_cn_correct", "en_to_cn_wrong", "en_to_cn_weight"
                    stat_ans_key, stat_corr_key = "en_to_cn_answered", "en_to_cn_correct"

                is_correct = (user_ans == correct_ans)

                if is_correct:
                    word[corr_key] = int(word.get(corr_key, 0)) + 1
                    word[weight_key] = max(1, int(word.get(weight_key, 3)) - 1)
                else:
                    word[wrong_key] = int(word.get(wrong_key, 0)) + 1
                    word[weight_key] = min(20, int(word.get(weight_key, 3)) + 2)

                save_words()

                daily_stats[stat_ans_key] = int(daily_stats.get(stat_ans_key, 0)) + 1
                if is_correct:
                    daily_stats[stat_corr_key] = int(daily_stats.get(stat_corr_key, 0)) + 1
                save_daily_stats()

                st.session_state.last_word_index = current_index
                st.session_state.last_answer = answer
                st.session_state.last_correct = is_correct

                next_word = get_random_word(question_type)
                if next_word:
                    st.session_state.current_word_index = words.index(next_word)

                st.rerun()

        # 今日统计
        st.divider()
        cn_ans = int(daily_stats.get("cn_to_en_answered", 0))
        cn_cor = int(daily_stats.get("cn_to_en_correct", 0))
        en_ans = int(daily_stats.get("en_to_cn_answered", 0))
        en_cor = int(daily_stats.get("en_to_cn_correct", 0))
        tot_ans, tot_cor = cn_ans + en_ans, cn_cor + en_cor

        st.subheader("📊 今日统计")
        c1, c2, c3 = st.columns(3)
        c1.metric("今日总答数", tot_ans)
        c2.metric("中译英", f"{cn_cor} / {cn_ans}")
        c3.metric("英译中", f"{en_cor} / {en_ans}")
        if tot_ans > 0:
            st.caption(f"今日总正确率：{(tot_cor / tot_ans * 100):.1f}%")


# ============================================================
# 📚 词库管理
# ============================================================

elif page == "📚 词库管理":
    st.header("📚 词库管理")

    st.subheader("➕ 添加单词 (表格形式，支持从 Excel 直接复制粘贴)")
    st.caption("提示：在 Excel 中选中各列数据后按 Ctrl+C 复制，点击下方表格首行按 Ctrl+V 粘贴。")

    df_template_vocab = pd.DataFrame([
        {"英文": "", "中文": "", "词性": "noun", "中文备注": "", "英文备注": ""}
    ])

    edited_vocab_df = st.data_editor(
        df_template_vocab,
        num_rows="dynamic",
        column_config={
            "英文": st.column_config.TextColumn("英文", required=True),
            "中文": st.column_config.TextColumn("中文", required=True),
            "词性": st.column_config.SelectboxColumn("词性", options=CATEGORIES, required=True),
            "中文备注": st.column_config.TextColumn("中文备注 (可选)"),
            "英文备注": st.column_config.TextColumn("英文备注 (可选)"),
        },
        use_container_width=True,
        key="vocab_table_input"
    )

    if st.button("➕ 确认添加单词到词库", use_container_width=True):
        added, duplicate = 0, 0
        for _, row in edited_vocab_df.iterrows():
            en = str(row.get("英文", "")).strip()
            cn = str(row.get("中文", "")).strip()
            cat = str(row.get("词性", "noun")).strip()
            cn_note = str(row.get("中文备注", "")).strip()
            en_note = str(row.get("英文备注", "")).strip()

            if not en or not cn:
                continue

            exists = any(
                item["english"].lower() == en.lower() and 
                item["chinese"] == cn and 
                item.get("category") == cat
                for item in words
            )

            if exists:
                duplicate += 1
            else:
                words.append({
                    "english": en,
                    "chinese": cn,
                    "category": cat if cat in CATEGORIES else "noun",
                    "cn_to_en_weight": 3,
                    "en_to_cn_weight": 3,
                    "cn_to_en_correct": 0,
                    "cn_to_en_wrong": 0,
                    "en_to_cn_correct": 0,
                    "en_to_cn_wrong": 0,
                    "is_countable": True,
                    "plural": "",
                    "third_person": "",
                    "past_tense": "",
                    "past_participle": "",
                    "comparative": "",
                    "superlative": "",
                    "cn_note": cn_note,
                    "en_note": en_note
                })
                added += 1

        if added > 0:
            if save_words():
                st.success(f"成功添加 {added} 个单词，并已同步到 GitHub！")
                st.rerun()
        if duplicate > 0:
            st.info(f"{duplicate} 个完全相同的单词没有重复添加。")

    st.divider()
    st.subheader("✏️ 编辑词库")

    search = st.text_input("🔍 搜索", placeholder="输入英文或中文", key="vocabulary_edit_search")

    for index, word in enumerate(words):
        if search and (search.lower() not in word["english"].lower() and search not in word["chinese"]):
            continue

        with st.expander(f"{word['english']} → {word['chinese']} ({word.get('category', 'noun')})"):
            render_word_edit_form(word, index, prefix="vocab_edit", is_new_word=False)


# ============================================================
# 📖 查看词库
# ============================================================

elif page == "📖 查看词库":
    st.header("📖 我的词库")

    if not words:
        st.info("目前没有单词。")
    else:
        search = st.text_input("🔍 搜索词库", placeholder="输入英文或中文", key="view_vocab_search")
        category_filter = st.selectbox("词性筛选", ["全部"] + CATEGORIES, key="view_category_filter")

        filtered_words = []
        for word in words:
            if search and (search.lower() not in word["english"].lower() and search not in word["chinese"]):
                continue
            if category_filter != "全部" and word.get("category", "noun") != category_filter:
                continue
            filtered_words.append(word)

        st.caption(f"找到 {len(filtered_words)} 个单词")

        # 排序处理
        sort_field = st.session_state.vocab_sort_field
        reverse = st.session_state.vocab_sort_reverse

        if sort_field == "english":
            filtered_words.sort(key=lambda x: x.get("english", "").lower(), reverse=reverse)
        elif sort_field == "chinese":
            filtered_words.sort(key=lambda x: x.get("chinese", ""), reverse=reverse)
        elif sort_field == "category":
            filtered_words.sort(key=lambda x: x.get("category", ""), reverse=reverse)
        elif sort_field == "cn_prob":
            filtered_words.sort(key=lambda x: calculate_probability(x, "中译英"), reverse=reverse)
        elif sort_field == "en_prob":
            filtered_words.sort(key=lambda x: calculate_probability(x, "英译中"), reverse=reverse)

        st.markdown('<div class="mobile-hint">📱 手机可以左右滑动查看完整词库；点击表头按钮排序</div>', unsafe_allow_html=True)

        cols = st.columns([2, 2, 1.2, 1.2, 1.2, 1, 1])

        def sort_label(field, text):
            if st.session_state.vocab_sort_field != field:
                return text
            return text + (" ↓" if st.session_state.vocab_sort_reverse else " ↑")

        with cols[0]:
            if st.button(sort_label("english", "英文"), key="sort_english", use_container_width=True):
                set_sort("english"); st.rerun()
        with cols[1]:
            if st.button(sort_label("chinese", "中文"), key="sort_chinese", use_container_width=True):
                set_sort("chinese"); st.rerun()
        with cols[2]:
            if st.button(sort_label("category", "词性"), key="sort_category", use_container_width=True):
                set_sort("category"); st.rerun()
        with cols[3]:
            if st.button(sort_label("cn_prob", "中译英概率"), key="sort_cn_prob", use_container_width=True):
                set_sort("cn_prob"); st.rerun()
        with cols[4]:
            if st.button(sort_label("en_prob", "英译中概率"), key="sort_en_prob", use_container_width=True):
                set_sort("en_prob"); st.rerun()

        rows = ""
        for word in filtered_words:
            english = html.escape(str(word.get("english", "")))
            chinese = html.escape(str(word.get("chinese", "")))
            category = html.escape(str(word.get("category", "noun")))
            cn_prob = calculate_probability(word, "中译英")
            en_prob = calculate_probability(word, "英译中")
            cn_stat = f"✓{word.get('cn_to_en_correct', 0)} / ✗{word.get('cn_to_en_wrong', 0)}"
            en_stat = f"✓{word.get('en_to_cn_correct', 0)} / ✗{word.get('en_to_cn_wrong', 0)}"

            rows += f"""
            <tr>
                <td class="english">{english}</td>
                <td>{chinese}</td>
                <td>{category}</td>
                <td class="probability">{cn_prob:.2f}% (w:{word.get('cn_to_en_weight', 3)})</td>
                <td class="probability">{en_prob:.2f}% (w:{word.get('en_to_cn_weight', 3)})</td>
                <td>{cn_stat}</td>
                <td>{en_stat}</td>
            </tr>
            """

        table_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
        * {{ box-sizing: border-box; }}
        html, body {{ margin: 0; padding: 0; width: 100%; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif; font-size: 14px; background-color: #ffffff; color: #1f1f1f; }}
        .table-wrapper {{ width: 100%; overflow-x: auto; border: 1px solid #d9d9d9; border-radius: 10px; background-color: #ffffff; }}
        table {{ width: 100%; min-width: 780px; border-collapse: collapse; background-color: #ffffff; color: #1f1f1f; }}
        th {{ padding: 10px 8px; text-align: left; font-weight: 700; background-color: #f3f4f6; border-bottom: 2px solid #cfcfcf; white-space: nowrap; }}
        td {{ padding: 9px 8px; background-color: #ffffff; border-bottom: 1px solid #e5e5e5; white-space: nowrap; }}
        tbody tr:hover td {{ background-color: #f5f5f5; }}
        .english {{ font-weight: 600; color: #111111; }}
        .probability {{ font-size: 13px; color: #444444; }}
        @media (prefers-color-scheme: dark) {{
            body, .table-wrapper, table {{ background-color: #0e1117; color: #f1f1f1; }}
            .table-wrapper {{ border-color: #3a3f47; }}
            th {{ color: #ffffff; background-color: #262b33; border-bottom-color: #4a5059; }}
            td {{ color: #f1f1f1; background-color: #0e1117; border-bottom-color: #30353d; }}
            tbody tr:hover td {{ background-color: #1c2128; }}
            .english {{ color: #ffffff; }}
            .probability {{ color: #d0d0d0; }}
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
                    <th>中译英概率</th>
                    <th>英译中概率</th>
                    <th>中译英战绩</th>
                    <th>英译中战绩</th>
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
            height=max(120, min(800, 65 + len(filtered_words) * 44)),
            scrolling=True
        )
