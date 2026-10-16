import base64
import hashlib
import json
import random
import re
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
import streamlit as st

# ============================================================
# Configuration
# ============================================================
st.set_page_config(page_title="Vocabulary App", page_icon="📚", layout="wide")
TZ = ZoneInfo("Asia/Kuala_Lumpur")
CATEGORIES = ["noun", "verb", "adjective", "adverb", "other"]
DEFAULT_GROUP_ID = "default"
SCHEMA_VERSION = 2

try:
    SECRETS = st.secrets
except Exception:
    SECRETS = {}

GITHUB_OWNER = str(SECRETS.get("GITHUB_OWNER", "ojoj0307"))
# Configure this in Streamlit Secrets if the JSON data is stored in another repo.
GITHUB_REPO = str(SECRETS.get("GITHUB_REPO", "Vocabulary"))
GITHUB_BRANCH = str(SECRETS.get("GITHUB_BRANCH", "master"))
GITHUB_TOKEN = str(SECRETS.get("GITHUB_TOKEN", ""))
FILES = {
    "vocabulary": "vocabulary.json",
    "new_words": "new_words.json",
    "daily_stats": "daily_stats.json",
    "groups": "groups.json",
    "memberships": "group_memberships.json",
    "learning": "group_learning.json",
    "progress": "new_word_progress.json",
}
API_ROOT = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents"

st.markdown("""
<style>
.block-container {max-width: 1200px; padding-top: 1.6rem; padding-bottom: 2rem;}
.word-title {font-size: 1.8rem; font-weight: 700; text-align: center; overflow-wrap: anywhere;}
.muted {opacity: .7;}
</style>
""", unsafe_allow_html=True)


def today():
    return datetime.now(TZ).strftime("%Y-%m-%d")


def stable_id(english, chinese=""):
    key = f"{str(english).strip().lower()}|{str(chinese).strip().lower()}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def safe_int(value, default=0, low=None, high=None):
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = default
    if low is not None:
        value = max(low, value)
    if high is not None:
        value = min(high, value)
    return value


# ============================================================
# GitHub storage
# ============================================================
class GitHubStore:
    def __init__(self):
        self.cache = {}

    def headers(self):
        if not GITHUB_TOKEN:
            raise RuntimeError("缺少 GITHUB_TOKEN。请在 Streamlit Secrets 中设置。")
        return {
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def read(self, path):
        url = f"{API_ROOT}/{path}"
        response = requests.get(
            url,
            headers=self.headers(),
            params={"ref": GITHUB_BRANCH},
            timeout=20,
        )
        if response.status_code == 404:
            return None, None
        if response.status_code != 200:
            raise RuntimeError(f"GitHub 读取 {path} 失败 ({response.status_code}): {response.text[:300]}")
        obj = response.json()
        content = base64.b64decode(obj["content"].replace("\n", "")).decode("utf-8")
        return json.loads(content), obj.get("sha")

    def write(self, path, data, message, sha=None):
        # Always refresh SHA just before writing to reduce stale-SHA conflicts.
        current, latest_sha = self.read(path)
        payload = {
            "message": message,
            "content": base64.b64encode(
                json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
            ).decode("utf-8"),
            "branch": GITHUB_BRANCH,
        }
        if latest_sha:
            payload["sha"] = latest_sha
        elif sha:
            payload["sha"] = sha
        response = requests.put(
            f"{API_ROOT}/{path}",
            headers=self.headers(),
            json=payload,
            timeout=25,
        )
        if response.status_code not in (200, 201):
            raise RuntimeError(f"GitHub 保存 {path} 失败 ({response.status_code}): {response.text[:400]}")
        result = response.json()
        self.cache[path] = (data, result.get("content", {}).get("sha"))
        return True

    def load_or_default(self, path, default):
        data, sha = self.read(path)
        if data is None:
            return default, None, True
        return data, sha, False


store = GitHubStore()


# ============================================================
# Data model and migration
# ============================================================
def default_groups():
    return {
        "schema_version": SCHEMA_VERSION,
        "default_group_id": DEFAULT_GROUP_ID,
        "groups": [{"id": DEFAULT_GROUP_ID, "name": "默认词库", "created_at": today()}],
    }


def default_new_words():
    return {"date": today(), "words": []}


def default_daily_stats():
    return {"schema_version": SCHEMA_VERSION, "date": today(), "by_group": {}}


def blank_learning_record():
    return {
        "cn_to_en_weight": 3, "en_to_cn_weight": 3,
        "cn_to_en_correct": 0, "cn_to_en_wrong": 0,
        "en_to_cn_correct": 0, "en_to_cn_wrong": 0,
        "cn_to_en_not_seen": 0, "en_to_cn_not_seen": 0,
    }


def blank_progress(date, group_id):
    return {
        "date": date, "group_id": group_id,
        "cn_to_en": {"round": 1, "completed_word_ids": []},
        "en_to_cn": {"round": 1, "completed_word_ids": []},
    }


def normalize_word(raw):
    word = dict(raw) if isinstance(raw, dict) else {}
    word["english"] = str(word.get("english", "")).strip()
    word["chinese"] = str(word.get("chinese", "")).strip()
    word["category"] = word.get("category", "noun")
    if word["category"] not in CATEGORIES:
        word["category"] = "other"
    for key in (
        "cn_note", "en_note", "english_note", "chinese_note",
        "plural", "third_person", "past", "past_participle",
        "comparative", "superlative", "countable", "synonyms",
    ):
        word.setdefault(key, "")
    word.setdefault("id", stable_id(word["english"], word["chinese"]))
    # Keep old fields intact for backwards compatibility.
    return word


def normalize_learning_record(old=None):
    old = old if isinstance(old, dict) else {}
    rec = blank_learning_record()
    legacy_weight = safe_int(old.get("weight", 3), 3, 1, 20)
    rec["cn_to_en_weight"] = safe_int(old.get("cn_to_en_weight", legacy_weight), legacy_weight, 1, 20)
    rec["en_to_cn_weight"] = safe_int(old.get("en_to_cn_weight", legacy_weight), legacy_weight, 1, 20)
    rec["cn_to_en_correct"] = safe_int(old.get("cn_to_en_correct", old.get("correct", 0)), 0, 0)
    rec["cn_to_en_wrong"] = safe_int(old.get("cn_to_en_wrong", old.get("wrong", 0)), 0, 0)
    rec["en_to_cn_correct"] = safe_int(old.get("en_to_cn_correct", 0), 0, 0)
    rec["en_to_cn_wrong"] = safe_int(old.get("en_to_cn_wrong", 0), 0, 0)
    rec["cn_to_en_not_seen"] = safe_int(old.get("cn_to_en_not_seen", 0), 0, 0)
    rec["en_to_cn_not_seen"] = safe_int(old.get("en_to_cn_not_seen", 0), 0, 0)
    return rec


def load_all():
    # Read all existing files before making any writes.
    raw_words, _, words_missing = store.load_or_default(FILES["vocabulary"], [])
    if not isinstance(raw_words, list):
        raise ValueError("vocabulary.json 必须是 JSON 数组。")
    words = [normalize_word(w) for w in raw_words]
    ids = set()
    for w in words:
        if w["id"] in ids:
            w["id"] = stable_id(w["english"], w["chinese"] + str(len(ids)))
        ids.add(w["id"])

    groups, _, groups_missing = store.load_or_default(FILES["groups"], default_groups())
    if not isinstance(groups, dict) or not isinstance(groups.get("groups"), list):
        groups = default_groups()
        groups_missing = True
    if not any(g.get("id") == DEFAULT_GROUP_ID for g in groups["groups"]):
        groups["groups"].insert(0, {"id": DEFAULT_GROUP_ID, "name": "默认词库", "created_at": today()})
    groups.setdefault("default_group_id", DEFAULT_GROUP_ID)
    groups.setdefault("schema_version", SCHEMA_VERSION)

    memberships, _, memberships_missing = store.load_or_default(FILES["memberships"], {"memberships": []})
    if not isinstance(memberships, dict):
        memberships = {"memberships": []}
    memberships.setdefault("memberships", [])
    known_pairs = {(m.get("word_id"), m.get("group_id")) for m in memberships["memberships"] if isinstance(m, dict)}
    # Migration: all existing words belong to default group.
    for w in words:
        pair = (w["id"], DEFAULT_GROUP_ID)
        if pair not in known_pairs:
            memberships["memberships"].append({"word_id": w["id"], "group_id": DEFAULT_GROUP_ID})
            known_pairs.add(pair)

    learning, _, learning_missing = store.load_or_default(FILES["learning"], {"schema_version": SCHEMA_VERSION, "records": {}})
    if not isinstance(learning, dict):
        learning = {"schema_version": SCHEMA_VERSION, "records": {}}
    learning.setdefault("records", {})
    # Migrate old per-word learning fields into default group only.
    for w in words:
        key = f"{DEFAULT_GROUP_ID}:{w['id']}"
        if key not in learning["records"]:
            learning["records"][key] = normalize_learning_record(w)
    learning["schema_version"] = SCHEMA_VERSION

    new_data, _, new_missing = store.load_or_default(FILES["new_words"], default_new_words())
    if isinstance(new_data, list):
        new_data = {"date": today(), "words": new_data}
    if not isinstance(new_data, dict):
        new_data = default_new_words()
    new_data.setdefault("date", today())
    new_data.setdefault("words", [])
    # Keep today's list only, matching the old app's daily-new-word behavior.
    if new_data.get("date") != today():
        new_data = default_new_words()
    normalized_new = []
    for item in new_data["words"]:
        if isinstance(item, dict):
            w = normalize_word(item)
            # If a word was stored only in new_words.json, add it to canonical words.
            if not any(x["id"] == w["id"] for x in words):
                words.append(w)
                memberships["memberships"].append({"word_id": w["id"], "group_id": DEFAULT_GROUP_ID})
                learning["records"][f"{DEFAULT_GROUP_ID}:{w['id']}"] = normalize_learning_record(w)
            normalized_new.append(w["id"])
        elif isinstance(item, str):
            # Legacy list might contain an English word or an ID.
            found = next((w for w in words if w["id"] == item or w["english"].lower() == item.lower()), None)
            if found:
                normalized_new.append(found["id"])
    new_data = {"date": today(), "words": list(dict.fromkeys(normalized_new))}

    stats, _, stats_missing = store.load_or_default(FILES["daily_stats"], default_daily_stats())
    if not isinstance(stats, dict) or stats.get("date") != today():
        stats = default_daily_stats()
    # Migrate legacy aggregate daily stats into the default group instead of dropping them.
    if "by_group" not in stats:
        legacy = {
            "cn_to_en_answered": safe_int(stats.get("cn_to_en_answered", 0), 0, 0),
            "cn_to_en_correct": safe_int(stats.get("cn_to_en_correct", 0), 0, 0),
            "en_to_cn_answered": safe_int(stats.get("en_to_cn_answered", 0), 0, 0),
            "en_to_cn_correct": safe_int(stats.get("en_to_cn_correct", 0), 0, 0),
            "new_word_answered": 0,
            "new_word_correct": 0,
        }
        stats["by_group"] = {DEFAULT_GROUP_ID: legacy}
    stats.setdefault("by_group", {})

    progress, _, progress_missing = store.load_or_default(FILES["progress"], {"schema_version": SCHEMA_VERSION, "items": {}})
    if not isinstance(progress, dict):
        progress = {"schema_version": SCHEMA_VERSION, "items": {}}
    progress.setdefault("items", {})
    progress["schema_version"] = SCHEMA_VERSION

    return {
        "words": words, "groups": groups, "memberships": memberships,
        "learning": learning, "new_words": new_data, "stats": stats,
        "progress": progress,
        "missing": {
            "vocabulary": words_missing, "groups": groups_missing,
            "memberships": memberships_missing, "learning": learning_missing,
            "new_words": new_missing, "daily_stats": stats_missing,
            "progress": progress_missing,
        }
    }


def save_data(key, data, message=None):
    # `data` is the full in-memory app state; write only the selected JSON document.
    payload = data[key]
    return store.write(FILES[key], payload, message or f"Update {FILES[key]}")


def get_group_names(data):
    return {g["id"]: g["name"] for g in data["groups"]["groups"]}


def group_word_ids(data, group_id):
    return {
        m["word_id"] for m in data["memberships"]["memberships"]
        if m.get("group_id") == group_id
    }


def get_word(data, word_id):
    return next((w for w in data["words"] if w.get("id") == word_id), None)


def learning_key(group_id, word_id):
    return f"{group_id}:{word_id}"


def get_record(data, group_id, word_id):
    key = learning_key(group_id, word_id)
    if key not in data["learning"]["records"]:
        data["learning"]["records"][key] = blank_learning_record()
    return data["learning"]["records"][key]


def add_membership(data, word_id, group_id):
    pairs = {(m.get("word_id"), m.get("group_id")) for m in data["memberships"]["memberships"]}
    if (word_id, group_id) not in pairs:
        data["memberships"]["memberships"].append({"word_id": word_id, "group_id": group_id})
    get_record(data, group_id, word_id)


def remove_membership(data, word_id, group_id):
    data["memberships"]["memberships"] = [
        m for m in data["memberships"]["memberships"]
        if not (m.get("word_id") == word_id and m.get("group_id") == group_id)
    ]
    # Keep learning records for history/re-adding the word later.


def get_progress(data, group_id):
    key = f"{today()}:{group_id}"
    if key not in data["progress"]["items"]:
        data["progress"]["items"][key] = blank_progress(today(), group_id)
    p = data["progress"]["items"][key]
    for direction in ("cn_to_en", "en_to_cn"):
        p.setdefault(direction, {"round": 1, "completed_word_ids": []})
        p[direction].setdefault("round", 1)
        p[direction].setdefault("completed_word_ids", [])
    return p


def get_stats_group(data, group_id):
    return data["stats"]["by_group"].setdefault(group_id, {
        "cn_to_en_answered": 0, "cn_to_en_correct": 0,
        "en_to_cn_answered": 0, "en_to_cn_correct": 0,
        "new_word_answered": 0, "new_word_correct": 0,
    })


# ============================================================
# Sampling and answer checking
# ============================================================
def sampling_weight(record, direction):
    if direction == "cn_to_en":
        base = safe_int(record.get("cn_to_en_weight", 3), 3, 1, 20)
        unseen = safe_int(record.get("cn_to_en_not_seen", 0), 0, 0)
    else:
        base = safe_int(record.get("en_to_cn_weight", 3), 3, 1, 20)
        unseen = safe_int(record.get("en_to_cn_not_seen", 0), 0, 0)
    if unseen < 3:
        bonus = 0
    elif unseen < 6:
        bonus = 0.5
    elif unseen < 11:
        bonus = 1
    elif unseen < 21:
        bonus = 2
    elif unseen < 31:
        bonus = 3
    else:
        bonus = 4
    return base + bonus


def weighted_pick(data, group_id, word_ids, direction):
    candidates = []
    weights = []
    for wid in word_ids:
        w = get_word(data, wid)
        if not w:
            continue
        rec = get_record(data, group_id, wid)
        candidates.append(w)
        weights.append(sampling_weight(rec, direction))
    if not candidates:
        return None
    return random.choices(candidates, weights=weights, k=1)[0]


def normalized_answer(s):
    s = str(s or "").strip().lower()
    s = re.sub(r"[.!?]+$", "", s)
    s = re.sub(r"\s+", " ", s)
    return s


def accepted_answers(word):
    values = [word.get("english", "")]
    # Optional accepted answers can be separated by semicolon or comma.
    for key in ("synonyms", "accepted_answers"):
        raw = word.get(key, "")
        if isinstance(raw, list):
            values.extend(raw)
        elif raw:
            values.extend(re.split(r"[;,]", str(raw)))
    return {normalized_answer(v) for v in values if normalized_answer(v)}


def is_correct(user_answer, word, direction):
    if direction == "en_to_cn":
        expected = normalized_answer(word.get("chinese", ""))
        given = normalized_answer(user_answer)
        return given == expected
    return normalized_answer(user_answer) in accepted_answers(word)


def apply_result(data, group_id, word, direction, correct):
    rec = get_record(data, group_id, word["id"])
    stats = get_stats_group(data, group_id)
    if direction == "cn_to_en":
        stats["cn_to_en_answered"] += 1
        rec["cn_to_en_not_seen"] = 0
        if correct:
            stats["cn_to_en_correct"] += 1
            rec["cn_to_en_correct"] += 1
            rec["cn_to_en_weight"] = max(1, safe_int(rec["cn_to_en_weight"], 3) - 1)
        else:
            rec["cn_to_en_wrong"] += 1
            rec["cn_to_en_weight"] = min(20, safe_int(rec["cn_to_en_weight"], 3) + 2)
    else:
        stats["en_to_cn_answered"] += 1
        rec["en_to_cn_not_seen"] = 0
        if correct:
            stats["en_to_cn_correct"] += 1
            rec["en_to_cn_correct"] += 1
            rec["en_to_cn_weight"] = max(1, safe_int(rec["en_to_cn_weight"], 3) - 1)
        else:
            rec["en_to_cn_wrong"] += 1
            rec["en_to_cn_weight"] = min(20, safe_int(rec["en_to_cn_weight"], 3) + 2)


def increment_unseen(data, group_id, eligible_ids, chosen_id, direction):
    key = "cn_to_en_not_seen" if direction == "cn_to_en" else "en_to_cn_not_seen"
    for wid in eligible_ids:
        rec = get_record(data, group_id, wid)
        if wid == chosen_id:
            rec[key] = 0
        else:
            rec[key] = safe_int(rec.get(key, 0), 0, 0) + 1


def render_audio(text, lang="en-GB", key=None):
    # HTML audio uses the browser's speech synthesis, avoiding external API keys.
    # Audio is best-effort and depends on the browser's installed voices.
    escaped = json.dumps(str(text))
    lang_js = json.dumps(lang)
    st.components.v1.html(
        f"""
        <button id="speak_{key or 'word'}" style="padding:6px 12px;border-radius:8px;cursor:pointer;">
          🔊 发音
        </button>
        <script>
        const btn = document.getElementById("speak_{key or 'word'}");
        btn.onclick = () => {{
          if (!("speechSynthesis" in window)) {{ alert("当前浏览器不支持语音合成"); return; }}
          window.speechSynthesis.cancel();
          const utterance = new SpeechSynthesisUtterance({escaped});
          utterance.lang = {lang_js};
          utterance.rate = 0.85;
          window.speechSynthesis.speak(utterance);
        }};
        </script>
        """,
        height=45,
    )


# ============================================================
# Load state
# ============================================================
if not GITHUB_TOKEN:
    st.error("未配置 GitHub Token。请在 Streamlit Cloud → Settings → Secrets 添加：")
    st.code('GITHUB_TOKEN = "你的 GitHub token"\nGITHUB_OWNER = "ojoj0307"\nGITHUB_REPO = "Vocabulary"\nGITHUB_BRANCH = "master"')
    st.stop()

if "app_data" not in st.session_state:
    try:
        with st.spinner("正在读取词库和学习记录…"):
            st.session_state.app_data = load_all()
    except Exception as exc:
        st.error(f"加载数据失败：{exc}")
        st.info("请检查仓库名称、分支、Token 的 Contents 读写权限，以及 JSON 文件格式。")
        st.stop()

data = st.session_state.app_data


def persist(*keys):
    try:
        for key in keys:
            save_data(key, data)
        st.session_state.app_data = data
        st.toast("已保存到 GitHub", icon="✅")
        return True
    except Exception as exc:
        st.error(f"保存失败：{exc}")
        st.warning("本次修改仍留在当前会话内，请勿关闭页面；修复 GitHub 配置后再尝试保存。")
        return False


# Save newly created migration files on explicit action only, not silently at app startup.
with st.sidebar:
    st.title("📚 Vocabulary")
    pages = ["🏠 首页", "🆕 新词系统", "🔁 复习系统", "📖 词库管理", "🗂️ 组别管理", "📊 学习统计", "🛠️ 数据迁移"]
    page = st.radio("导航", pages)
    group_names = get_group_names(data)
    st.caption(f"数据仓库：{GITHUB_OWNER}/{GITHUB_REPO} · {GITHUB_BRANCH}")
    st.caption(f"词汇总数：{len(data['words'])}")


# ============================================================
# Home
# ============================================================
if page == "🏠 首页":
    st.title("Vocabulary App")
    st.write("词库管理、每日新词轮次练习，以及按组别独立统计的复习系统。")
    c1, c2, c3 = st.columns(3)
    c1.metric("正式词汇", len(data["words"]))
    c2.metric("组别数量", len(data["groups"]["groups"]))
    c3.metric("今日新词", len(data["new_words"]["words"]))
    st.subheader("今日学习")
    cols = st.columns(2)
    for col, direction, label in [
        (cols[0], "cn_to_en", "中译英"),
        (cols[1], "en_to_cn", "英译中"),
    ]:
        with col:
            total_answered = sum(s.get(f"{direction}_answered", 0) for s in data["stats"]["by_group"].values())
            total_correct = sum(s.get(f"{direction}_correct", 0) for s in data["stats"]["by_group"].values())
            rate = total_correct / total_answered * 100 if total_answered else 0
            st.metric(f"{label}今日答题", total_answered, help="所有组别合计")
            st.metric(f"{label}今日正确率", f"{rate:.1f}%")
    st.info("首次使用新版本时，请先进入「数据迁移」完成备份与新结构初始化。")


# ============================================================
# New words
# ============================================================
elif page == "🆕 新词系统":
    st.title("🆕 每日新词")
    st.caption("新词轮次按组别、日期和翻译方向分别计算。答对才完成本轮该词；答错仍留在本轮。")
    names = get_group_names(data)
    selected_group = st.selectbox(
        "新词练习组别",
        list(names.keys()),
        format_func=lambda x: names[x],
        key="new_group",
    )
    words_by_id = {w["id"]: w for w in data["words"]}
    new_ids = [wid for wid in data["new_words"]["words"] if wid in words_by_id]
    group_ids = group_word_ids(data, selected_group)
    # New-word candidates are today's new words assigned to this group.
    new_ids = [wid for wid in new_ids if wid in group_ids]
    with st.expander("添加今日新词", expanded=False):
        with st.form("add_new_word_form", clear_on_submit=True):
            english = st.text_input("英文单词 *")
            chinese = st.text_input("中文释义 *")
            category = st.selectbox("词性", CATEGORIES)
            cn_note = st.text_input("中文备注")
            en_note = st.text_input("英文备注")
            submitted = st.form_submit_button("添加到今日新词和默认词库")
        if submitted:
            if not english.strip() or not chinese.strip():
                st.error("英文单词和中文释义不能为空。")
            else:
                wid = stable_id(english, chinese)
                existing = get_word(data, wid)
                if existing is None:
                    new_word = normalize_word({
                        "id": wid, "english": english, "chinese": chinese,
                        "category": category, "cn_note": cn_note, "en_note": en_note,
                    })
                    data["words"].append(new_word)
                if wid not in data["new_words"]["words"]:
                    data["new_words"]["words"].append(wid)
                add_membership(data, wid, DEFAULT_GROUP_ID)
                # If the user selected a non-default group, also assign the word there.
                if selected_group != DEFAULT_GROUP_ID:
                    add_membership(data, wid, selected_group)
                persist("vocabulary", "new_words", "memberships", "learning")
                st.rerun()

    if new_ids:
        st.subheader(f"今日新词列表（{len(new_ids)}）")
        for idx, wid in enumerate(new_ids):
            w = words_by_id[wid]
            left, mid, right = st.columns([3, 3, 1])
            with left:
                st.markdown(f"**{w['english']}**")
                render_audio(w["english"], key=f"new_{idx}")
            with mid:
                st.write(w["chinese"])
                st.caption(w.get("category", ""))
            with right:
                if st.button("移出今日", key=f"remove_new_{wid}"):
                    data["new_words"]["words"] = [x for x in data["new_words"]["words"] if x != wid]
                    persist("new_words")
                    st.rerun()
    else:
        st.info("这个组别目前没有今日新词。新增词汇会默认进入默认词库。")

    st.divider()
    st.subheader("轮次练习")
    if not new_ids:
        st.info("请先添加今日新词，并确保它们属于所选组别。")
    else:
        direction_label = st.radio("练习方向", ["中译英", "英译中"], horizontal=True, key="new_direction")
        direction = "cn_to_en" if direction_label == "中译英" else "en_to_cn"
        progress = get_progress(data, selected_group)[direction]
        # Progress applies only to this group and today's list.
        completed = set(progress["completed_word_ids"]) & set(new_ids)
        remaining = [wid for wid in new_ids if wid not in completed]
        total = len(new_ids)
        st.progress(len(completed) / total if total else 0)
        st.write(f"第 **{progress['round']}** 轮 · 本轮完成 **{len(completed)}/{total}** · 尚未完成 **{len(remaining)}**")
        if not remaining:
            st.success(f"第 {progress['round']} 轮完成！下一轮将重新练习全部今日新词。")
            if st.button("开始下一轮", type="primary"):
                progress["round"] += 1
                progress["completed_word_ids"] = []
                persist("progress")
                st.rerun()
        else:
            current_id_key = f"new_current_{selected_group}_{direction}"
            if st.session_state.get(current_id_key) not in remaining:
                picked = weighted_pick(data, selected_group, remaining, direction)
                st.session_state[current_id_key] = picked["id"] if picked else None
            current_id = st.session_state.get(current_id_key)
            word = get_word(data, current_id) if current_id else None
            if word:
                prompt = word["chinese"] if direction == "cn_to_en" else word["english"]
                st.markdown(f"<div class='word-title'>{prompt}</div>", unsafe_allow_html=True)
                if direction == "en_to_cn":
                    render_audio(word["english"], key=f"question_{current_id}")
                with st.form(f"new_answer_form_{selected_group}_{direction}_{current_id}"):
                    answer = st.text_input("你的答案", key=f"new_answer_{selected_group}_{direction}_{current_id}")
                    submit = st.form_submit_button("提交答案", type="primary")
                if submit:
                    correct = is_correct(answer, word, direction)
                    apply_result(data, selected_group, word, direction, correct)
                    stats = get_stats_group(data, selected_group)
                    stats["new_word_answered"] += 1
                    if correct:
                        stats["new_word_correct"] += 1
                        if current_id not in progress["completed_word_ids"]:
                            progress["completed_word_ids"].append(current_id)
                        st.success(f"正确！答案：{word['english'] if direction == 'cn_to_en' else word['chinese']}")
                    else:
                        st.error(f"再试一次。正确答案：{word['english'] if direction == 'cn_to_en' else word['chinese']}")
                    # A wrong answer stays in this round; avoid immediately repeating same item if possible.
                    st.session_state.pop(current_id_key, None)
                    persist("learning", "progress", "stats")
                    st.rerun()


# ============================================================
# Review system
# ============================================================
elif page == "🔁 复习系统":
    st.title("🔁 复习系统")
    names = get_group_names(data)
    group_id = st.selectbox("选择词库组别", list(names.keys()), format_func=lambda x: names[x], key="review_group")
    direction_label = st.radio("练习方向", ["中译英", "英译中"], horizontal=True, key="review_direction")
    direction = "cn_to_en" if direction_label == "中译英" else "en_to_cn"
    group_ids = sorted(group_word_ids(data, group_id))
    if not group_ids:
        st.info("该组别没有词汇，请先在词库管理中添加。")
    else:
        col1, col2 = st.columns(2)
        col1.metric("组内词汇", len(group_ids))
        total_w = sum(sampling_weight(get_record(data, group_id, wid), direction) for wid in group_ids)
        col2.metric("总抽题权重", f"{total_w:.1f}")
        state_key = f"review_current_{group_id}_{direction}"
        if st.session_state.get(state_key) not in group_ids:
            picked = weighted_pick(data, group_id, group_ids, direction)
            st.session_state[state_key] = picked["id"] if picked else None
            if picked:
                increment_unseen(data, group_id, group_ids, picked["id"], direction)
        word = get_word(data, st.session_state.get(state_key))
        if word:
            prompt = word["chinese"] if direction == "cn_to_en" else word["english"]
            st.markdown(f"<div class='word-title'>{prompt}</div>", unsafe_allow_html=True)
            if direction == "en_to_cn":
                render_audio(word["english"], key=f"review_{word['id']}")
            with st.form(f"review_answer_form_{group_id}_{direction}_{word['id']}"):
                answer = st.text_input("你的答案")
                submit = st.form_submit_button("提交答案", type="primary")
            if submit:
                correct = is_correct(answer, word, direction)
                apply_result(data, group_id, word, direction, correct)
                if correct:
                    st.success(f"正确！答案：{word['english'] if direction == 'cn_to_en' else word['chinese']}")
                else:
                    st.error(f"正确答案：{word['english'] if direction == 'cn_to_en' else word['chinese']}")
                st.session_state.pop(state_key, None)
                persist("learning", "stats")
                st.rerun()
        if st.button("跳过此题", key=f"skip_{group_id}_{direction}"):
            st.session_state.pop(state_key, None)
            st.rerun()


# ============================================================
# Vocabulary management
# ============================================================
elif page == "📖 词库管理":
    st.title("📖 词库管理")
    names = get_group_names(data)
    group_id = st.selectbox("管理哪个组别的成员", list(names.keys()), format_func=lambda x: names[x], key="manage_group")
    with st.expander("添加正式词汇", expanded=False):
        with st.form("add_vocab_form", clear_on_submit=True):
            english = st.text_input("英文单词 *", key="vocab_english")
            chinese = st.text_input("中文释义 *", key="vocab_chinese")
            category = st.selectbox("词性", CATEGORIES, key="vocab_category")
            plural = st.text_input("复数形式")
            third_person = st.text_input("第三人称单数")
            past = st.text_input("过去式")
            past_participle = st.text_input("过去分词")
            comparative = st.text_input("比较级")
            superlative = st.text_input("最高级")
            cn_note = st.text_input("中文备注")
            en_note = st.text_input("英文备注")
            submit = st.form_submit_button("添加单词")
        if submit:
            if not english.strip() or not chinese.strip():
                st.error("英文单词和中文释义不能为空。")
            else:
                wid = stable_id(english, chinese)
                w = get_word(data, wid)
                if w is None:
                    w = normalize_word({
                        "id": wid, "english": english, "chinese": chinese, "category": category,
                        "plural": plural, "third_person": third_person, "past": past,
                        "past_participle": past_participle, "comparative": comparative,
                        "superlative": superlative, "cn_note": cn_note, "en_note": en_note,
                    })
                    data["words"].append(w)
                add_membership(data, w["id"], group_id)
                if group_id == DEFAULT_GROUP_ID:
                    # A word created in default group is also available in the default vocabulary.
                    pass
                persist("vocabulary", "memberships", "learning")
                st.rerun()

    group_ids = group_word_ids(data, group_id)
    visible_words = [w for w in data["words"] if w["id"] in group_ids]
    query = st.text_input("搜索英文或中文")
    if query.strip():
        q = query.strip().lower()
        visible_words = [w for w in visible_words if q in w["english"].lower() or q in w["chinese"].lower()]
    st.caption(f"当前组别：{len(visible_words)} 个单词")
    for w in visible_words:
        with st.expander(f"{w['english']} — {w['chinese']}"):
            c1, c2 = st.columns([3, 1])
            with c1:
                render_audio(w["english"], key=f"vocab_{w['id']}")
                st.write(f"词性：{w.get('category', 'other')}")
                st.write(f"中文备注：{w.get('cn_note', '') or '—'}")
                st.write(f"英文备注：{w.get('en_note', '') or '—'}")
                rec = get_record(data, group_id, w["id"])
                st.write(
                    f"中译英：权重 {rec['cn_to_en_weight']} · 正确 {rec['cn_to_en_correct']} · 错误 {rec['cn_to_en_wrong']}"
                )
                st.write(
                    f"英译中：权重 {rec['en_to_cn_weight']} · 正确 {rec['en_to_cn_correct']} · 错误 {rec['en_to_cn_wrong']}"
                )
            with c2:
                other_groups = [g for g in data["groups"]["groups"] if g["id"] != group_id and w["id"] not in group_word_ids(data, g["id"])]
                if other_groups:
                    target = st.selectbox("复制到组别", other_groups, format_func=lambda g: g["name"], key=f"copy_group_{w['id']}")
                    if st.button("添加到组别", key=f"add_group_{w['id']}"):
                        add_membership(data, w["id"], target["id"])
                        persist("memberships", "learning")
                        st.rerun()
                if st.button("从当前组移除", key=f"remove_member_{w['id']}"):
                    remove_membership(data, w["id"], group_id)
                    persist("memberships")
                    st.rerun()
                if st.button("删除单词资料", key=f"delete_word_{w['id']}", disabled=(group_id != DEFAULT_GROUP_ID)):
                    # Delete canonical word only from default group context; keep membership/history elsewhere.
                    data["words"] = [x for x in data["words"] if x["id"] != w["id"]]
                    data["memberships"]["memberships"] = [m for m in data["memberships"]["memberships"] if m["word_id"] != w["id"]]
                    data["new_words"]["words"] = [x for x in data["new_words"]["words"] if x != w["id"]]
                    persist("vocabulary", "memberships", "new_words")
                    st.rerun()


# ============================================================
# Group management
# ============================================================
elif page == "🗂️ 组别管理":
    st.title("🗂️ 组别管理")
    with st.form("create_group_form", clear_on_submit=True):
        group_name = st.text_input("新组别名称")
        create = st.form_submit_button("创建组别")
    if create:
        name = group_name.strip()
        if not name:
            st.error("组别名称不能为空。")
        elif any(g["name"].casefold() == name.casefold() for g in data["groups"]["groups"]):
            st.error("组别名称已存在。")
        else:
            gid = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "group"
            gid = f"{gid}-{hashlib.sha1(name.encode()).hexdigest()[:6]}"
            data["groups"]["groups"].append({"id": gid, "name": name, "created_at": today()})
            persist("groups")
            st.rerun()
    st.divider()
    for group in list(data["groups"]["groups"]):
        with st.container(border=True):
            col1, col2, col3 = st.columns([3, 2, 1])
            with col1:
                st.write(f"**{group['name']}**")
                st.caption(f"ID: {group['id']} · {len(group_word_ids(data, group['id']))} 个单词")
            with col2:
                new_name = st.text_input("重命名", value=group["name"], key=f"rename_{group['id']}")
                if st.button("保存名称", key=f"save_name_{group['id']}"):
                    if new_name.strip() and not any(g["id"] != group["id"] and g["name"].casefold() == new_name.strip().casefold() for g in data["groups"]["groups"]):
                        group["name"] = new_name.strip()
                        persist("groups")
                        st.rerun()
                    else:
                        st.error("名称不能为空或与其他组别重复。")
            with col3:
                if group["id"] != DEFAULT_GROUP_ID and st.button("删除组别", key=f"delete_group_{group['id']}"):
                    data["groups"]["groups"] = [g for g in data["groups"]["groups"] if g["id"] != group["id"]]
                    data["memberships"]["memberships"] = [m for m in data["memberships"]["memberships"] if m["group_id"] != group["id"]]
                    # Keep group_learning records as historical data; they will not be used unless group is recreated with same ID.
                    persist("groups", "memberships")
                    st.rerun()
    st.caption("删除组别不会删除单词资料或其他组别的学习记录。")


# ============================================================
# Statistics
# ============================================================
elif page == "📊 学习统计":
    st.title("📊 学习统计")
    names = get_group_names(data)
    selected = st.selectbox("统计范围", ["全部组别", *list(names.keys())], format_func=lambda x: x if x == "全部组别" else names[x])
    if selected == "全部组别":
        stats_rows = []
        for gid, name in names.items():
            s = data["stats"]["by_group"].get(gid, {})
            stats_rows.append({
                "组别": name,
                "中译英答题": s.get("cn_to_en_answered", 0),
                "中译英正确率": f"{s.get('cn_to_en_correct', 0) / s.get('cn_to_en_answered', 1) * 100:.1f}%" if s.get("cn_to_en_answered", 0) else "—",
                "英译中答题": s.get("en_to_cn_answered", 0),
                "英译中正确率": f"{s.get('en_to_cn_correct', 0) / s.get('en_to_cn_answered', 1) * 100:.1f}%" if s.get("en_to_cn_answered", 0) else "—",
            })
    else:
        s = data["stats"]["by_group"].get(selected, {})
        stats_rows = [{
            "组别": names[selected],
            "中译英答题": s.get("cn_to_en_answered", 0),
            "中译英正确率": f"{s.get('cn_to_en_correct', 0) / s.get('cn_to_en_answered', 1) * 100:.1f}%" if s.get("cn_to_en_answered", 0) else "—",
            "英译中答题": s.get("en_to_cn_answered", 0),
            "英译中正确率": f"{s.get('en_to_cn_correct', 0) / s.get('en_to_cn_answered', 1) * 100:.1f}%" if s.get("en_to_cn_answered", 0) else "—",
        }]
    st.dataframe(stats_rows, use_container_width=True, hide_index=True)
    st.subheader("组别学习记录")
    rows = []
    for key, rec in data["learning"]["records"].items():
        if ":" not in key:
            continue
        gid, wid = key.split(":", 1)
        if selected != "全部组别" and gid != selected:
            continue
        word = get_word(data, wid)
        if not word:
            continue
        rows.append({
            "组别": names.get(gid, gid), "英文": word["english"], "中文": word["chinese"],
            "中译英权重": rec.get("cn_to_en_weight", 3),
            "中译英正确/错误": f"{rec.get('cn_to_en_correct', 0)}/{rec.get('cn_to_en_wrong', 0)}",
            "英译中权重": rec.get("en_to_cn_weight", 3),
            "英译中正确/错误": f"{rec.get('en_to_cn_correct', 0)}/{rec.get('en_to_cn_wrong', 0)}",
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)


# ============================================================
# Data migration and diagnostics
# ============================================================
elif page == "🛠️ 数据迁移":
    st.title("🛠️ 数据迁移与检查")
    st.warning("请先备份 GitHub 仓库中的原始 JSON。初始化会创建/更新新版本数据文件。")
    st.write("本工具会将旧词库的所有单词放入默认词库，并把旧学习记录迁移到默认组；其他组别从独立初始状态开始。")
    st.write("当前数据概况：")
    st.json({
        "words": len(data["words"]),
        "groups": len(data["groups"]["groups"]),
        "memberships": len(data["memberships"]["memberships"]),
        "learning_records": len(data["learning"]["records"]),
        "today_new_words": len(data["new_words"]["words"]),
        "schema_version": SCHEMA_VERSION,
    })
    st.subheader("数据检查")
    problems = []
    ids = [w["id"] for w in data["words"]]
    if len(ids) != len(set(ids)):
        problems.append("存在重复 word_id。")
    known_ids = set(ids)
    for m in data["memberships"]["memberships"]:
        if m.get("word_id") not in known_ids:
            problems.append(f"组别关系引用不存在的单词：{m.get('word_id')}")
        if m.get("group_id") not in get_group_names(data):
            problems.append(f"组别关系引用不存在的组别：{m.get('group_id')}")
    if problems:
        for p in problems:
            st.error(p)
    else:
        st.success("当前内存数据的 ID 和组别关系检查通过。")
    if st.button("备份并初始化新结构", type="primary"):
        try:
            # Write a dated backup of existing raw files before writing migrated files.
            backup_stamp = datetime.now(TZ).strftime("%Y%m%d-%H%M%S")
            backup = {
                "backup_date": datetime.now(TZ).isoformat(),
                "vocabulary": data["words"],
                "new_words": data["new_words"],
                "daily_stats": data["stats"],
            }
            store.write(f"backups/vocabulary-backup-{backup_stamp}.json", backup, "Backup before vocabulary app migration")
            for key in ("vocabulary", "new_words", "daily_stats", "groups", "memberships", "learning", "progress"):
                save_data(key, data, f"Initialize Vocabulary App v{SCHEMA_VERSION}: {key}")
            st.success("备份与初始化成功。原始文件已备份到 backups/。")
        except Exception as exc:
            st.error(f"初始化失败：{exc}")
            st.warning("请检查 GitHub token 的 Contents 读写权限。未能确认成功的文件不要手动删除。")
