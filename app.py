import streamlit as st
import json
import random
import base64
import html
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

st.set_page_config(page_title="English Vocabulary", page_icon="📚", layout="wide", initial_sidebar_state="expanded")

GITHUB_OWNER = "ojoj0307"
GITHUB_REPO = "english-vocabulary"
VOCABULARY_PATH = "vocabulary.json"
NEW_WORDS_PATH = "new_words.json"
DAILY_STATS_PATH = "daily_stats.json"

try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
except Exception:
    GITHUB_TOKEN = ""

GITHUB_API_BASE = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents/"
MALAYSIA_TZ = ZoneInfo("Asia/Kuala_Lumpur")
CATEGORIES = ["noun", "verb", "adjective", "adverb"]

st.markdown("""<style>
.block-container{padding-top:2.5rem;padding-bottom:.5rem;max-width:1150px}
h1{font-size:26px!important;margin-bottom:5px!important} h2{font-size:21px!important} h3{font-size:18px!important}
section[data-testid="stSidebar"] div[role="radiogroup"] label{font-size:19px!important;font-weight:600!important;padding-top:8px!important;padding-bottom:8px!important}
section[data-testid="stSidebar"] p{font-size:18px!important;font-weight:600!important}
.question{font-size:30px;font-weight:600;text-align:center;margin:8px 0 6px;word-break:break-word}
.question-category{font-size:17px;font-weight:500;text-align:center;margin-bottom:12px;opacity:.75}
.previous-question{font-size:24px;font-weight:600;text-align:center;margin:8px 0 6px;word-break:break-word}
.previous-category{font-size:16px;font-weight:500;text-align:center;margin-bottom:12px;opacity:.75}
.answer-text{font-size:16px;margin:5px 0;word-break:break-word}
div[data-testid="stTextInput"] input{font-size:18px;height:42px}
div.stButton>button{min-height:38px;font-size:15px}
.mobile-hint{font-size:13px;opacity:.65;margin-bottom:8px}
@media(max-width:700px){.block-container{padding-top:2.5rem;padding-left:.7rem;padding-right:.7rem}.question{font-size:25px}.question-category{font-size:16px}.previous-question{font-size:21px}.previous-category{font-size:15px}section[data-testid="stSidebar"] div[role="radiogroup"] label{font-size:18px!important}}
</style>""", unsafe_allow_html=True)

def github_headers():
    return {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}

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
        r = requests.get(GITHUB_API_BASE + path, headers=github_headers(), timeout=15)
        if r.status_code == 200:
            obj = r.json()
            return base64.b64decode(obj.get("content","").replace("\n","")).decode("utf-8"), obj.get("sha")
        if r.status_code == 404:
            return None, None
        st.error(f"GitHub API 错误：{r.status_code} {r.text}")
    except Exception as e:
        st.error(f"无法连接 GitHub：{e}")
    return None, None

def github_save_file(path, data, sha=None, message="Update file"):
    if not check_github_token():
        return False
    try:
        text = json.dumps(data, ensure_ascii=False, indent=4)
        payload = {"message": message, "content": base64.b64encode(text.encode()).decode()}
        if sha: payload["sha"] = sha
        r = requests.put(GITHUB_API_BASE + path, headers=github_headers(), json=payload, timeout=15)
        if r.status_code in (200,201): return True
        st.error(f"GitHub API 错误：{r.status_code} {r.text}")
    except Exception as e:
        st.error(f"保存到 GitHub 失败：{e}")
    return False

def get_today():
    return datetime.now(MALAYSIA_TZ).strftime("%Y-%m-%d")

def default_daily_stats():
    return {"date":get_today(),"cn_to_en_answered":0,"cn_to_en_correct":0,"en_to_cn_answered":0,"en_to_cn_correct":0}

def default_new_words():
    return {"date":get_today(),"words":[]}

def blank_fields():
    return {"countable":"","plural":"","third_person":"","past":"","past_participle":"","comparative":"","superlative":"","english_note":"","chinese_note":""}

def normalize_word(w):
    changed = False

    # Preserve old correct/wrong totals if they exist; otherwise derive them.
    old_correct = w.get("correct", None)
    old_wrong = w.get("wrong", None)

    defaults = {
        "english": "", "chinese": "", "category": "noun", "weight": 3,
        "cn_to_en_correct": 0, "cn_to_en_wrong": 0,
        "en_to_cn_correct": 0, "en_to_cn_wrong": 0,
        **blank_fields()
    }

    for k, v in defaults.items():
        if k not in w:
            w[k] = v
            changed = True

    if w.get("category") not in CATEGORIES:
        w["category"] = "noun"
        changed = True

    for k in ["weight", "cn_to_en_correct", "cn_to_en_wrong",
              "en_to_cn_correct", "en_to_cn_wrong"]:
        try:
            w[k] = int(w.get(k, 0))
        except Exception:
            w[k] = 3 if k == "weight" else 0
            changed = True

    if old_correct is None:
        w["correct"] = w["cn_to_en_correct"] + w["en_to_cn_correct"]
        changed = True
    else:
        try:
            w["correct"] = int(old_correct)
        except Exception:
            w["correct"] = w["cn_to_en_correct"] + w["en_to_cn_correct"]
            changed = True

    if old_wrong is None:
        w["wrong"] = w["cn_to_en_wrong"] + w["en_to_cn_wrong"]
        changed = True
    else:
        try:
            w["wrong"] = int(old_wrong)
        except Exception:
            w["wrong"] = w["cn_to_en_wrong"] + w["en_to_cn_wrong"]
            changed = True

    # Empty/optional fields are always strings.
    for k in ["english", "chinese", "category", "countable", "plural",
              "third_person", "past", "past_participle", "comparative",
              "superlative", "english_note", "chinese_note"]:
        if w.get(k) is None:
            w[k] = ""
            changed = True

    return changed

def normalize_vocabulary(data):
    changed = False
    for w in data:
        if normalize_word(w): changed = True
    return changed

def load_words():
    content, sha = github_get_file(VOCABULARY_PATH)
    if content is None:
        st.error("无法读取 GitHub 上的 vocabulary.json"); return [], None
    try: data = json.loads(content)
    except Exception as e:
        st.error(f"vocabulary.json 格式错误：{e}"); return [], sha
    if not isinstance(data,list):
        st.error("vocabulary.json 必须是数组。"); return [], sha
    if normalize_vocabulary(data):
        _, latest_sha = github_get_file(VOCABULARY_PATH)
        if latest_sha and github_save_file(VOCABULARY_PATH,data,latest_sha,"Update vocabulary data structure"):
            _, sha = github_get_file(VOCABULARY_PATH)
    return data, sha

def normalize_new_word(w):
    changed = normalize_word(w)
    # New-word stats are independent; force defaults only when fields are absent.
    return changed

def load_new_words():
    content, sha = github_get_file(NEW_WORDS_PATH)
    if content is None:
        data = default_new_words()
        if github_save_file(NEW_WORDS_PATH,data,None,"Create new words"):
            _, sha = github_get_file(NEW_WORDS_PATH)
        return data, sha
    try: raw = json.loads(content)
    except Exception: raw = default_new_words()
    changed = False
    if isinstance(raw,list): data={"date":get_today(),"words":raw}; changed=True
    elif isinstance(raw,dict): data=raw
    else: data=default_new_words(); changed=True
    if "date" not in data: data["date"]=get_today(); changed=True
    if "words" not in data or not isinstance(data["words"],list): data["words"]=[]; changed=True
    if data["date"] != get_today(): data={"date":get_today(),"words":[]}; changed=True
    for w in data["words"]:
        if normalize_new_word(w): changed=True
    if changed:
        _, latest_sha = github_get_file(NEW_WORDS_PATH)
        if latest_sha and github_save_file(NEW_WORDS_PATH,data,latest_sha,"Update daily new words"):
            _, sha = github_get_file(NEW_WORDS_PATH)
    return data, sha

def load_daily_stats():
    content, sha = github_get_file(DAILY_STATS_PATH)
    if content is None:
        data=default_daily_stats()
        if github_save_file(DAILY_STATS_PATH,data,None,"Create daily statistics"): _,sha=github_get_file(DAILY_STATS_PATH)
        return data,sha
    try: data=json.loads(content)
    except: data=default_daily_stats()
    changed=False
    if data.get("date") != get_today(): data=default_daily_stats(); changed=True
    for k in ["cn_to_en_answered","cn_to_en_correct","en_to_cn_answered","en_to_cn_correct"]:
        if k not in data: data[k]=0; changed=True
    if changed:
        _, latest_sha=github_get_file(DAILY_STATS_PATH)
        if latest_sha and github_save_file(DAILY_STATS_PATH,data,latest_sha,"Update daily statistics"): _,sha=github_get_file(DAILY_STATS_PATH)
    return data,sha

words, vocabulary_sha = load_words()
new_words_data, new_words_sha = load_new_words()
daily_stats, daily_stats_sha = load_daily_stats()
new_words = new_words_data["words"]

def save_words():
    global vocabulary_sha
    _, latest_sha=github_get_file(VOCABULARY_PATH)
    if latest_sha is None: return False
    ok=github_save_file(VOCABULARY_PATH,words,latest_sha,"Update vocabulary")
    if ok: _,vocabulary_sha=github_get_file(VOCABULARY_PATH)
    return ok

def save_new_words():
    global new_words_sha
    new_words_data["date"]=get_today(); new_words_data["words"]=new_words
    _, latest_sha=github_get_file(NEW_WORDS_PATH)
    if latest_sha is None: return False
    ok=github_save_file(NEW_WORDS_PATH,new_words_data,latest_sha,"Update daily new words")
    if ok: _,new_words_sha=github_get_file(NEW_WORDS_PATH)
    return ok

def save_daily_stats():
    global daily_stats_sha
    _, latest_sha=github_get_file(DAILY_STATS_PATH)
    if latest_sha is None: return False
    ok=github_save_file(DAILY_STATS_PATH,daily_stats,latest_sha,"Update daily statistics")
    if ok: _,daily_stats_sha=github_get_file(DAILY_STATS_PATH)
    return ok

def calculate_probability(w, pool=None):
    pool = words if pool is None else pool
    if not pool: return 0
    total=sum(max(1,int(x.get("weight",3))) for x in pool)
    return max(1,int(w.get("weight",3)))/total*100

def get_random_word(pool):
    if not pool: return None
    return random.choices(pool,weights=[max(1,int(w.get("weight",3))) for w in pool],k=1)[0]

def pronunciation_button(text,key):
    encoded=base64.b64encode(str(text).encode()).decode()
    st.components.v1.html(f"""<html><body style="margin:0;background:transparent"><button onclick="speak()" title="British English" style="border:none;background:transparent;cursor:pointer;font-size:21px;padding:2px 6px">🔊</button><script>
    function speak(){{const t=decodeURIComponent(escape(atob("{encoded}")));window.speechSynthesis.cancel();const s=new SpeechSynthesisUtterance(t);s.lang="en-GB";s.rate=.85;window.speechSynthesis.speak(s);}}
    </script></body></html>""",height=35,width=50,scrolling=False)

def word_details(w):
    c=w.get("category","noun")
    if c=="noun":
        status={"countable":"可数","uncountable":"不可数","both":"可数及不可数"}.get(str(w.get("countable","")).lower(),str(w.get("countable","")).strip())
        return [("可数性",status),("复数",w.get("plural",""))]
    if c=="verb":
        return [("第三人称单数",w.get("third_person","")),("过去式",w.get("past","")),("过去分词",w.get("past_participle",""))]
    if c=="adjective":
        return [("比较级",w.get("comparative","")),("最高级",w.get("superlative",""))]
    return []

def render_word_forms(w):
    details = word_details(w)
    if details:
        filled = [f"**{label}：** {value}" for label, value in details if str(value).strip()]
        if filled:
            st.markdown(" · ".join(filled))

def render_note(w, question_type):
    if question_type == "中译英":
        note = str(w.get("chinese_note", "")).strip()
        if note:
            st.info("中文备注：" + note)
    else:
        note = str(w.get("english_note", "")).strip()
        if note:
            st.info("English note: " + note)

def parse_paste(text):
    """Parse tab-separated text copied from Excel/Sheets. Also accepts comma-separated rows."""
    rows=[]
    for line in text.splitlines():
        if not line.strip(): continue
        parts=line.split("\t")
        if len(parts)==1: parts=line.split(",")
        rows.append([p.strip() for p in parts])
    return rows

HEADERS=["word","chinese","pos","countable","plural","third_person","past","past_participle","comparative","superlative","english_note","chinese_note"]

def rows_to_words(text):
    parsed=parse_paste(text)
    if not parsed: return [], "没有检测到内容。"
    # Ignore a header row when it resembles the template.
    first=[x.lower().replace(" ","_") for x in parsed[0]]
    if first and first[0] in ("word","english","英文") and any(x in first for x in ("chinese","中文","pos")):
        parsed=parsed[1:]
    result=[]; errors=[]
    for n,row in enumerate(parsed,1):
        if len(row)<2:
            errors.append(f"第 {n} 行至少需要英文和中文。"); continue
        row=row+[""]*(12-len(row))
        pos=row[2].lower().strip() or "noun"
        if pos not in CATEGORIES:
            errors.append(f"第 {n} 行词性无效：{row[2]}"); continue
        w={"english":row[0],"chinese":row[1],"category":pos,
           "countable":row[3],"plural":row[4],"third_person":row[5],"past":row[6],
           "past_participle":row[7],"comparative":row[8],"superlative":row[9],
           "english_note":row[10],"chinese_note":row[11],"weight":3,
           "cn_to_en_correct":0,"cn_to_en_wrong":0,"en_to_cn_correct":0,"en_to_cn_wrong":0,"correct":0,"wrong":0}
        if not w["english"]: errors.append(f"第 {n} 行英文为空。"); continue
        if not w["chinese"]: errors.append(f"第 {n} 行中文为空。"); continue
        result.append(w)
    return result, errors

def sync_vocab_from_new(old,new):
    for v in words:
        if (v.get("english","").strip().lower()==old.get("english","").strip().lower()
            and v.get("chinese","").strip()==old.get("chinese","").strip()
            and v.get("category","noun")==old.get("category","noun")):
            for k in ["english","chinese","category","countable","plural","third_person","past","past_participle","comparative","superlative","english_note","chinese_note"]:
                v[k]=new.get(k,"")
            return

for key,default in {
    "current_word_index":None,"question_type":"中译英","last_word_index":None,"last_answer":"","last_correct":None,
    "learning_word_index":None,"learning_question_type":"中译英","learning_last_word_index":None,"learning_last_answer":"","learning_last_correct":None,
    "vocab_sort_field":None,"vocab_sort_reverse":False}.items():
    if key not in st.session_state: st.session_state[key]=default

def set_sort(field):
    if st.session_state.vocab_sort_field==field: st.session_state.vocab_sort_reverse=not st.session_state.vocab_sort_reverse
    else: st.session_state.vocab_sort_field=field; st.session_state.vocab_sort_reverse=False

st.title("📚 English Vocabulary")
with st.sidebar:
    page=st.radio("功能",["🎓 学习模式","🎯 练习模式","📚 词库管理","📖 查看词库"])

def add_paste_ui(target, key_prefix):
    st.caption("按下面的顺序从 Excel / Google Sheets 复制并粘贴；列之间必须是 Tab。")
    st.code("word\tchinese\tpos\tcountable\tplural\tthird_person\tpast\tpast_participle\tcomparative\tsuperlative\tenglish_note\tchinese_note",language=None)
    return st.text_area("粘贴表格",height=180,placeholder="application\t申请\tnoun\tcountable\tapplications\t\t\t\t\t\t英文备注\t中文备注",key=key_prefix)

if page=="🎓 学习模式":
    st.header("🎓 学习模式")
    st.subheader("➕ 添加新词")
    paste=add_paste_ui("new_words","learning_paste")
    if st.button("➕ 添加新词",use_container_width=True):
        added_words,errors=rows_to_words(paste)
        added=duplicate=0
        for w in added_words:
            exists_new=any(x.get("english","").strip().lower()==w["english"].lower() and x.get("chinese","").strip()==w["chinese"].strip() and x.get("category","noun")==w["category"] for x in new_words)
            if exists_new: duplicate+=1; continue
            new_words.append(w)
            exists_vocab=any(x.get("english","").strip().lower()==w["english"].lower() and x.get("chinese","").strip()==w["chinese"].strip() and x.get("category","noun")==w["category"] for x in words)
            if not exists_vocab:
                words.append(w.copy())
                words[-1].update({"cn_to_en_correct":0,"cn_to_en_wrong":0,"en_to_cn_correct":0,"en_to_cn_wrong":0,"correct":0,"wrong":0})
            added+=1
        if errors:
            for e in errors if isinstance(errors,list) else [errors]: st.error(e)
        if added:
            if save_new_words() and save_words(): st.success(f"成功添加 {added} 个新词，并已同步到正式词库。"); st.rerun()
        if duplicate: st.info(f"{duplicate} 个今天已经存在的新词没有重复添加。")
    st.divider()
    if not new_words: st.info("今天还没有新词，请先添加新词。")
    else:
        st.caption(f"今天共有 {len(new_words)} 个新词")
        qt=st.radio("题型",["中译英","英译中"],horizontal=True,key="learning_qt")
        if qt!=st.session_state.learning_question_type:
            st.session_state.learning_question_type=qt; st.session_state.learning_word_index=None; st.session_state.learning_last_word_index=None; st.session_state.learning_last_answer=""; st.session_state.learning_last_correct=None
        if st.session_state.learning_word_index is None or st.session_state.learning_word_index>=len(new_words):
            selected=get_random_word(new_words); st.session_state.learning_word_index=new_words.index(selected)
        i=st.session_state.learning_word_index; w=new_words[i]; cat=w.get("category","noun")
        left,right=st.columns(2,gap="large")
        with left:
            st.markdown("### 上一题")
            li=st.session_state.learning_last_word_index
            if li is None: st.caption("开始答题后显示上一题")
            elif li<len(new_words):
                last=new_words[li]
                q=last["chinese"] if qt=="中译英" else last["english"]
                st.markdown(f'<div class="previous-question">{html.escape(q)}</div><div class="previous-category">{html.escape(last.get("category","noun"))}</div>',unsafe_allow_html=True)
                if qt=="英译中": pronunciation_button(last["english"],"learning_last_en_cn")
                st.markdown(f'<div class="answer-text">你的答案：<b>{html.escape(st.session_state.learning_last_answer)}</b></div>',unsafe_allow_html=True)
                correct=last["english"] if qt=="中译英" else last["chinese"]
                st.markdown(f'<div class="answer-text">正确答案：<b>{html.escape(correct)}</b></div>',unsafe_allow_html=True)
                if qt=="中译英" and last.get("chinese_note"): st.info("中文备注：" + str(last["chinese_note"]))
                if qt=="英译中":
                    pronunciation_button(last["english"],"learning_last_en_cn2")
                    render_word_forms(last)
                    render_note(last, qt)
                (st.success("正确",icon="✅") if st.session_state.learning_last_correct else st.error("错误",icon="❌"))
        with right:
            st.markdown("### 下一题")
            q=w["chinese"] if qt=="中译英" else w["english"]
            st.markdown(f'<div class="question">{html.escape(q)}</div><div class="question-category">{html.escape(cat)}</div>',unsafe_allow_html=True)
            if qt=="英译中": pronunciation_button(w["english"],"learning_current")
            with st.form("learning_answer_form",clear_on_submit=True):
                ans=st.text_input("答案",label_visibility="collapsed",placeholder="输入答案后按 Enter",autocomplete="off")
                submitted=st.form_submit_button("提交",use_container_width=True)
            if submitted:
                ans=ans.strip()
                if not ans: st.warning("请输入答案后再提交。"); st.stop()
                correct=(ans.lower()==w["english"].strip().lower()) if qt=="中译英" else (ans==w["chinese"].strip())
                w["weight"]=max(1,int(w.get("weight",3))-1) if correct else min(20,int(w.get("weight",3))+2)
                ok=save_new_words()
                st.session_state.learning_last_word_index=i; st.session_state.learning_last_answer=ans; st.session_state.learning_last_correct=correct
                nxt=get_random_word(new_words); st.session_state.learning_word_index=new_words.index(nxt)
                if not ok: st.error("⚠️ 新词数据保存失败，请检查 GitHub Token 权限。")
                st.rerun()
    st.divider(); st.subheader("✏️ 编辑列表")
    search=st.text_input("🔍 搜索新词",placeholder="输入英文或中文",key="new_word_edit_search")
    for i,w in enumerate(new_words):
        if search and search.lower() not in w.get("english","").lower() and search not in w.get("chinese",""): continue
        with st.expander(f"{w['english']} → {w['chinese']} ({w.get('category','noun')})"):
            c1,c2=st.columns(2)
            with c1: en=st.text_input("英文",w["english"],key=f"ne{i}"); cn=st.text_input("中文",w["chinese"],key=f"nc{i}")
            with c2:
                cat=st.selectbox("词性",CATEGORIES,index=CATEGORIES.index(w.get("category","noun")) if w.get("category") in CATEGORIES else 0,key=f"ncat{i}")
            detail_text=st.text_area("词性资料 / 备注（可留空）",value="\t".join([w.get(k,"") for k in ["countable","plural","third_person","past","past_participle","comparative","superlative","english_note","chinese_note"]]),key=f"nd{i}",height=100)
            st.caption(f"独立权重：{w.get('weight',3)}　抽题概率：{calculate_probability(w,new_words):.2f}%")
            a,b=st.columns(2)
            with a:
                if st.button("💾 保存",key=f"ns{i}",use_container_width=True):
                    vals=(detail_text.split("\t")+[""]*9)[:9]
                    old=w.copy(); w.update({"english":en.strip(),"chinese":cn.strip(),"category":cat})
                    for k,v in zip(["countable","plural","third_person","past","past_participle","comparative","superlative","english_note","chinese_note"],vals): w[k]=v.strip()
                    sync_vocab_from_new(old,w)
                    if save_new_words() and save_words(): st.success("修改成功，并已同步到正式词库。"); st.rerun()
            with b:
                if st.button("🗑️ 删除",key=f"ndel{i}",use_container_width=True):
                    new_words.pop(i)
                    if save_new_words(): st.success("已从今天的新词列表删除。"); st.rerun()

elif page=="🎯 练习模式":
    st.header("🎯 练习模式")
    if not words: st.warning("词库为空，请先到「词库管理」添加单词。")
    else:
        qt=st.radio("题型",["中译英","英译中"],horizontal=True)
        if qt!=st.session_state.question_type:
            st.session_state.question_type=qt; st.session_state.current_word_index=None; st.session_state.last_word_index=None; st.session_state.last_answer=""; st.session_state.last_correct=None
        if st.session_state.current_word_index is None or st.session_state.current_word_index>=len(words):
            selected=get_random_word(words); st.session_state.current_word_index=words.index(selected)
        i=st.session_state.current_word_index; w=words[i]; cat=w.get("category","noun")
        left,right=st.columns(2,gap="large")
        with left:
            st.markdown("### 上一题"); li=st.session_state.last_word_index
            if li is None: st.caption("开始答题后显示上一题")
            elif li<len(words):
                last=words[li]; q=last["chinese"] if qt=="中译英" else last["english"]
                st.markdown(f'<div class="previous-question">{html.escape(q)}</div><div class="previous-category">{html.escape(last.get("category","noun"))}</div>',unsafe_allow_html=True)
                if qt=="英译中": pronunciation_button(last["english"],"last_en")
                st.markdown(f'<div class="answer-text">你的答案：<b>{html.escape(st.session_state.last_answer)}</b></div>',unsafe_allow_html=True)
                correct=last["english"] if qt=="中译英" else last["chinese"]
                st.markdown(f'<div class="answer-text">正确答案：<b>{html.escape(correct)}</b></div>',unsafe_allow_html=True)
                if qt=="中译英" and last.get("chinese_note"): st.info("中文备注：" + str(last["chinese_note"]))
                if qt=="英译中":
                    render_word_forms(last)
                    render_note(last, qt)
                if st.session_state.last_correct: st.success("正确",icon="✅")
                else:
                    st.error("错误",icon="❌")
                    if st.button("我的答案也是近义词 ✓",key="similar_answer",use_container_width=True):
                        if qt=="中译英":
                            last["cn_to_en_wrong"]=max(0,int(last.get("cn_to_en_wrong",0))-1); last["cn_to_en_correct"]=int(last.get("cn_to_en_correct",0))+1; daily_stats["cn_to_en_correct"]+=1
                        else:
                            last["en_to_cn_wrong"]=max(0,int(last.get("en_to_cn_wrong",0))-1); last["en_to_cn_correct"]=int(last.get("en_to_cn_correct",0))+1; daily_stats["en_to_cn_correct"]+=1
                        last["correct"]=int(last.get("correct",0))+1; last["wrong"]=max(0,int(last.get("wrong",0))-1); last["weight"]=max(1,int(last.get("weight",3))-2)
                        save_words(); save_daily_stats(); st.session_state.last_correct=True; st.rerun()
        with right:
            st.markdown("### 下一题"); q=w["chinese"] if qt=="中译英" else w["english"]
            st.markdown(f'<div class="question">{html.escape(q)}</div><div class="question-category">{html.escape(cat)}</div>',unsafe_allow_html=True)
            if qt=="英译中": pronunciation_button(w["english"],"current_sound")
            with st.form("answer_form",clear_on_submit=True):
                ans=st.text_input("答案",label_visibility="collapsed",placeholder="输入答案后按 Enter",autocomplete="off")
                submitted=st.form_submit_button("提交",use_container_width=True)
            if submitted:
                ans=ans.strip()
                if not ans: st.warning("请输入答案后再提交。"); st.stop()
                correct=(ans.lower()==w["english"].strip().lower()) if qt=="中译英" else (ans==w["chinese"].strip())
                if qt=="中译英":
                    keyc,keyw="cn_to_en_correct","cn_to_en_wrong"
                else: keyc,keyw="en_to_cn_correct","en_to_cn_wrong"
                if correct: w[keyc]+=1; w["correct"]=int(w.get("correct",0))+1; w["weight"]=max(1,int(w.get("weight",3))-1)
                else: w[keyw]+=1; w["wrong"]=int(w.get("wrong",0))+1; w["weight"]=min(20,int(w.get("weight",3))+2)
                ok=save_words()
                if daily_stats.get("date")!=get_today(): daily_stats=default_daily_stats()
                daily_stats[f"{'cn_to_en' if qt=='中译英' else 'en_to_cn'}_answered"]+=1
                if correct: daily_stats[f"{'cn_to_en' if qt=='中译英' else 'en_to_cn'}_correct"]+=1
                save_daily_stats()
                st.session_state.last_word_index=i; st.session_state.last_answer=ans; st.session_state.last_correct=correct
                nxt=get_random_word(words); st.session_state.current_word_index=words.index(nxt)
                if not ok: st.error("⚠️ 数据保存失败，请检查 GitHub Token 权限。")
                st.rerun()
        st.divider(); st.subheader("📊 今日统计")
        ca=int(daily_stats.get("cn_to_en_answered",0)); cc=int(daily_stats.get("cn_to_en_correct",0)); ea=int(daily_stats.get("en_to_cn_answered",0)); ec=int(daily_stats.get("en_to_cn_correct",0))
        total=ca+ea; totalc=cc+ec
        a,b,c=st.columns(3); a.metric("今日总答数",total); b.metric("中译英",f"{cc} / {ca}"); c.metric("英译中",f"{ec} / {ea}")
        if total: st.caption(f"今日总正确率：{totalc/total*100:.1f}%")

elif page=="📚 词库管理":
    st.header("📚 词库管理")
    st.subheader("➕ 添加单词")
    paste=add_paste_ui("vocabulary","vocab_paste")
    if st.button("➕ 添加",use_container_width=True):
        added_words,errors=rows_to_words(paste); added=dup=0
        for w in added_words:
            exists=any(x.get("english","").strip().lower()==w["english"].lower() and x.get("chinese","").strip()==w["chinese"].strip() and x.get("category","noun")==w["category"] for x in words)
            if exists: dup+=1; continue
            words.append(w); added+=1
        for e in errors if isinstance(errors,list) else [errors]: st.error(e)
        if added and save_words(): st.success(f"成功添加 {added} 个单词，并已同步到 GitHub。"); st.rerun()
        if dup: st.info(f"{dup} 个完全相同的单词没有添加。")
    st.divider(); st.subheader("✏️ 编辑词库")
    search=st.text_input("🔍 搜索",placeholder="输入英文或中文",key="vocabulary_edit_search")
    for i,w in enumerate(words):
        if search and search.lower() not in w.get("english","").lower() and search not in w.get("chinese",""): continue
        with st.expander(f"{w['english']} → {w['chinese']} ({w.get('category','noun')})"):
            c1,c2=st.columns(2)
            with c1: en=st.text_input("英文",w["english"],key=f"edit_en_{i}"); cn=st.text_input("中文",w["chinese"],key=f"edit_cn_{i}")
            with c2: cat=st.selectbox("词性",CATEGORIES,index=CATEGORIES.index(w.get("category","noun")) if w.get("category") in CATEGORIES else 0,key=f"edit_cat_{i}")
            detail=st.text_area("词性资料 / 备注（可留空）",value="\t".join([w.get(k,"") for k in ["countable","plural","third_person","past","past_participle","comparative","superlative","english_note","chinese_note"]]),key=f"detail_{i}",height=100)
            st.caption(f"权重：{w.get('weight',3)}")
            st.caption(f"中译英：✓ {w.get('cn_to_en_correct',0)} / ✗ {w.get('cn_to_en_wrong',0)}　英译中：✓ {w.get('en_to_cn_correct',0)} / ✗ {w.get('en_to_cn_wrong',0)}　抽题概率：{calculate_probability(w):.2f}%")
            a,b=st.columns(2)
            with a:
                if st.button("💾 保存",key=f"save_{i}",use_container_width=True):
                    vals=(detail.split("\t")+[""]*9)[:9]; w["english"]=en.strip(); w["chinese"]=cn.strip(); w["category"]=cat
                    for k,v in zip(["countable","plural","third_person","past","past_participle","comparative","superlative","english_note","chinese_note"],vals): w[k]=v.strip()
                    if save_words(): st.success("修改成功，并已同步到 GitHub。"); st.rerun()
            with b:
                if st.button("🗑️ 删除",key=f"delete_{i}",use_container_width=True):
                    words.pop(i)
                    if save_words(): st.success("删除成功，并已同步到 GitHub。"); st.rerun()

elif page=="📖 查看词库":
    st.header("📖 我的词库")
    if not words: st.info("目前没有单词。")
    else:
        search=st.text_input("🔍 搜索词库",placeholder="输入英文或中文",key="view_vocab_search")
        filt=st.selectbox("词性筛选",["全部"]+CATEGORIES,key="view_category_filter")
        filtered=[w for w in words if (not search or search.lower() in w.get("english","").lower() or search in w.get("chinese","")) and (filt=="全部" or w.get("category","noun")==filt)]
        st.caption(f"找到 {len(filtered)} 个单词")
        sf=st.session_state.vocab_sort_field; rev=st.session_state.vocab_sort_reverse
        keys={"english":lambda x:x.get("english","").lower(),"chinese":lambda x:x.get("chinese",""),"category":lambda x:x.get("category",""),"weight":lambda x:int(x.get("weight",3)),"probability":lambda x:calculate_probability(x),"correct":lambda x:int(x.get("cn_to_en_correct",0))+int(x.get("en_to_cn_correct",0)),"wrong":lambda x:int(x.get("cn_to_en_wrong",0))+int(x.get("en_to_cn_wrong",0))}
        if sf: filtered.sort(key=keys[sf],reverse=rev)
        def sl(field,label):
            return label+(" ↓" if rev and sf==field else " ↑" if sf==field else "")
        cols=st.columns([2,2,1.2,.9,1.2,.8,.8])
        for col,field,label in zip(cols,["english","chinese","category","weight","probability","correct","wrong"],["英文","中文","词性","权重","概率","✓","✗"]):
            if col.button(sl(field,label),key=f"sort_{field}",use_container_width=True): set_sort(field); st.rerun()
        st.markdown('<div class="mobile-hint">📱 手机可以左右滑动查看完整词库</div>',unsafe_allow_html=True)
        rows=""
        for w in filtered:
            vals=[html.escape(str(w.get("english",""))),html.escape(str(w.get("chinese",""))),html.escape(str(w.get("category","noun"))),str(int(w.get("weight",3))),f"{calculate_probability(w):.2f}%",str(int(w.get("cn_to_en_correct",0))+int(w.get("en_to_cn_correct",0))),str(int(w.get("cn_to_en_wrong",0))+int(w.get("en_to_cn_wrong",0)))]
            rows+="<tr>"+ "".join(f"<td>{v}</td>" for v in vals)+"</tr>"
        table=f"""<div style="width:100%;overflow-x:auto;border:1px solid #d9d9d9;border-radius:10px"><table style="width:100%;min-width:720px;border-collapse:collapse"><thead><tr>{''.join(f'<th style="padding:10px 8px;text-align:left;background:#f3f4f6;border-bottom:2px solid #cfcfcf">{x}</th>' for x in ["英文","中文","词性","权重","概率","✓","✗"])}</tr></thead><tbody>{rows}</tbody></table></div>"""
        st.components.v1.html(table,height=max(120,min(800,65+len(filtered)*44)),scrolling=True)
