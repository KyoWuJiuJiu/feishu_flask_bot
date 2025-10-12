from feishu import _parse_task_line_multi, build_post_zh_cn_from_sections
summary = '''明日任务:
@ou_dd62b0f0c5a1e99269b55104a234d27a, 插件-Apple/MS Task抓取, 阅读swift extension的document., 未完成
@ou_dd62b0f0c5a1e99269b55104a234d27a, 插件-Apple/MS Task抓取, 建立swift的开发环境, 未完成
@ou_dd62b0f0c5a1e99269b55104a234d27a, 插件-Apple/MS Task抓取, 先建立函数和多维表格的API打通, 需要哪些API?, 未完成
'''
lines = [ln.strip() for ln in summary.splitlines() if ln.strip()]
# Simplified: take lines starting with '@' as today
today_raw = [ln for ln in lines if ln.startswith('@')]
items = []
for ln in today_raw:
    uids, txt = _parse_task_line_multi(ln)
    items.append({'user_ids': uids, 'text': txt})
zh = build_post_zh_cn_from_sections(title='调试', date_label='明日', today_items=items, week_items=[])
print(zh)
