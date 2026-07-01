#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
雅丽洁「水感美白防晒乳」AIGC概念短片 —— 一键生成脚本
=====================================================

功能：调用 xAI Grok Imagine 视频接口，按分镜脚本生成 7 个镜头，
      下载后用 ffmpeg 拼接成 33 秒竖屏（9:16）成片。

依赖：
    pip install requests
    ffmpeg（系统需已安装，命令行能跑 `ffmpeg -version`）

用法：
    export XAI_API_KEY="xai-你的key"
    # 把产品白底图存成同目录下的 product.jpg（镜头2、3用它做图生视频）
    python3 generate_video.py

    可选参数：
    python3 generate_video.py --model grok-imagine-video-1.5   # 换模型
    python3 generate_video.py --skip-existing                  # 跳过已下载的镜头，断点续跑
    python3 generate_video.py --only 1,3,6                     # 只重跑指定镜头

产出：
    ./shots/           每个镜头的 mp4
    ./final_output.mp4 拼接好的完整成片
"""

import os
import sys
import time
import json
import base64
import argparse
import subprocess
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("缺少 requests，请先运行：pip install requests")

API_BASE = "https://api.x.ai/v1"
HERE = Path(__file__).resolve().parent
SHOTS_DIR = HERE / "shots"
PRODUCT_IMG = HERE / "product.jpg"   # 产品白底图，镜头2/3用
FINAL = HERE / "final_output.mp4"

# 竖屏短视频
ASPECT = "9:16"
RESOLUTION = "720p"

# ---------- 分镜定义 ----------
# kind: "t2v" 文生视频 | "i2v" 图生视频（需 product.jpg）| "card" ffmpeg文字卡片（不调API）
SHOTS = [
    {
        "id": "01_alarm", "kind": "t2v", "dur": 3,
        "prompt": "特写镜头，数字闹钟显示7:50，晨光从左侧斜射入画面，一只女性的手"
                  "（指甲干净，涂浅色甲油）快速伸入按下闹钟，微焦效果，写实电影质感，暖色调。"
                  "Close-up, digital alarm clock showing 7:50, morning light from the left, "
                  "a woman's hand with clean light-polished nails presses the alarm, shallow "
                  "focus, cinematic realism, warm tones, vertical 9:16.",
    },
    {
        "id": "02_bottle", "kind": "i2v", "dur": 4,
        "prompt": "产品缓慢旋转展示，白色瓶身搭配橙色瓶盖，柔光扫过表面高光闪烁，背景白色丝绸质感"
                  "缓慢流动，商业级摄影布光，慢动作，4K质感。Product slowly rotating, white bottle "
                  "with orange cap, soft light sweeping across the surface, flowing white silk "
                  "background, commercial studio lighting, slow motion, vertical 9:16.",
    },
    {
        "id": "03_lotion", "kind": "i2v", "dur": 5,
        "prompt": "白色乳液从瓶口缓缓挤出，落在一只纤细白皙的女性手背上，呈现水润流动质感，微距镜头，"
                  "高帧率慢动作，光线打出乳液的光泽感。White lotion slowly squeezed from the bottle "
                  "onto a slender fair-skinned woman's hand, watery fluid texture, macro shot, "
                  "high frame rate slow motion, glossy sheen, vertical 9:16.",
    },
    {
        "id": "04_apply", "kind": "t2v", "dur": 3,
        "prompt": "女生用指尖轻轻在脸颊侧面打圈推开乳液，动作轻柔自然，皮肤逐渐呈现自然光泽，特写偏侧脸角度，"
                  "柔和自然光，画面唯美清新。A woman gently massages lotion onto her cheek in circular "
                  "motions with fingertips, soft natural movement, skin revealing a natural glow, "
                  "side-face close-up, soft natural light, fresh elegant mood, vertical 9:16.",
    },
    {
        "id": "05_timeflip", "kind": "card", "dur": 3,
        "card_lines": ["7:50", "→", "7:52"],
        "card_sub": "2 分钟，搞定",
    },
    {
        "id": "06_film", "kind": "t2v", "dur": 4,
        "prompt": "涂抹后的女生手臂/脸颊皮肤表面浮现半透明金色光膜，粒子状光效缓缓扩散包裹皮肤，象征防晒保护层，"
                  "光效柔和不刺眼，唯美质感。A translucent golden light film emerges on a woman's skin "
                  "after application, particle-like glow slowly spreading to envelop the skin, "
                  "symbolizing sun protection, soft elegant glow, vertical 9:16.",
    },
    {
        "id": "07_exit", "kind": "t2v", "dur": 6,
        "prompt": "年轻女生转身面向镜头微笑，逆光轮廓勾勒发丝光晕，暖色调阳光洒落，肩背包做出门动作，节奏轻快自然。"
                  "A young woman turns and smiles toward the camera, backlit silhouette with hair "
                  "glowing at the edges, warm sunlight, swinging a bag over her shoulder as she "
                  "heads out, light natural rhythm, vertical 9:16.",
    },
    {
        "id": "08_logo", "kind": "card", "dur": 2,
        "card_lines": ["雅丽洁"],
        "card_sub": "2min，防晒美白都搞定",
    },
]


def api_headers():
    key = os.environ.get("XAI_API_KEY")
    if not key:
        sys.exit("未设置 XAI_API_KEY 环境变量。请先：export XAI_API_KEY=\"xai-...\"")
    return {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}


def img_data_uri(path: Path) -> str:
    raw = path.read_bytes()
    b64 = base64.b64encode(raw).decode()
    ext = path.suffix.lower().lstrip(".") or "jpeg"
    if ext == "jpg":
        ext = "jpeg"
    return f"data:image/{ext};base64,{b64}"


def submit_generation(shot, model):
    """提交生成请求，返回 request_id。"""
    body = {
        "model": model,
        "prompt": shot["prompt"],
        "duration": shot["dur"],
        "aspect_ratio": ASPECT,
        "resolution": RESOLUTION,
    }
    if shot["kind"] == "i2v":
        if not PRODUCT_IMG.exists():
            print(f"  [!] 缺少 {PRODUCT_IMG.name}，镜头 {shot['id']} 降级为文生视频")
        else:
            body["image_url"] = img_data_uri(PRODUCT_IMG)

    resp = requests.post(f"{API_BASE}/videos/generations",
                         headers=api_headers(), json=body, timeout=60)
    if resp.status_code >= 400:
        raise RuntimeError(f"提交失败 HTTP {resp.status_code}: {resp.text}")
    data = resp.json()
    # 兼容不同返回字段命名
    rid = data.get("request_id") or data.get("id")
    if not rid:
        # 有些实现同步直接返回 url
        url = _extract_url(data)
        if url:
            return {"sync_url": url}
        raise RuntimeError(f"返回中找不到 request_id，原始返回：{json.dumps(data)[:500]}")
    return {"request_id": rid}


def _extract_url(data):
    if not isinstance(data, dict):
        return None
    if isinstance(data.get("video"), dict) and data["video"].get("url"):
        return data["video"]["url"]
    for k in ("url", "video_url", "output_url"):
        if data.get(k):
            return data[k]
    if isinstance(data.get("data"), list) and data["data"]:
        return _extract_url(data["data"][0])
    return None


def poll(request_id, timeout_s=600):
    """轮询直到完成，返回视频 url。"""
    start = time.time()
    while time.time() - start < timeout_s:
        r = requests.get(f"{API_BASE}/videos/{request_id}",
                         headers=api_headers(), timeout=60)
        if r.status_code >= 400:
            raise RuntimeError(f"轮询失败 HTTP {r.status_code}: {r.text}")
        data = r.json()
        status = (data.get("status") or "").lower()
        if status in ("done", "succeeded", "completed", "success"):
            url = _extract_url(data)
            if not url:
                raise RuntimeError(f"完成但无 url：{json.dumps(data)[:500]}")
            return url
        if status in ("expired", "failed", "error", "canceled"):
            raise RuntimeError(f"生成失败，状态={status}：{json.dumps(data)[:500]}")
        print(f"    ...状态 {status or '处理中'}，5秒后再查")
        time.sleep(5)
    raise TimeoutError(f"{request_id} 轮询超时（{timeout_s}s）")


def download(url, dest: Path):
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)
    print(f"    已下载 -> {dest.name} ({dest.stat().st_size//1024} KB)")


def make_card(shot, dest: Path):
    """用 ffmpeg 生成纯色文字卡片（镜头4时间翻牌 / 收尾Logo）。"""
    dur = shot["dur"]
    main = "  ".join(shot.get("card_lines", []))
    sub = shot.get("card_sub", "")
    # 竖屏 720x1280 黑底金字
    vf = (
        f"drawtext=text='{main}':fontcolor=0xC9A96A:fontsize=110:"
        f"x=(w-text_w)/2:y=(h-text_h)/2-60"
    )
    if sub:
        vf += (
            f",drawtext=text='{sub}':fontcolor=0xECE7DD:fontsize=44:"
            f"x=(w-text_w)/2:y=(h-text_h)/2+90"
        )
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=0x08080A:s=720x1280:d={dur}:r=30",
        "-vf", vf,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", str(dur),
        str(dest),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    print(f"    生成卡片 -> {dest.name}")


def normalize(src: Path, dest: Path):
    """统一分辨率/帧率/编码，保证拼接不出错。"""
    cmd = [
        "ffmpeg", "-y", "-i", str(src),
        "-vf", "scale=720:1280:force_original_aspect_ratio=increase,"
               "crop=720:1280,setsar=1,fps=30",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-an",  # 去音轨，成片可后期统一配乐
        str(dest),
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def concat(parts, dest: Path):
    listfile = SHOTS_DIR / "_concat.txt"
    listfile.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts))
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
           "-i", str(listfile), "-c", "copy", str(dest)]
    subprocess.run(cmd, check=True, capture_output=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="grok-imagine-video")
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("--only", default="", help="只跑指定序号，逗号分隔，如 1,3,6")
    args = ap.parse_args()

    SHOTS_DIR.mkdir(exist_ok=True)
    only = {int(x) for x in args.only.split(",") if x.strip()} if args.only else None

    normalized_parts = []
    for idx, shot in enumerate(SHOTS, 1):
        if only and idx not in only:
            # 仍需已有文件参与拼接
            norm = SHOTS_DIR / f"{shot['id']}_norm.mp4"
            if norm.exists():
                normalized_parts.append(norm)
            continue

        raw = SHOTS_DIR / f"{shot['id']}.mp4"
        norm = SHOTS_DIR / f"{shot['id']}_norm.mp4"
        print(f"\n[{idx}/{len(SHOTS)}] 镜头 {shot['id']} ({shot['kind']}, {shot['dur']}s)")

        if args.skip_existing and norm.exists():
            print("    已存在，跳过")
            normalized_parts.append(norm)
            continue

        try:
            if shot["kind"] == "card":
                make_card(shot, raw)
            else:
                print("    提交生成请求...")
                res = submit_generation(shot, args.model)
                if "sync_url" in res:
                    url = res["sync_url"]
                else:
                    print(f"    request_id={res['request_id']}，轮询中...")
                    url = poll(res["request_id"])
                download(url, raw)

            normalize(raw, norm)
            normalized_parts.append(norm)
        except Exception as e:
            print(f"    [错误] 镜头 {shot['id']} 失败：{e}")
            print("    该镜头跳过，你可稍后用 --only 单独重跑。")

    if not normalized_parts:
        sys.exit("\n没有任何可用镜头，未生成成片。")

    print(f"\n拼接 {len(normalized_parts)} 个镜头 -> {FINAL.name}")
    concat(normalized_parts, FINAL)
    print(f"\n✅ 完成！成片：{FINAL}")
    print("   （已去音轨，可导入剪映统一配乐 + 加收尾字幕）")


if __name__ == "__main__":
    main()
