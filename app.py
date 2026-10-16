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
