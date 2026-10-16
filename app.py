
import base64
import html
import json
import random
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st


st.set_page_config(
    page_title="English Vocabulary",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

GITHUB_OWNER = "ojoj0307"
GITHUB_REPO = "english-vocabulary"

VOCABULARY_PATH = "vocabulary.json"
NEW_WORDS_PATH = "new_words.json"
DAILY_STATS_PATH = "daily_stats.json"

MALAYSIA_TZ = ZoneInfo("Asia/Kuala_Lumpur")
CATEGORIES = ["noun", "verb", "adjective", "adverb"]
PRIORITY_BY_STREAK = [12, 11, 9, 6, 2, 0]

try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
except Exception:
    GITHUB_TOKEN = ""

GITHUB_API_BASE = (
    f"https://api.github.com/repos/"
    f"{GITHUB_OWNER}/{GITHUB_REPO}/contents/"
)

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

    @media (max-width: 700px) {
        .block-container {
            padding-top: 2.5rem;
            padding-left: 0.7rem;
            padding-right: 0.7rem;
        }

        .question {
            font-size: 25px;
        }

        .previous-question {
            font-size: 21px;
        }

        section[data-testid="stSidebar"] div[role="radiogroup"] label {
            font-size: 18px !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def get_today():
    return datetime.now(MALAYSIA_TZ).strftime("%Y-%m-%d")


def github_headers():
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def check_github_token():
    if not GITHUB_TOKEN:
        st.error("没有找到 GITHUB_TOKEN。")
        st.info("请在 Streamlit Cloud → Settings → Secrets 添加 GITHUB_TOKEN。")
        return False
    return True


def github_get_file(path):
    if not check_github_token():
        return None, None

    try:
        response = requests.get(
            GITHUB_API_BASE + path,
            headers=github_headers(),
            timeout=15,
        )

        if response.status_code == 404:
            return None, None

        if response.status_code != 200:
            st.error(f"GitHub API 错误：{response.status_code} {response.text}")
            return None, None

        result = response.json()
        content = result.get("content", "").replace("\n", "")
        return base64.b64decode(content).decode("utf-8"), result.get("sha")

    except Exception as error:
        st.error(f"无法连接 GitHub：{error}")
        return None, None


def github_save_file(path, data, sha=None, message="Update file"):
    if not check_github_token():
        return False

    try:
        content = json.dumps(data, ensure_ascii=False, indent=4)
        payload = {
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
        }

        if sha:
            payload["sha"] = sha

        response = requests.put(
            GITHUB_API_BASE + path,
            headers=github_headers(),
            json=payload,
            timeout=15,
        )

        if response.status_code in (200, 201):
            return True

        st.error(f"GitHub API 错误：{response.status_code} {response.text}")
        return False

    except Exception as error:
        st.error(f"保存到 GitHub 失败：{error}")
        return False


def direction_keys(question_type):
    if question_type == "中译英":
        return {
            "weight": "cn_to_en_weight",
            "not_seen": "cn_to_en_not_seen",
            "correct": "cn_to_en_correct",
            "wrong": "cn_to_en_wrong",
            "round_done": "cn_to_en_round_done",
        }

    return {
        "weight": "en_to_cn_weight",
        "not_seen": "en_to_cn_not_seen",
        "correct": "en_to_cn_correct",
        "wrong": "en_to_cn_wrong",
        "round_done": "en_to_cn_round_done",
    }


def normalize_word(word):
    changed = False

    defaults = {
        "id": str(uuid.uuid4()),
        "english": "",
        "chinese": "",
        "category": "noun",
        "cn_note": "",
        "en_note": "",
        "cn_to_en_weight": 3,
        "en_to_cn_weight": 3,
        "cn_to_en_not_seen": 0,
        "en_to_cn_not_seen": 0,
        "cn_to_en_correct": 0,
        "cn_to_en_wrong": 0,
        "en_to_cn_correct": 0,
        "en_to_cn_wrong": 0,
        "cn_to_en_round_done": False,
        "en_to_cn_round_done": False,
        "is_proficient": False,
        "review_priority": 12,
        "review_correct_streak": 0,
        "review_wrong_streak": 0,
    }

    for key, value in defaults.items():
        if key not in word:
            word[key] = value
            changed = True

    if word.get("category") not in CATEGORIES:
        word["category"] = "noun"
        changed = True

    for key in (
        "cn_to_en_weight",
        "en_to_cn_weight",
        "cn_to_en_not_seen",
        "en_to_cn_not_seen",
        "cn_to_en_correct",
        "cn_to_en_wrong",
        "en_to_cn_correct",
        "en_to_cn_wrong",
        "review_priority",
        "review_correct_streak",
        "review_wrong_streak",
    ):
        try:
            word[key] = int(word.get(key, defaults[key]))
        except (TypeError, ValueError):
            word[key] = defaults[key]
            changed = True

    word["is_proficient"] = bool(word.get("is_proficient", False))
    word["cn_to_en_round_done"] = bool(word.get("cn_to_en_round_done", False))
    word["en_to_cn_round_done"] = bool(word.get("en_to_cn_round_done", False))

    return changed


def load_words():
    content, sha = github_get_file(VOCABULARY_PATH)

    if content is None:
        return [], None

    try:
        data = json.loads(content)
    except Exception:
        st.error("vocabulary.json 格式错误。")
        return [], sha

    if not isinstance(data, list):
        st.error("vocabulary.json 必须是数组。")
        return [], sha

    changed = False
    for item in data:
        if normalize_word(item):
            changed = True

    if changed:
        github_save_file(
            VOCABULARY_PATH,
            data,
            sha,
            "Upgrade vocabulary review fields",
        )
        _, sha = github_get_file(VOCABULARY_PATH)

    return data, sha


def default_new_words():
    return {"date": get_today(), "words": []}


def load_new_words():
    content, sha = github_get_file(NEW_WORDS_PATH)

    if content is None:
        data = default_new_words()
        github_save_file(NEW_WORDS_PATH, data, None, "Create new words")
        _, sha = github_get_file(NEW_WORDS_PATH)
        return data, sha

    try:
        data = json.loads(content)
    except Exception:
        data = default_new_words()

    if isinstance(data, list):
        data = {"date": get_today(), "words": data}

    if not isinstance(data, dict):
        data = default_new_words()

    if data.get("date") != get_today():
        data = default_new_words()

    if not isinstance(data.get("words"), list):
        data["words"] = []

    changed = False
    for item in data["words"]:
        if normalize_word(item):
            changed = True

    if changed:
        github_save_file(NEW_WORDS_PATH, data, sha, "Upgrade new words fields")
        _, sha = github_get_file(NEW_WORDS_PATH)

    return data, sha


words, vocabulary_sha = load_words()
new_words_data, new_words_sha = load_new_words()
new_words = new_words_data["words"]


def save_words():
    global vocabulary_sha
    _, latest_sha = github_get_file(VOCABULARY_PATH)

    if latest_sha is None:
        return False

    success = github_save_file(
        VOCABULARY_PATH,
        words,
        latest_sha,
        "Update vocabulary",
    )

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

    success = github_save_file(
        NEW_WORDS_PATH,
        new_words_data,
        latest_sha,
        "Update daily new words",
    )

    if success:
        _, new_words_sha = github_get_file(NEW_WORDS_PATH)

    return success


def calculate_sampling_weight(word, question_type):
    keys = direction_keys(question_type)

    try:
        base_weight = max(1, int(word.get(keys["weight"], 3)))
    except (TypeError, ValueError):
        base_weight = 3

    try:
        not_seen = max(0, int(word.get(keys["not_seen"], 0)))
    except (TypeError, ValueError):
        not_seen = 0

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


def probability(word, pool, question_type):
    total = sum(calculate_sampling_weight(item, question_type) for item in pool)

    if total <= 0:
        return 0

    return calculate_sampling_weight(word, question_type) / total * 100


def weighted_pick(pool, question_type):
    if not pool:
        return None

    selected = random.choices(
        pool,
        weights=[calculate_sampling_weight(item, question_type) for item in pool],
        k=1,
    )[0]

    not_seen_key = direction_keys(question_type)["not_seen"]

    for item in pool:
        if item is selected:
            item[not_seen_key] = 0
        else:
            item[not_seen_key] = int(item.get(not_seen_key, 0)) + 1

    return selected


def get_random_new_word(question_type):
    """
    新词：答对的词在本轮中不再出现。
    当全部新词都答对后，自动重置为下一轮。
    中译英和英译中各自独立记录。
    """
    if not new_words:
        return None

    done_key = direction_keys(question_type)["round_done"]
    candidates = [item for item in new_words if not item.get(done_key, False)]

    if not candidates:
        for item in new_words:
            item[done_key] = False
        candidates = list(new_words)

    return weighted_pick(candidates, question_type)


def get_normal_review_word():
    normal_words = [
        item for item in words
        if not item.get("is_proficient", False)
    ]

    if not normal_words:
        return None

    priorities = [
        max(1, int(item.get("review_priority", 12)))
        for item in normal_words
    ]

    return random.choices(normal_words, weights=priorities, k=1)[0]


def get_proficient_review_word(question_type):
    proficient_words = [
        item for item in words
        if item.get("is_proficient", False)
    ]

    return weighted_pick(proficient_words, question_type)


def adjust_probability(word, question_type, correct):
    weight_key = direction_keys(question_type)["weight"]
    current = int(word.get(weight_key, 3))

    if correct:
        word[weight_key] = max(1, current - 1)
    else:
        word[weight_key] = min(20, current + 2)


def record_new_word_result(word, question_type, correct):
    keys = direction_keys(question_type)

    adjust_probability(word, question_type, correct)

    if correct:
        word[keys["correct"]] = int(word.get(keys["correct"], 0)) + 1
        word[keys["round_done"]] = True
    else:
        word[keys["wrong"]] = int(word.get(keys["wrong"], 0)) + 1


def record_normal_review_result(word, correct):
    """
    普通复习规则：
    初始 12
    连续答对：12 → 11 → 9 → 6 → 2 → 0
    第五次连续答对自动转为熟练。
    连续答错时，优先级分别额外增加 +2、+4、+6……
    """
    if correct:
        streak = int(word.get("review_correct_streak", 0)) + 1
        word["review_correct_streak"] = streak
        word["review_wrong_streak"] = 0

        if streak >= 5:
            word["review_priority"] = 0
            word["is_proficient"] = True
        else:
            word["review_priority"] = PRIORITY_BY_STREAK[streak]

    else:
        wrong_streak = int(word.get("review_wrong_streak", 0)) + 1
        current_priority = int(word.get("review_priority", 12))

        word["review_correct_streak"] = 0
        word["review_wrong_streak"] = wrong_streak
        word["review_priority"] = min(
            50,
            current_priority + wrong_streak * 2,
        )


def pronunciation_button(text, key):
    encoded = base64.b64encode(str(text).encode("utf-8")).decode("ascii")

    st.components.v1.html(
        f"""
        <button
            style="
                border:none;
                background:transparent;
                cursor:pointer;
                font-size:21px;
                padding:2px 6px;
            "
            onclick="
                const text = decodeURIComponent(escape(atob('{encoded}')));
                window.speechSynthesis.cancel();
                const speech = new SpeechSynthesisUtterance(text);
                speech.lang = 'en-GB';
                speech.rate = 0.85;
                window.speechSynthesis.speak(speech);
            "
            title="British English"
        >🔊</button>
        """,
        height=35,
        width=50,
        scrolling=False,
        key=key,
    )


def answer_is_correct(word, question_type, answer):
    if question_type == "中译英":
        return answer.strip().lower() == word["english"].strip().lower()

    return answer.strip() == word["chinese"].strip()


def render_quiz(title, session_prefix, picker, result_handler, saver):
    question_type_key = f"{session_prefix}_question_type"
    current_key = f"{session_prefix}_current"
    last_key = f"{session_prefix}_last"

    if question_type_key not in st.session_state:
        st.session_state[question_type_key] = "中译英"

    question_type = st.radio(
        "题型",
        ["中译英", "英译中"],
        horizontal=True,
        key=f"{session_prefix}_question_type_radio",
    )

    if question_type != st.session_state[question_type_key]:
        st.session_state[question_type_key] = question_type
        st.session_state[current_key] = None
        st.session_state[last_key] = None

    current_word = st.session_state.get(current_key)

    if current_word is None:
        current_word = picker(question_type)
        st.session_state[current_key] = current_word

    if current_word is None:
        st.info("目前没有可复习的单词。")
        return

    left, right = st.columns([1, 1], gap="large")

    with left:
        st.markdown("### 上一题")
        last = st.session_state.get(last_key)

        if not last:
            st.caption("开始答题后显示上一题。")
        else:
            previous_word = last["word"]
            st.markdown(
                f"""
                <div class="previous-question">
                    {html.escape(last["question"])}
                </div>
                <div class="answer-text">
                    你的答案：<b>{html.escape(last["answer"])}</b>
                </div>
                <div class="answer-text">
                    正确答案：<b>{html.escape(last["correct_answer"])}</b>
                </div>
                """,
                unsafe_allow_html=True,
            )

            pronunciation_button(
                previous_word["english"],
                f"{session_prefix}_last_audio_{previous_word['id']}",
            )

            if last["correct"]:
                st.success("正确", icon="✅")
            else:
                st.error("错误", icon="❌")

    with right:
        st.markdown(f"### {title}")

        if question_type == "中译英":
            question = current_word["chinese"]
            correct_answer = current_word["english"]
            note = current_word.get("cn_note", "")
        else:
            question = current_word["english"]
            correct_answer = current_word["chinese"]
            note = current_word.get("en_note", "")

        note_html = (
            f"<br><small style='opacity:.8;'>📝 备注：{html.escape(note)}</small>"
            if note
            else ""
        )

        st.markdown(
            f"""
            <div class="question">{html.escape(question)}{note_html}</div>
            <div class="question-category">
                {html.escape(current_word.get("category", "noun"))}
            </div>
            """,
            unsafe_allow_html=True,
        )

        pronunciation_button(
            current_word["english"],
            f"{session_prefix}_current_audio_{current_word['id']}",
        )

        with st.form(f"{session_prefix}_answer_form", clear_on_submit=True):
            answer = st.text_input(
                "答案",
                label_visibility="collapsed",
                placeholder="输入答案后按 Enter",
                autocomplete="off",
            )
            submitted = st.form_submit_button("提交", use_container_width=True)

        if submitted:
            answer = answer.strip()

            if not answer:
                st.warning("请输入答案后再提交。")
                st.stop()

            correct = answer_is_correct(current_word, question_type, answer)
            result_handler(current_word, question_type, correct)

            st.session_state[last_key] = {
                "word": current_word,
                "question": question,
                "answer": answer,
                "correct_answer": correct_answer,
                "correct": correct,
            }

            st.session_state[current_key] = picker(question_type)

            if not saver():
                st.error("保存失败，请检查 GitHub Token 权限。")

            st.rerun()


st.title("📚 English Vocabulary")

with st.sidebar:
    page = st.radio(
        "功能",
        [
            "🎓 学习模式",
            "🎯 练习模式",
            "📚 词库管理",
            "📖 查看词库",
        ],
    )


if page == "🎓 学习模式":
    st.header("🎓 学习模式")
    st.subheader("➕ 添加新词")

    initial_df = pd.DataFrame(
        [{
            "english": "",
            "chinese": "",
            "category": "noun",
            "cn_note": "",
            "en_note": "",
        }]
    )

    edited_df = st.data_editor(
        initial_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "english": st.column_config.TextColumn("英文", required=True),
            "chinese": st.column_config.TextColumn("中文", required=True),
            "category": st.column_config.SelectboxColumn(
                "词性",
                options=CATEGORIES,
                default="noun",
                required=True,
            ),
            "cn_note": st.column_config.TextColumn("中文备注"),
            "en_note": st.column_config.TextColumn("英文备注"),
        },
        key="learning_batch_editor",
    )

    if st.button("➕ 批量添加新词", use_container_width=True):
        added = 0

        for _, row in edited_df.iterrows():
            english = str(row.get("english") or "").strip()
            chinese = str(row.get("chinese") or "").strip()

            if not english or not chinese:
                continue

            category = str(row.get("category") or "noun").strip()
            if category not in CATEGORIES:
                category = "noun"

            exists = any(
                item["english"].strip().lower() == english.lower()
                and item["chinese"].strip() == chinese
                and item.get("category") == category
                for item in new_words
            )

            if exists:
                continue

            word = {
                "id": str(uuid.uuid4()),
                "english": english,
                "chinese": chinese,
                "category": category,
                "cn_note": "" if pd.isna(row.get("cn_note")) else str(row.get("cn_note")).strip(),
                "en_note": "" if pd.isna(row.get("en_note")) else str(row.get("en_note")).strip(),
            }
            normalize_word(word)
            new_words.append(word)

            if not any(
                item["english"].strip().lower() == english.lower()
                and item["chinese"].strip() == chinese
                and item.get("category") == category
                for item in words
            ):
                words.append(word.copy())

            added += 1

        if added:
            if save_new_words() and save_words():
                st.success(f"成功添加 {added} 个新词，并同步到正式词库。")
                st.rerun()
        else:
            st.warning("没有可添加的新词。")

    st.divider()

    if not new_words:
        st.info("今天还没有新词，请先添加新词。")
    else:
        st.caption(f"今天共有 {len(new_words)} 个新词")
        st.caption("答对一个词后，该词本轮不再出现；全部答对后自动开始下一轮。")

        render_quiz(
            "下一题",
            "learning",
            get_random_new_word,
            record_new_word_result,
            save_new_words,
        )

    st.divider()
    st.subheader("✏️ 编辑列表")

    for index, word in enumerate(new_words):
        with st.expander(
            f"{word['english']} → {word['chinese']} "
            f"({word.get('category', 'noun')})"
        ):
            pronunciation_button(
                word["english"],
                f"new_word_list_audio_{word['id']}",
            )

            col1, col2 = st.columns(2)

            with col1:
                english = st.text_input(
                    "英文",
                    value=word["english"],
                    key=f"new_english_{word['id']}",
                )

            with col2:
                chinese = st.text_input(
                    "中文",
                    value=word["chinese"],
                    key=f"new_chinese_{word['id']}",
                )

            category = st.selectbox(
                "词性",
                CATEGORIES,
                index=CATEGORIES.index(word.get("category", "noun")),
                key=f"new_category_{word['id']}",
            )

            cn_note = st.text_input(
                "中文备注",
                value=word.get("cn_note", ""),
                key=f"new_cn_note_{word['id']}",
            )

            en_note = st.text_input(
                "英文备注",
                value=word.get("en_note", ""),
                key=f"new_en_note_{word['id']}",
            )

            st.caption(
                f"中译英概率：{probability(word, new_words, '中译英'):.2f}% "
                f"| 本轮完成：{'是' if word['cn_to_en_round_done'] else '否'}"
            )
            st.caption(
                f"英译中概率：{probability(word, new_words, '英译中'):.2f}% "
                f"| 本轮完成：{'是' if word['en_to_cn_round_done'] else '否'}"
            )

            save_col, delete_col = st.columns(2)

            with save_col:
                if st.button("💾 保存", key=f"new_save_{word['id']}", use_container_width=True):
                    word["english"] = english.strip()
                    word["chinese"] = chinese.strip()
                    word["category"] = category
                    word["cn_note"] = cn_note.strip()
                    word["en_note"] = en_note.strip()

                    for vocabulary_word in words:
                        if vocabulary_word["id"] == word["id"]:
                            vocabulary_word.update(word)
                            break

                    if save_new_words() and save_words():
                        st.success("修改成功。")
                        st.rerun()

            with delete_col:
                if st.button("🗑️ 删除", key=f"new_delete_{word['id']}", use_container_width=True):
                    new_words.pop(index)

                    if save_new_words():
                        st.success("已从今天的新词列表删除。")
                        st.rerun()


elif page == "🎯 练习模式":
    st.header("🎯 练习模式")

    normal_tab, proficient_tab = st.tabs(["普通", "熟练"])

    with normal_tab:
        normal_count = sum(
            not item.get("is_proficient", False)
            for item in words
        )

        st.caption(
            f"普通词：{normal_count} 个。"
            "连续答对会降低优先级，第 5 次连续答对后自动进入熟练。"
        )

        def normal_result_handler(word, question_type, correct):
            record_normal_review_result(word, correct)

            keys = direction_keys(question_type)
            if correct:
                word[keys["correct"]] += 1
            else:
                word[keys["wrong"]] += 1

        render_quiz(
            "下一题",
            "normal_review",
            lambda _question_type: get_normal_review_word(),
            normal_result_handler,
            save_words,
        )

    with proficient_tab:
        proficient_count = sum(
            item.get("is_proficient", False)
            for item in words
        )

        st.caption(
            f"熟练词：{proficient_count} 个。"
            "熟练词使用原有概率系统抽取。"
        )

        def proficient_result_handler(word, question_type, correct):
            adjust_probability(word, question_type, correct)

            keys = direction_keys(question_type)
            if correct:
                word[keys["correct"]] += 1
            else:
                word[keys["wrong"]] += 1

        render_quiz(
            "下一题",
            "proficient_review",
            get_proficient_review_word,
            proficient_result_handler,
            save_words,
        )


elif page == "📚 词库管理":
    st.header("📚 词库管理")

    if not words:
        st.info("词库为空。")
    else:
        st.caption("可直接勾选「熟练」；取消勾选会回到普通复习。")

        display_rows = []

        for word in words:
            display_rows.append({
                "id": word["id"],
                "english": word["english"],
                "chinese": word["chinese"],
                "category": word.get("category", "noun"),
                "cn_note": word.get("cn_note", ""),
                "en_note": word.get("en_note", ""),
                "熟练": word.get("is_proficient", False),
                "普通优先级": word.get("review_priority", 12),
                "连续答对": word.get("review_correct_streak", 0),
                "连续答错": word.get("review_wrong_streak", 0),
            })

        editor = st.data_editor(
            pd.DataFrame(display_rows),
            use_container_width=True,
            hide_index=True,
            column_config={
                "id": None,
                "category": st.column_config.SelectboxColumn(
                    "词性",
                    options=CATEGORIES,
                ),
                "熟练": st.column_config.CheckboxColumn("熟练"),
                "普通优先级": st.column_config.NumberColumn(
                    "普通优先级",
                    disabled=True,
                ),
                "连续答对": st.column_config.NumberColumn(
                    "连续答对",
                    disabled=True,
                ),
                "连续答错": st.column_config.NumberColumn(
                    "连续答错",
                    disabled=True,
                ),
            },
            key="vocabulary_editor",
        )

        if st.button("💾 保存词库修改", use_container_width=True):
            edited_rows = editor.to_dict("records")
            lookup = {item["id"]: item for item in words}

            for row in edited_rows:
                word = lookup.get(row["id"])

                if not word:
                    continue

                was_proficient = word.get("is_proficient", False)

                word["english"] = str(row["english"]).strip()
                word["chinese"] = str(row["chinese"]).strip()
                word["category"] = row["category"]
                word["cn_note"] = str(row.get("cn_note") or "").strip()
                word["en_note"] = str(row.get("en_note") or "").strip()
                word["is_proficient"] = bool(row["熟练"])

                if was_proficient and not word["is_proficient"]:
                    word["review_priority"] = 12
                    word["review_correct_streak"] = 0
                    word["review_wrong_streak"] = 0

            if save_words():
                st.success("词库已保存。")
                st.rerun()


elif page == "📖 查看词库":
    st.header("📖 查看词库")

    search = st.text_input("🔍 搜索", placeholder="输入英文或中文")

    filtered = words

    if search:
        search_lower = search.lower()
        filtered = [
            item for item in words
            if search_lower in item["english"].lower()
            or search in item["chinese"]
        ]

    if not filtered:
        st.info("没有符合条件的单词。")
    else:
        for word in filtered:
            status = "✅ 熟练" if word.get("is_proficient") else "📌 普通"

            with st.expander(
                f"{word['english']} → {word['chinese']} "
                f"({word.get('category', 'noun')}) · {status}"
            ):
                pronunciation_button(
                    word["english"],
                    f"vocabulary_view_audio_{word['id']}",
                )

                if word.get("cn_note"):
                    st.caption(f"中文备注：{word['cn_note']}")

                if word.get("en_note"):
                    st.caption(f"英文备注：{word['en_note']}")

                if not word.get("is_proficient"):
                    st.caption(
                        f"普通优先级：{word.get('review_priority', 12)} "
                        f"| 连续答对：{word.get('review_correct_streak', 0)} "
                        f"| 连续答错：{word.get('review_wrong_streak', 0)}"
                    )
                else:
                    st.caption(
                        f"中译英概率："
                        f"{probability(word, [x for x in words if x.get('is_proficient')], '中译英'):.2f}%"
                    )
                    st.caption(
                        f"英译中概率："
                        f"{probability(word, [x for x in words if x.get('is_proficient')], '英译中'):.2f}%"
                    )
