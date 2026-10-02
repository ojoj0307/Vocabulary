import base64
import json
import random
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import requests
import streamlit as st

# ==================== 1. 页面基本配置 ====================
st.set_page_config(
    page_title="背单词 & 练习应用",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 自定义 CSS：调整字体显示与按钮样式
st.markdown(
    """
    <style>
    /* 保证单选框和按钮文本完全显示，不截断 */
    .stRadio label, .stButton button {
        white-space: nowrap !important;
        word-break: keep-all !important;
    }
    .stButton button {
        width: 100%;
    }
    </style>
""",
    unsafe_allow_html=True,
)

# ==================== 2. GitHub API 配置 ====================
GITHUB_TOKEN = st.secrets.get("GITHUB_TOKEN", "")
REPO_OWNER = "ojoj0307"
REPO_NAME = "english-vocabulary"
BRANCH = "main"

HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}

TIMEZONE = ZoneInfo("Asia/Kuala_Lumpur")


def get_today_str():
    return datetime.now(TIMEZONE).strftime("%Y-%m-%d")


# ==================== 3. GitHub 数据读写函数 ====================
def fetch_json_from_github(file_path):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{file_path}?ref={BRANCH}"
    response = requests.get(url, headers=HEADERS)
    if response.status_code == 200:
        content = response.json()
        decoded_bytes = base64.b64decode(content["content"])
        return json.loads(decoded_bytes.decode("utf-8")), content["sha"]
    elif response.status_code == 404:
        return None, None
    else:
        st.error(
            f"读取 GitHub 文件 {file_path} 失败，状态码：{response.status_code}"
        )
        return None, None


def save_json_to_github(file_path, data, sha, message):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{file_path}"
    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    encoded_content = base64.b64encode(json_str.encode("utf-8")).decode("utf-8")

    payload = {
        "message": message,
        "content": encoded_content,
        "branch": BRANCH,
    }
    if sha:
        payload["sha"] = sha

    response = requests.put(url, headers=HEADERS, json=payload)
    if response.status_code in [200, 201]:
        return response.json()["content"]["sha"]
    else:
        st.error(
            f"保存到 GitHub 文件 {file_path} 失败，状态码：{response.status_code}"
        )
        return None


# ==================== 4. 数据初始化与同步 ====================
def load_data():
    vocab_data, vocab_sha = fetch_json_from_github("vocabulary.json")
    if vocab_data is None:
        vocab_data = []

    new_words_data, new_words_sha = fetch_json_from_github("new_words.json")
    if new_words_data is None:
        new_words_data = {"date": get_today_str(), "words": []}

    # 跨日清空逻辑
    if new_words_data.get("date") != get_today_str():
        new_words_data = {"date": get_today_str(), "words": []}

    stats_data, stats_sha = fetch_json_from_github("daily_stats.json")
    today = get_today_str()
    if stats_data is None or stats_data.get("date") != today:
        stats_data = {
            "date": today,
            "total_answered": 0,
            "c2e_correct": 0,
            "c2e_total": 0,
            "e2c_correct": 0,
            "e2c_total": 0,
        }

    st.session_state.vocab = vocab_data
    st.session_state.vocab_sha = vocab_sha
    st.session_state.new_words = new_words_data
    st.session_state.new_words_sha = new_words_sha
    st.session_state.daily_stats = stats_data
    st.session_state.stats_sha = stats_sha


if "vocab" not in st.session_state:
    load_data()


# ==================== 5. 辅助功能 ====================
def play_audio(word):
    audio_html = f"""
        <audio autoplay style="display:none;">
            <source src="https://dict.youdao.com/dictvoice?audio={word}&type=1" type="audio/mpeg">
        </audio>
    """
    st.components.v1.html(audio_html, height=0)


def calculate_weight(correct, wrong):
    # 动态权重算法：基于答题正确率
    total = correct + wrong
    if total == 0:
        return 10
    accuracy = correct / total
    if accuracy < 0.3:
        return 20
    elif accuracy < 0.6:
        return 15
    elif accuracy < 0.8:
        return 10
    else:
        return 5


# ==================== 6. 侧边栏与模式选择 ====================
st.sidebar.title("📌 导航菜单")
mode = st.sidebar.radio(
    "选择模式",
    ["🎓 学习模式", "🎯 练习模式", "📚 词库管理", "📖 查看词库"],
)

st.sidebar.markdown("---")
st.sidebar.subheader("📊 今日统计")
stats = st.session_state.daily_stats
st.sidebar.write(f"今日答题总数：**{stats['total_answered']}**")

c2e_acc = (
    (stats["c2e_correct"] / stats["c2e_total"] * 100)
    if stats["c2e_total"] > 0
    else 0
)
e2c_acc = (
    (stats["e2c_correct"] / stats["e2c_total"] * 100)
    if stats["e2c_total"] > 0
    else 0
)

st.sidebar.write(
    f"中译英正确率：**{c2e_acc:.1f}%** ({stats['c2e_correct']}/{stats['c2e_total']})"
)
st.sidebar.write(
    f"英译中正确率：**{e2c_acc:.1f}%** ({stats['e2c_correct']}/{stats['e2c_total']})"
)


# ==================== 模块 1：🎓 学习模式 ====================
if mode == "🎓 学习模式":
    st.header("🎓 学习模式 - 添加与学习每日新词")

    tab1, tab2 = st.tabs(["批量/表格添加新词", "新词卡片学习"])

    with tab1:
        st.subheader("添加新单词（支持 Excel 复制粘贴格式）")
        input_method = st.radio("输入方式", ["文本批量粘贴", "在线表格编辑"])

        if input_method == "文本批量粘贴":
            st.caption("格式：每行一个词，使用 tab 或逗号分隔：`英文  中文  词性  备注`")
            raw_text = st.text_area("在此粘贴文本", height=150)
            if st.button("提交添加"):
                if raw_text.strip():
                    lines = raw_text.strip().split("\n")
                    added_count = 0
                    for line in lines:
                        parts = [
                            p.strip()
                            for p in line.replace("\t", ",").split(",")
                            if p.strip()
                        ]
                        if len(parts) >= 2:
                            word_item = {
                                "english": parts[0],
                                "chinese": parts[1],
                                "pos": parts[2] if len(parts) > 2 else "v.",
                                "note": parts[3] if len(parts) > 3 else "",
                                "correct": 0,
                                "wrong": 0,
                            }
                            st.session_state.new_words["words"].append(
                                word_item
                            )
                            # 同步追加到正式词库
                            st.session_state.vocab.append(word_item)
                            added_count += 1

                    # 保存更新
                    st.session_state.new_words_sha = save_json_to_github(
                        "new_words.json",
                        st.session_state.new_words,
                        st.session_state.new_words_sha,
                        "Update new words",
                    )
                    st.session_state.vocab_sha = save_json_to_github(
                        "vocabulary.json",
                        st.session_state.vocab,
                        st.session_state.vocab_sha,
                        "Sync new words to main vocab",
                    )
                    st.success(f"成功添加 {added_count} 个单词！")
                    st.rerun()

        elif input_method == "在线表格编辑":
            df_template = pd.DataFrame(
                columns=["english", "chinese", "pos", "note"]
            )
            edited_df = st.data_editor(
                df_template, num_rows="dynamic", use_container_width=True
            )
            if st.button("保存表格数据"):
                added_count = 0
                for idx, row in edited_df.iterrows():
                    if row["english"] and row["chinese"]:
                        word_item = {
                            "english": str(row["english"]).strip(),
                            "chinese": str(row["chinese"]).strip(),
                            "pos": (
                                str(row["pos"]).strip() if row["pos"] else "v."
                            ),
                            "note": (
                                str(row["note"]).strip() if row["note"] else ""
                            ),
                            "correct": 0,
                            "wrong": 0,
                        }
                        st.session_state.new_words["words"].append(word_item)
                        st.session_state.vocab.append(word_item)
                        added_count += 1

                if added_count > 0:
                    st.session_state.new_words_sha = save_json_to_github(
                        "new_words.json",
                        st.session_state.new_words,
                        st.session_state.new_words_sha,
                        "Update new words from table",
                    )
                    st.session_state.vocab_sha = save_json_to_github(
                        "vocabulary.json",
                        st.session_state.vocab,
                        st.session_state.vocab_sha,
                        "Sync table new words to vocab",
                    )
                    st.success(f"成功添加 {added_count} 个单词！")
                    st.rerun()

    with tab2:
        words = st.session_state.new_words.get("words", [])
        if not words:
            st.info("今日暂无新词，请先在上方添加。")
        else:
            st.subheader(f"今日新词卡片（共 {len(words)} 个）")
            for idx, item in enumerate(words):
                with st.expander(f"{idx + 1}. {item['english']}"):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"**词性**: {item.get('pos', 'v.')}")
                        st.write(f"**中文**: {item['chinese']}")
                        if item.get("note"):
                            st.write(f"**备注**: {item['note']}")
                    with col2:
                        if st.button("🔊 发音", key=f"voice_learn_{idx}"):
                            play_audio(item["english"])


# ==================== 模块 2：🎯 练习模式 ====================
elif mode == "🎯 练习模式":
    st.header("🎯 练习模式")

    vocab = st.session_state.vocab
    if not vocab:
        st.warning("词库为空，请先前往学习模式或词库管理添加单词！")
    else:
        # 修改方向选项名称：改成“中译英”和“英译中”
        col_opt1, col_opt2 = st.columns([2, 2])
        with col_opt1:
            quiz_type = st.radio(
                "请选择练习模式", ["中译英", "英译中"], horizontal=True
            )

        # 权重抽题
        if "current_quiz" not in st.session_state:

            def get_next_question():
                weights = [
                    calculate_weight(
                        item.get("correct", 0), item.get("wrong", 0)
                    )
                    for item in vocab
                ]
                selected_item = random.choices(vocab, weights=weights, k=1)[0]
                return selected_item

            st.session_state.current_quiz = get_next_question()
            st.session_state.quiz_submitted = False
            st.session_state.user_answer = ""

        quiz = st.session_state.current_quiz

        st.subheader("请回答以下题目：")
        if quiz_type == "中译英":
            st.markdown(
                f"### 中文词意：**{quiz['chinese']}** ({quiz.get('pos', 'v.')})"
            )
            user_input = st.text_input(
                "请输入对应的英文单词：", key="quiz_input"
            )

            col1, col2 = st.columns([1, 4])
            with col1:
                submit_btn = st.button("提交答案")

            if submit_btn and user_input:
                is_correct = (
                    user_input.strip().lower() == quiz["english"].lower()
                )
                st.session_state.quiz_submitted = True
                st.session_state.is_correct = is_correct

                # 更新统计
                st.session_state.daily_stats["total_answered"] += 1
                st.session_state.daily_stats["c2e_total"] += 1

                if is_correct:
                    st.success("🎉 回答正确！")
                    quiz["correct"] = quiz.get("correct", 0) + 1
                    st.session_state.daily_stats["c2e_correct"] += 1
                else:
                    st.error(f"❌ 回答错误！正确答案是：**{quiz['english']}**")
                    quiz["wrong"] = quiz.get("wrong", 0) + 1

                # 保存词库与统计
                save_json_to_github(
                    "vocabulary.json",
                    st.session_state.vocab,
                    st.session_state.vocab_sha,
                    "Update word counts",
                )
                save_json_to_github(
                    "daily_stats.json",
                    st.session_state.daily_stats,
                    st.session_state.stats_sha,
                    "Update daily stats",
                )

            if st.session_state.get("quiz_submitted") and not st.session_state.get(
                "is_correct"
            ):
                if st.button("🙋 我的答案也是近义词（算我对）"):
                    quiz["wrong"] = max(0, quiz.get("wrong", 1) - 1)
                    quiz["correct"] = quiz.get("correct", 0) + 1
                    st.session_state.daily_stats["c2e_correct"] += 1
                    save_json_to_github(
                        "vocabulary.json",
                        st.session_state.vocab,
                        st.session_state.vocab_sha,
                        "Override answer to correct",
                    )
                    save_json_to_github(
                        "daily_stats.json",
                        st.session_state.daily_stats,
                        st.session_state.stats_sha,
                        "Override stats",
                    )
                    st.success("已修正为正确！")
                    st.rerun()

        else:  # 英译中
            st.markdown(f"### 英文单词：**{quiz['english']}**")
            if st.button("🔊 发音", key="voice_quiz"):
                play_audio(quiz["english"])

            user_input = st.text_input(
                "请输入中文含义（参考含义即可）：", key="quiz_input_e2c"
            )

            col1, col2 = st.columns([1, 4])
            with col1:
                submit_btn = st.button("提交答案")

            if submit_btn and user_input:
                st.info(f"参考标准答案：**{quiz['chinese']}**")
                col_correct, col_wrong = st.columns(2)

                st.session_state.daily_stats["total_answered"] += 1
                st.session_state.daily_stats["e2c_total"] += 1

                with col_correct:
                    if st.button("✅ 我答对了"):
                        quiz["correct"] = quiz.get("correct", 0) + 1
                        st.session_state.daily_stats["e2c_correct"] += 1
                        save_json_to_github(
                            "vocabulary.json",
                            st.session_state.vocab,
                            st.session_state.vocab_sha,
                            "Update stats",
                        )
                        save_json_to_github(
                            "daily_stats.json",
                            st.session_state.daily_stats,
                            st.session_state.stats_sha,
                            "Update stats",
                        )
                        del st.session_state.current_quiz
                        st.rerun()

                with col_wrong:
                    if st.button("❌ 我答错了"):
                        quiz["wrong"] = quiz.get("wrong", 0) + 1
                        save_json_to_github(
                            "vocabulary.json",
                            st.session_state.vocab,
                            st.session_state.vocab_sha,
                            "Update stats",
                        )
                        save_json_to_github(
                            "daily_stats.json",
                            st.session_state.daily_stats,
                            st.session_state.stats_sha,
                            "Update stats",
                        )
                        del st.session_state.current_quiz
                        st.rerun()

        if st.button("下一题 ➡️"):
            del st.session_state.current_quiz
            st.rerun()


# ==================== 模块 3：📚 词库管理 ====================
elif mode == "📚 词库管理":
    st.header("📚 词库管理")

    tab_manage, tab_import = st.tabs(["修改与删除单词", "批量表格导入"])

    with tab_manage:
        if not st.session_state.vocab:
            st.info("词库中暂无单词。")
        else:
            search_word = st.text_input("🔍 搜索要修改或删除的单词：")
            filtered_vocab = [
                item
                for item in st.session_state.vocab
                if search_word.lower() in item["english"].lower()
                or search_word in item["chinese"]
            ]

            for idx, item in enumerate(filtered_vocab):
                with st.expander(
                    f"{item['english']} - {item['chinese']} ({item.get('pos', 'v.')})"
                ):
                    new_eng = st.text_input(
                        "英文", value=item["english"], key=f"edit_eng_{idx}"
                    )
                    new_chi = st.text_input(
                        "中文", value=item["chinese"], key=f"edit_chi_{idx}"
                    )
                    new_pos = st.text_input(
                        "词性",
                        value=item.get("pos", "v."),
                        key=f"edit_pos_{idx}",
                    )
                    new_note = st.text_input(
                        "备注",
                        value=item.get("note", ""),
                        key=f"edit_note_{idx}",
                    )

                    col_save, col_del = st.columns([1, 1])
                    with col_save:
                        if st.button("💾 保存修改", key=f"save_btn_{idx}"):
                            item["english"] = new_eng
                            item["chinese"] = new_chi
                            item["pos"] = new_pos
                            item["note"] = new_note
                            st.session_state.vocab_sha = save_json_to_github(
                                "vocabulary.json",
                                st.session_state.vocab,
                                st.session_state.vocab_sha,
                                "Update word",
                            )
                            st.success("修改成功！")
                            st.rerun()

                    with col_del:
                        if st.button("🗑️ 删除单词", key=f"del_btn_{idx}"):
                            st.session_state.vocab.remove(item)
                            st.session_state.vocab_sha = save_json_to_github(
                                "vocabulary.json",
                                st.session_state.vocab,
                                st.session_state.vocab_sha,
                                "Delete word",
                            )
                            st.success("删除成功！")
                            st.rerun()

    with tab_import:
        st.subheader("批量导入单词到完整词库")
        df_import = st.data_editor(
            pd.DataFrame(columns=["english", "chinese", "pos", "note"]),
            num_rows="dynamic",
            key="import_editor",
        )
        if st.button("确认导入词库"):
            count = 0
            for _, row in df_import.iterrows():
                if row["english"] and row["chinese"]:
                    st.session_state.vocab.append(
                        {
                            "english": str(row["english"]).strip(),
                            "chinese": str(row["chinese"]).strip(),
                            "pos": (
                                str(row["pos"]).strip() if row["pos"] else "v."
                            ),
                            "note": (
                                str(row["note"]).strip() if row["note"] else ""
                            ),
                            "correct": 0,
                            "wrong": 0,
                        }
                    )
                    count += 1
            if count > 0:
                st.session_state.vocab_sha = save_json_to_github(
                    "vocabulary.json",
                    st.session_state.vocab,
                    st.session_state.vocab_sha,
                    "Batch import words",
                )
                st.success(f"成功导入 {count} 个单词！")
                st.rerun()


# ==================== 模块 4：📖 查看词库 ====================
elif mode == "📖 查看词库":
    st.header("📖 完整词库列表")

    vocab = st.session_state.vocab
    if not vocab:
        st.info("词库为空。")
    else:
        # 准备表格数据
        data_list = []
        total_weights = sum(
            [
                calculate_weight(item.get("correct", 0), item.get("wrong", 0))
                for item in vocab
            ]
        )

        for item in vocab:
            w = calculate_weight(item.get("correct", 0), item.get("wrong", 0))
            prob = (w / total_weights * 100) if total_weights > 0 else 0
            data_list.append(
                {
                    "英文": item["english"],
                    "中文": item["chinese"],
                    "词性": item.get("pos", "v."),
                    "备注": item.get("note", ""),
                    "答对次数": item.get("correct", 0),
                    "答错次数": item.get("wrong", 0),
                    "当前权重": w,
                    "抽题概率 (%)": round(prob, 2),
                }
            )

        df = pd.DataFrame(data_list)

        # 筛选与搜索
        col_search, col_pos = st.columns([2, 1])
        with col_search:
            search_query = st.text_input("🔍 搜索单词或中文：")
        with col_pos:
            pos_filter = st.selectbox(
                "词性筛选",
                ["全部"] + list(df["词性"].unique()) if not df.empty else ["全部"],
            )

        if search_query:
            df = df[
                df["英文"].str.contains(search_query, case=False)
                | df["中文"].str.contains(search_query)
            ]

        if pos_filter != "全部":
            df = df[df["词性"] == pos_filter]

        st.dataframe(df, use_container_width=True, height=500)
