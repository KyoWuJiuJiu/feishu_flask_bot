from feishu import _parse_task_line_multi,_shrink_to_task_status
line="@ou_dd62b0f0c5a1e99269b55104a234d27a, 插件-Apple/MS Task抓取, 阅读swift extension的document., 未完成"
uids, txt = _parse_task_line_multi(line)
print(uids)
print(txt)
print(_shrink_to_task_status(txt))
