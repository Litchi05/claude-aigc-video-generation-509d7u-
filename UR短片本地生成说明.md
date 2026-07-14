# UR 时尚女装「都市即秀场」AIGC 短片 · 本地一键生成说明

沙盒环境连不上 `api.x.ai`（被网络策略拦截），所以真实生成要在你本地跑。
脚本 `generate_video_ur.py` 已写好，全流程自动：调用 xAI 生成 9 个镜头 → 下载 → ffmpeg 拼成 35 秒竖屏成片。

## 一、准备环境（只需一次）

```bash
# 1. Python 依赖
pip install requests

# 2. ffmpeg（拼接用）
#   macOS:   brew install ffmpeg
#   Windows: winget install Gyan.FFmpeg   或去 ffmpeg.org 下载
#   Linux:   sudo apt install ffmpeg
ffmpeg -version   # 能打印版本就说明装好了
```

## 二、放这些东西到脚本同目录

1. `generate_video_ur.py`（本脚本）
2. **可选**：`look1.jpg`（日装/风衣造型图，镜头 3 用）、`look2.jpg`（夜装/缎面裙造型图，镜头 7 用）
   —— 有图就走"图生视频"锁定真实服装款式；缺图会自动降级为文生视频，不影响跑通。

## 三、设置 API Key 并运行

```bash
export XAI_API_KEY="xai-你的key"          # Windows PowerShell: $env:XAI_API_KEY="xai-..."
python3 generate_video_ur.py
```

跑完会得到：
- `shots_ur/`  —— 每个镜头的 mp4
- `final_output_ur.mp4` —— 拼好的完整成片（已去音轨，方便你导入剪映统一配乐+加字幕）

## 四、常用参数

```bash
# 断点续跑：跳过已生成的镜头
python3 generate_video_ur.py --skip-existing

# 只重跑某几个镜头（比如第 3、6、8 个不满意）
python3 generate_video_ur.py --only 3,6,8

# 换用 1.5 模型
python3 generate_video_ur.py --model grok-imagine-video-1.5
```

## 五、分镜结构（共 35s，9:16 竖屏）

| # | 镜头 | 类型 | 时长 |
|---|------|------|------|
| 1 | 城市晨光 · 剪影开场 | t2v | 3s |
| 2 | 衣杆滑动 · 面料特写 | t2v | 4s |
| 3 | 风衣街拍 · 大步走位 | i2v（look1.jpg，可选） | 4s |
| 4 | 转身扬摆 · 织纹微距 | t2v | 4s |
| 5 | 标题卡 ONE CITY / THREE LOOKS | card（ffmpeg） | 3s |
| 6 | 粒子换装转场 ★ 全片记忆点 | t2v | 5s |
| 7 | 缎面夜装 · 霓虹回眸 | i2v（look2.jpg，可选） | 4s |
| 8 | 三造型走秀合集 | t2v | 5s |
| 9 | 收尾 Logo：URBAN REVIVO | card（ffmpeg） | 3s |

## 六、说明

- **标题卡（镜头5）和收尾 Logo 定版（镜头9）** 不适合 AI 生成，脚本里直接用 ffmpeg
  生成了黑底白字卡片（贴合 UR 黑白极简风），保证一条命令跑通。
  想做更精致的动效可在剪映里替换这两段。
- **人物一致性**：镜头 3/4/6/7/8 都涉及同一位模特。文生视频难以完全保证同脸，
  建议：① 先跑镜头 3 挑一个满意的模特形象；② 把该镜头截帧存为 look1.jpg / look2.jpg
  再用 i2v 重跑后续镜头，能显著提升一致性。
- **计费**：每个镜头都会消耗 xAI 账户额度，9 个镜头里有 7 个走 API（镜头 5、9 不走）。
  建议先 `--only 1` 试跑一个镜头，确认效果和扣费正常，再整体跑。
- **字段兼容**：脚本对返回字段（request_id / status / url）做了多种命名兼容；
  万一 xAI 接口有细微调整报错，错误信息会打印完整返回，照着调一下 body 字段即可。
- **后期建议**：成片已去音轨。配乐建议选节奏感强的 Electro/House（BPM 110-125），
  镜头 5 标题卡处正好卡一个 Drop；字幕只在镜头 8 加一句卖点即可，保持画面干净。
