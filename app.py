import requests
import textwrap


SOURCE_URL = (
    "https://raw.githubusercontent.com/ojoj0307/"
    "Vocabulary/master/app.py"
)


response = requests.get(
    SOURCE_URL,
    timeout=30
)
response.raise_for_status()
source = response.text


def replace_once(text, old, new, label):
    if old not in text:
        raise RuntimeError(f"找不到替换位置：{label}")
    return text.replace(old, new, 1)


def patch_function(text, start_marker, end_marker, callback):
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    block = text[start:end]
    block = callback(block)
    return text[:start] + block + text[end:]


# ============================================================
# 正式词库增加普通模式字段
# ============================================================

def patch_vocabulary_normalization(block):
    addition = """
        if "priority" not in word:
            word["priority"] = (
                0
                if word.get("proficient", False)
                else 12
            )
            changed = True

        if "proficient" not in word:
            word["proficient"] = (
                int(word.get("priority", 12)) <= 0
            )
            changed = True

        if "correct_streak" not in word:
            word["correct_streak"] = 0
            changed = True

        if "wrong_streak" not in word:
            word["wrong_streak"] = 0
            changed = True

"""
    return replace_once(
        block,
        "    return changed",
        addition + "    return changed",
        "正式词库字段"
    )


source = patch_function(
    source,
    "def normalize_vocabulary(data):",
    "# 加载正式词库",
    patch_vocabulary_normalization
)


# ============================================================
# 新词增加轮次字段
# ============================================================

def patch_new_word_normalization(block):
    addition = """
    if "proficient" not in word:
        word["proficient"] = False
        changed = True

    if "cn_to_en_round_done" not in word:
        word["cn_to_en_round_done"] = False
        changed = True

    if "en_to_cn_round_done" not in word:
        word["en_to_cn_round_done"] = False
        changed = True

"""
    return replace_once(
        block,
        "    return changed",
        addition + "    return changed",
        "新词字段"
    )


source = patch_function(
    source,
    "def normalize_new_word(word):",
    "# 加载新词",
    patch_new_word_normalization
)


# ============================================================
# 新词抽取：同一题型一轮内答对后不再重复
# ============================================================

new_word_selector = r'''
def get_new_word_candidates(q_type="中译英"):

    round_key = (
        "cn_to_en_round_done"
        if q_type == "中译英"
        else "en_to_cn_round_done"
    )

    candidates = [
        word
        for word in new_words
        if not bool(word.get(round_key, False))
    ]

    if not candidates and new_words:
        for word in new_words:
            word[round_key] = False

        candidates = list(new_words)

    return candidates


def get_random_new_word(q_type="中译英"):

    candidates = get_new_word_candidates(q_type)

    if not candidates:
        return None

    weights = [
        calculate_sampling_weight(word, q_type)
        for word in candidates
    ]

    selected_word = random.choices(
        candidates,
        weights=weights,
        k=1
    )[0]

    not_seen_key = (
        "cn_to_en_not_seen"
        if q_type == "中译英"
        else "en_to_cn_not_seen"
    )

    selected_word[not_seen_key] = 0

    for word in candidates:
        if word is not selected_word:
            try:
                current_not_seen = int(
                    word.get(not_seen_key, 0)
                )
            except (ValueError, TypeError):
                current_not_seen = 0

            word[not_seen_key] = current_not_seen + 1

    return selected_word


'''


start = source.index(
    'def get_random_new_word(q_type="中译英"):'
)
end = source.index("# 发音", start)

source = (
    source[:start]
    + new_word_selector
    + source[end:]
)


# ============================================================
# 新词答对后标记当前题型已完成
# ============================================================

old_learning_update = r'''                    weight_key = "cn_to_en_weight" if learning_question_type == "中译英" else "en_to_cn_weight"

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

'''


new_learning_update = r'''                    weight_key = "cn_to_en_weight" if learning_question_type == "中译英" else "en_to_cn_weight"

                    round_key = (
                        "cn_to_en_round_done"
                        if learning_question_type == "中译英"
                        else "en_to_cn_round_done"
                    )

                    if is_correct:
                        learning_word[round_key] = True
                        learning_word[weight_key] = max(
                            1,
                            int(
                                learning_word.get(
                                    weight_key,
                                    3
                                )
                            ) - 1
                        )

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

'''


source = replace_once(
    source,
    old_learning_update,
    new_learning_update,
    "新词答题更新"
)


# ============================================================
# 新词和正式词库的新建记录增加字段
# ============================================================

source = source.replace(
    '''                    "cn_to_en_weight": 3,
                    "en_to_cn_weight": 3
                }''',
    '''                    "cn_to_en_weight": 3,
                    "en_to_cn_weight": 3,
                    "proficient": False,
                    "cn_to_en_round_done": False,
                    "en_to_cn_round_done": False
                }''',
    1
)


source = source.replace(
    '''                        "correct": 0,
                        "wrong": 0
                    })''',
    '''                        "correct": 0,
                        "wrong": 0,
                        "priority": 12,
                        "proficient": False,
                        "correct_streak": 0,
                        "wrong_streak": 0
                    })'''
)


# ============================================================
# 新词列表增加发音按钮和熟练勾选
# ============================================================

new_word_caption = '''                st.caption(
                    f"中译英权重：{word.get('cn_to_en_weight', 3)} | 概率：{calculate_new_probability(word, '中译英'):.2f}%"
'''


new_word_controls = '''                pronunciation_button(
                    word["english"],
                    f"new_word_sound_{index}"
                )

                current_new_proficient = bool(
                    word.get("proficient", False)
                )

                edit_new_proficient = st.checkbox(
                    "熟练",
                    value=current_new_proficient,
                    key=f"new_edit_proficient_{index}"
                )

                if edit_new_proficient != current_new_proficient:
                    word["proficient"] = edit_new_proficient

                    for vocabulary_word in words:
                        if (
                            vocabulary_word.get(
                                "english",
                                ""
                            ).strip().lower()
                            == word["english"].strip().lower()
                            and vocabulary_word.get(
                                "chinese",
                                ""
                            ).strip()
                            == word["chinese"].strip()
                            and vocabulary_word.get(
                                "category",
                                "noun"
                            )
                            == word.get(
                                "category",
                                "noun"
                            )
                        ):
                            vocabulary_word["proficient"] = (
                                edit_new_proficient
                            )

                            if edit_new_proficient:
                                vocabulary_word["priority"] = 0
                                vocabulary_word["correct_streak"] = 5
                                vocabulary_word["wrong_streak"] = 0
                            else:
                                vocabulary_word["priority"] = 12
                                vocabulary_word["correct_streak"] = 0
                                vocabulary_word["wrong_streak"] = 0

                            break

                    new_ok = save_new_words()
                    vocab_ok = save_words()

                    if new_ok and vocab_ok:
                        st.rerun()
                    else:
                        st.error(
                            "熟练状态保存失败，请检查 GitHub Token。"
                        )

'''


source = replace_once(
    source,
    new_word_caption,
    new_word_controls + new_word_caption,
    "新词发音和熟练选项"
)


# ============================================================
# 正式词库编辑区增加熟练勾选
# ============================================================

formal_caption = '''            st.caption(
                f"中译英：权重 {calculate_sampling_weight(word, '中译英')} | "
'''


formal_controls = '''            current_proficient = bool(
                word.get("proficient", False)
            )

            edit_proficient = st.checkbox(
                "熟练",
                value=current_proficient,
                key=f"edit_proficient_{index}"
            )

            if edit_proficient != current_proficient:
                word["proficient"] = edit_proficient

                if edit_proficient:
                    word["priority"] = 0
                    word["correct_streak"] = 5
                    word["wrong_streak"] = 0
                else:
                    word["priority"] = 12
                    word["correct_streak"] = 0
                    word["wrong_streak"] = 0

                if save_words():
                    st.rerun()
                else:
                    st.error(
                        "熟练状态保存失败，请检查 GitHub Token。"
                    )

'''


source = replace_once(
    source,
    formal_caption,
    formal_controls + formal_caption,
    "正式词库熟练选项"
)


# ============================================================
# 新复习系统
# ============================================================

review_helpers = r'''
NORMAL_INITIAL_PRIORITY = 12
NORMAL_MAX_PRIORITY = 100
NORMAL_CORRECT_STEPS = [1, 2, 3, 4, 2]


def safe_int(value, default=0):

    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def is_proficient_word(word):

    return bool(word.get("proficient", False)) or (
        safe_int(
            word.get(
                "priority",
                NORMAL_INITIAL_PRIORITY
            ),
            NORMAL_INITIAL_PRIORITY
        )
        <= 0
    )


def get_normal_word(q_type="中译英"):

    candidates = [
        word
        for word in words
        if not is_proficient_word(word)
    ]

    if not candidates:
        return None

    weights = [
        max(
            1,
            safe_int(
                word.get(
                    "priority",
                    NORMAL_INITIAL_PRIORITY
                ),
                NORMAL_INITIAL_PRIORITY
            )
        )
        for word in candidates
    ]

    return random.choices(
        candidates,
        weights=weights,
        k=1
    )[0]


def get_proficient_word(q_type="中译英"):

    candidates = [
        word
        for word in words
        if is_proficient_word(word)
    ]

    if not candidates:
        return None

    weights = [
        calculate_sampling_weight(word, q_type)
        for word in candidates
    ]

    selected_word = random.choices(
        candidates,
        weights=weights,
        k=1
    )[0]

    not_seen_key = (
        "cn_to_en_not_seen"
        if q_type == "中译英"
        else "en_to_cn_not_seen"
    )

    selected_word[not_seen_key] = 0

    for word in candidates:
        if word is not selected_word:
            word[not_seen_key] = (
                safe_int(
                    word.get(not_seen_key, 0),
                    0
                ) + 1
            )

    return selected_word


def update_normal_priority(word, is_correct):

    if is_correct:
        correct_streak = (
            safe_int(
                word.get("correct_streak", 0),
                0
            ) + 1
        )

        word["correct_streak"] = correct_streak
        word["wrong_streak"] = 0

        step_index = min(
            correct_streak,
            len(NORMAL_CORRECT_STEPS)
        ) - 1

        decrease = NORMAL_CORRECT_STEPS[step_index]

        word["priority"] = max(
            0,
            safe_int(
                word.get(
                    "priority",
                    NORMAL_INITIAL_PRIORITY
                ),
                NORMAL_INITIAL_PRIORITY
            ) - decrease
        )

        if word["priority"] <= 0:
            word["priority"] = 0
            word["proficient"] = True
            word["correct_streak"] = 5

    else:
        wrong_streak = (
            safe_int(
                word.get("wrong_streak", 0),
                0
            ) + 1
        )

        word["wrong_streak"] = wrong_streak
        word["correct_streak"] = 0

        word["priority"] = min(
            NORMAL_MAX_PRIORITY,
            safe_int(
                word.get(
                    "priority",
                    NORMAL_INITIAL_PRIORITY
                ),
                NORMAL_INITIAL_PRIORITY
            ) + wrong_streak
        )

        word["proficient"] = False


def review_direction_fields(q_type="中译英"):

    if q_type == "中译英":
        return (
            "cn_to_en_correct",
            "cn_to_en_wrong",
            "cn_to_en_weight"
        )

    return (
        "en_to_cn_correct",
        "en_to_cn_wrong",
        "en_to_cn_weight"
    )


def update_review_counters(
    word,
    q_type,
    is_correct
):

    correct_key, wrong_key, _ = (
        review_direction_fields(q_type)
    )

    if is_correct:
        word[correct_key] = (
            safe_int(
                word.get(correct_key, 0),
                0
            ) + 1
        )
    else:
        word[wrong_key] = (
            safe_int(
                word.get(wrong_key, 0),
                0
            ) + 1
        )

    word["correct"] = (
        safe_int(
            word.get("cn_to_en_correct", 0),
            0
        )
        + safe_int(
            word.get("en_to_cn_correct", 0),
            0
        )
    )

    word["wrong"] = (
        safe_int(
            word.get("cn_to_en_wrong", 0),
            0
        )
        + safe_int(
            word.get("en_to_cn_wrong", 0),
            0
        )
    )


def update_daily_review_stats(
    q_type,
    is_correct
):

    global daily_stats

    answered_key = (
        "cn_to_en_answered"
        if q_type == "中译英"
        else "en_to_cn_answered"
    )

    correct_key = (
        "cn_to_en_correct"
        if q_type == "中译英"
        else "en_to_cn_correct"
    )

    daily_stats[answered_key] = (
        safe_int(
            daily_stats.get(answered_key, 0),
            0
        ) + 1
    )

    if is_correct:
        daily_stats[correct_key] = (
            safe_int(
                daily_stats.get(correct_key, 0),
                0
            ) + 1
        )


def submit_review_answer(
    word,
    q_type,
    answer,
    mode
):

    if q_type == "中译英":
        correct_answer = (
            word.get("english", "")
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
            word.get("chinese", "")
            .strip()
        )

        user_answer = answer.strip()

    is_correct = (
        user_answer == correct_answer
    )

    update_review_counters(
        word,
        q_type,
        is_correct
    )

    if mode == "normal":
        update_normal_priority(
            word,
            is_correct
        )

    else:
        _, _, weight_key = (
            review_direction_fields(q_type)
        )

        if is_correct:
            word[weight_key] = max(
                1,
                safe_int(
                    word.get(weight_key, 3),
                    3
                ) - 1
            )
        else:
            word[weight_key] = min(
                20,
                safe_int(
                    word.get(weight_key, 3),
                    3
                ) + 2
            )

    update_daily_review_stats(
        q_type,
        is_correct
    )

    save_words()
    save_daily_stats()

    return is_correct


def mark_wrong_review_as_correct(
    word,
    q_type,
    mode
):

    correct_key, wrong_key, weight_key = (
        review_direction_fields(q_type)
    )

    word[wrong_key] = max(
        0,
        safe_int(
            word.get(wrong_key, 0),
            0
        ) - 1
    )

    word[correct_key] = (
        safe_int(
            word.get(correct_key, 0),
            0
        ) + 1
    )

    word["correct"] = (
        safe_int(
            word.get("cn_to_en_correct", 0),
            0
        )
        + safe_int(
            word.get("en_to_cn_correct", 0),
            0
        )
    )

    word["wrong"] = (
        safe_int(
            word.get("cn_to_en_wrong", 0),
            0
        )
        + safe_int(
            word.get("en_to_cn_wrong", 0),
            0
        )
    )

    if mode == "normal":
        wrong_streak = safe_int(
            word.get("wrong_streak", 0),
            0
        )

        word["priority"] = max(
            0,
            safe_int(
                word.get(
                    "priority",
                    NORMAL_INITIAL_PRIORITY
                ),
                NORMAL_INITIAL_PRIORITY
            ) - wrong_streak
        )

        word["wrong_streak"] = 0

        update_normal_priority(
            word,
            True
        )

    else:
        word[weight_key] = max(
            1,
            safe_int(
                word.get(weight_key, 3),
                3
            ) - 2
        )

    daily_correct_key = (
        "cn_to_en_correct"
        if q_type == "中译英"
        else "en_to_cn_correct"
    )

    daily_stats[daily_correct_key] = (
        safe_int(
            daily_stats.get(daily_correct_key, 0),
            0
        ) + 1
    )

    save_words()
    save_daily_stats()


def render_previous_review(mode):

    prefix = "review_" + mode

    last_index = st.session_state.get(
        f"{prefix}_last_index"
    )

    last_correct = st.session_state.get(
        f"{prefix}_last_correct"
    )

    if last_index is None or last_correct is None:
        st.caption("开始答题后显示上一题")
        return

    if (
        not isinstance(last_index, int)
        or last_index < 0
        or last_index >= len(words)
    ):
        st.caption("上一题不存在")
        return

    last_word = words[last_index]

    q_type = st.session_state.get(
        f"{prefix}_last_question_type",
        "中译英"
    )

    last_answer = st.session_state.get(
        f"{prefix}_last_answer",
        ""
    )

    category = last_word.get(
        "category",
        "noun"
    )

    if q_type == "中译英":
        prompt = last_word.get(
            "chinese",
            ""
        )
        answer = last_word.get(
            "english",
            ""
        )
        note = last_word.get(
            "cn_note",
            ""
        )
    else:
        prompt = last_word.get(
            "english",
            ""
        )
        answer = last_word.get(
            "chinese",
            ""
        )
        note = last_word.get(
            "en_note",
            ""
        )

    note_display = (
        f"<br><small style='opacity:0.8;'>"
        f"📝 备注：{html.escape(note)}</small>"
        if note
        else ""
    )

    st.markdown(
        f"""
        <div class="previous-question">
            {html.escape(prompt)}
            {note_display}
        </div>
        <div class="previous-category">
            {html.escape(category)}
        </div>
        """,
        unsafe_allow_html=True
    )

    if q_type == "英译中":
        pronunciation_button(
            last_word.get("english", ""),
            f"{prefix}_last_sound"
        )

    st.markdown(
        f"""
        <div class="answer-text">
            你的答案：
            <b>{html.escape(last_answer)}</b>
        </div>
        <div class="answer-text">
            正确答案：
            <b>{html.escape(answer)}</b>
        </div>
        """,
        unsafe_allow_html=True
    )

    if last_correct:
        st.success("正确", icon="✅")
    else:
        st.error("错误", icon="❌")

        if st.button(
            "我的答案也是近义词 ✓",
            key=f"{prefix}_similar_answer",
            use_container_width=True
        ):
            mark_wrong_review_as_correct(
                last_word,
                q_type,
                mode
            )

            st.session_state[
                f"{prefix}_last_correct"
            ] = True

            st.rerun()


def render_review_mode(mode):

    prefix = "review_" + mode

    st.session_state.setdefault(
        f"{prefix}_current_index",
        None
    )

    st.session_state.setdefault(
        f"{prefix}_question_type",
        "中译英"
    )

    st.session_state.setdefault(
        f"{prefix}_last_index",
        None
    )

    st.session_state.setdefault(
        f"{prefix}_last_answer",
        ""
    )

    st.session_state.setdefault(
        f"{prefix}_last_correct",
        None
    )

    st.session_state.setdefault(
        f"{prefix}_last_question_type",
        "中译英"
    )

    st.session_state.setdefault(
        f"{prefix}_selected_question_type",
        "中译英"
    )

    q_type = st.radio(
        "题型",
        ["中译英", "英译中"],
        horizontal=True,
        key=f"{prefix}_question_type"
    )

    if q_type != st.session_state[
        f"{prefix}_selected_question_type"
    ]:
        st.session_state[
            f"{prefix}_selected_question_type"
        ] = q_type

        st.session_state[
            f"{prefix}_current_index"
        ] = None

    if mode == "normal":
        available = [
            word
            for word in words
            if not is_proficient_word(word)
        ]
        empty_message = (
            "普通词库暂时没有词，请先在词库管理中添加单词。"
        )
    else:
        available = [
            word
            for word in words
            if is_proficient_word(word)
        ]
        empty_message = (
            "还没有熟练词，请先在普通模式中连续答对 5 次。"
        )

    if not available:
        st.info(empty_message)
        return

    current_index = st.session_state[
        f"{prefix}_current_index"
    ]

    current_invalid = (
        current_index is None
        or current_index < 0
        or current_index >= len(words)
    )

    if not current_invalid:
        if mode == "normal":
            current_invalid = is_proficient_word(
                words[current_index]
            )
        else:
            current_invalid = not is_proficient_word(
                words[current_index]
            )

    if current_invalid:
        selected_word = (
            get_normal_word(q_type)
            if mode == "normal"
            else get_proficient_word(q_type)
        )

        if selected_word is None:
            st.info(empty_message)
            return

        current_index = words.index(selected_word)

        st.session_state[
            f"{prefix}_current_index"
        ] = current_index

    current_word = words[current_index]
    category = current_word.get(
        "category",
        "noun"
    )

    left, right = st.columns(
        [1, 1],
        gap="large"
    )

    with left:
        st.markdown("### 上一题")
        render_previous_review(mode)

    with right:
        st.markdown("### 下一题")

        if q_type == "中译英":
            prompt = current_word.get(
                "chinese",
                ""
            )
            note = current_word.get(
                "cn_note",
                ""
            )
        else:
            prompt = current_word.get(
                "english",
                ""
            )
            note = current_word.get(
                "en_note",
                ""
            )

        note_display = (
            f"<br><small style='opacity:0.8; "
            f"font-size:16px;'>"
            f"📝 备注：{html.escape(note)}</small>"
            if note
            else ""
        )

        st.markdown(
            f"""
            <div class="question">
                {html.escape(prompt)}
                {note_display}
            </div>
            <div class="question-category">
                {html.escape(category)}
            </div>
            """,
            unsafe_allow_html=True
        )

        if q_type == "英译中":
            pronunciation_button(
                current_word.get("english", ""),
                f"{prefix}_current_sound"
            )

        if mode == "normal":
            st.caption(
                f"当前优先级："
                f"{safe_int(current_word.get('priority', 12), 12)}"
                f" / {NORMAL_INITIAL_PRIORITY}"
            )
        else:
            st.caption(
                "熟练模式：使用原有概率系统抽题"
            )

        with st.form(
            key=f"{prefix}_answer_form",
            clear_on_submit=True
        ):
            answer = st.text_input(
                "答案",
                label_visibility="collapsed",
                placeholder="输入答案后按 Enter",
                autocomplete="off",
                key=f"{prefix}_answer_input"
            )

            submitted = st.form_submit_button(
                "提交",
                use_container_width=True
            )

        if submitted:
            answer = answer.strip()

            if not answer:
                st.warning("请输入答案后再提交。")
                st.stop()

            is_correct = submit_review_answer(
                current_word,
                q_type,
                answer,
                mode
            )

            st.session_state[
                f"{prefix}_last_index"
            ] = current_index

            st.session_state[
                f"{prefix}_last_answer"
            ] = answer

            st.session_state[
                f"{prefix}_last_correct"
            ] = is_correct

            st.session_state[
                f"{prefix}_last_question_type"
            ] = q_type

            next_word = (
                get_normal_word(q_type)
                if mode == "normal"
                else get_proficient_word(q_type)
            )

            if next_word is None:
                st.session_state[
                    f"{prefix}_current_index"
                ] = None
            else:
                st.session_state[
                    f"{prefix}_current_index"
                ] = words.index(next_word)

            st.rerun()


def render_daily_review_stats():

    st.divider()
    st.subheader("📊 今日统计")

    cn_answered = safe_int(
        daily_stats.get("cn_to_en_answered", 0),
        0
    )

    cn_correct = safe_int(
        daily_stats.get("cn_to_en_correct", 0),
        0
    )

    en_answered = safe_int(
        daily_stats.get("en_to_cn_answered", 0),
        0
    )

    en_correct = safe_int(
        daily_stats.get("en_to_cn_correct", 0),
        0
    )

    col1, col2 = st.columns(2)

    with col1:
        st.metric(
            "中译英",
            f"{cn_correct} / {cn_answered}"
        )

    with col2:
        st.metric(
            "英译中",
            f"{en_correct} / {en_answered}"
        )


'''


source = source.replace(
    "# 标题",
    review_helpers + "\n# 标题",
    1
)


# ============================================================
# 替换原练习页面
# ============================================================

review_start = source.index(
    'elif page == "🎯 练习模式":'
)

review_end = source.index(
    'elif page == "📚 词库管理":',
    review_start
)


new_review_page = '''
elif page == "🎯 练习模式":

    st.header("🎯 练习模式")

    normal_tab, proficient_tab = st.tabs(
        ["普通", "熟练"]
    )

    with normal_tab:
        render_review_mode("normal")

    with proficient_tab:
        render_review_mode("proficient")

    render_daily_review_stats()


'''


source = (
    source[:review_start]
    + new_review_page
    + source[review_end:]
)


# 执行修改后的原始程序。
exec(
    compile(
        source,
        "app.py",
        "exec"
    ),
    globals(),
    globals()
)
