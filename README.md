# jd-login
无界插件对应京东登录

包括账密登录和密码登录
可以直接纯净docker部署 使用compose代码如下（可自行加前缀代理）
```
version: "3"
services:
  jd_autologin:
    image: python:3.12.4
    container_name: jd_autologin
    restart: unless-stopped
    ports:
      - 12345:12345
    working_dir: /app
    environment:
      TZ: Asia/Shanghai
    command: >
      sh -c "apt -y update && apt -y install libnss3 libnspr4 libatk1.0-0
      libatk-bridge2.0-0 libcups2 libdrm2 libdbus-1-3 libxkbcommon0
      libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2
      libatspi2.0-0 libxshmfence1 && python -m pip install --upgrade pip && pip
      install pyppeteer Pillow asyncio aiohttp opencv-python-headless ddddocr
      quart && rm -rf && wget -O api.py
      https://raw.githubusercontent.com/zhao-zg/jd-login/main/api.py
      && wget -O login.py
      https://raw.githubusercontent.com/zhao-zg/jd-login/main/login.py
      && python api.py"
networks: {}

```

# 感谢作者小九九
