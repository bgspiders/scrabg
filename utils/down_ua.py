import requests
# 手动下载 https://gitea.bgspider.com/bgspider/user-agents/raw/branch/main/src/user-agents.json.gz
# 解压文件，得到 user-agents.json，然后运行下面代码，将结果复制到user_agents.py替换之前的ua
with open('./user-agents.json', 'r') as f:
    user_agents = json.load(f)
user_agents_list=[]
for ua in user_agents:
    if ua['deviceCategory']=='desktop':
        if 'Mac' in ua['platform'] or 'Win' in ua['platform']:
            user_agents_list.append(ua['userAgent'])
user_agents_list=list(set(user_agents_list))
print(user_agents_list)
