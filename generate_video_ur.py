#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UR 时尚女装「都市即秀场」AIGC概念短片 —— 一键生成脚本
=====================================================

功能：调用 xAI Grok Imagine 视频接口，按分镜脚本生成 9 个镜头，
      下载后用 ffmpeg 拼接成 35 秒竖屏（9:16）成片。

依赖：
    pip install requests
    ffmpeg（系统需已安装，命令行能跑 `ffmpeg -version`）

用法：
    export XAI_API_KEY="xai-你的key"
    # 可选：把服装图存成同目录下的 look1.jpg / look2.jpg（镜头3、7用它做图生视频，
    #        缺图时自动降级为文生视频，不影响跑通）
    python3 generate_video_ur.py

    可选参数：
    python3 generate_video_ur.py --model grok-imagine-video-1.5   # 换模型
    python3 generate_video_ur.py --skip-existing                  # 跳过已下载的镜头，断点续跑
    python3 generate_video_ur.py --only 1,3,6                     # 只重跑指定镜头

产出：
    ./shots_ur/           每个镜头的 mp4
    ./final_output_ur.mp4 拼接好的完整成片
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
SHOTS_DIR = HERE / "shots_ur"
FINAL = HERE / "final_output_ur.mp4"

# 竖屏短视频
ASPECT = "9:16"
RESOLUTION = "720p"

# ---------- 分镜定义 ----------
# kind: "t2v" 文生视频 | "i2v" 图生视频（需 image 字段指向的图片）| "card" ffmpeg文字卡片（不调API）
# 总时长：3+4+4+4+3+5+4+5+3 = 35s
SHOTS = [
    {
        "id": "01_city_dawn", "kind": "t2v", "dur": 3,
        "prompt": "都市清晨，玻璃幕墙高楼之间的窄巷，冷调晨光穿过楼宇形成光束，一位年轻女性的剪影"
                  "拎着风衣快步走过画面，脚步利落，时装大片开场氛围，电影感，浅景深。"
                  "Urban dawn, narrow street between glass skyscrapers, cool morning light beams "
                  "between buildings, silhouette of a young woman striding past carrying a trench "
                  "coat, brisk confident steps, fashion-film opening mood, cinematic, shallow depth "
                  "of field, vertical 9:16.",
    },
    {
        "id": "02_rack_fabric", "kind": "t2v", "dur": 4,
        "prompt": "特写镜头，服装店金属衣杆上的衣架被依次快速拨动滑过，米色风衣、黑色西装、针织衫"
                  "面料依次划过画面，一只女性的手指轻轻拂过羊毛面料的纹理，质感细腻，商业布光，慢动作收尾。"
                  "Close-up, hangers sliding fast along a metal rack, beige trench coat, black blazer, "
                  "knitwear fabrics sweeping past, a woman's fingers brushing across fine wool texture, "
                  "tactile detail, commercial lighting, ending in slow motion, vertical 9:16.",
    },
    {
        "id": "03_look1_walk", "kind": "i2v", "dur": 4,
        "image": "look1.jpg",
        "prompt": "一位气质出众的年轻女模特身穿米色长款风衣搭配白色内搭，在城市街头大步走向镜头，"
                  "低角度仰拍，风衣下摆随步伐摆动，背景是虚化的都市街景，高级街拍时尚大片质感，自然日光。"
                  "A striking young female model in a long beige trench coat over a white top strides "
                  "toward the camera on a city street, low-angle shot, coat hem swinging with each "
                  "step, blurred urban background, high-end street-style fashion editorial, natural "
                  "daylight, vertical 9:16.",
    },
    {
        "id": "04_twirl_detail", "kind": "t2v", "dur": 4,
        "prompt": "女模特原地轻盈转身，衣摆与长发在慢动作中扬起，镜头快速推近到面料的编织纹理与缝线细节，"
                  "微距质感，光线勾勒面料光泽，时装广告级画面。"
                  "The female model does a light twirl in place, hem and long hair lifting in slow "
                  "motion, camera pushing in fast to the weave texture and stitching details of the "
                  "fabric, macro feel, light tracing the fabric sheen, fashion-commercial grade, "
                  "vertical 9:16.",
    },
    {
        "id": "05_titlecard", "kind": "card", "dur": 3,
        "card_lines": ["ONE CITY", "THREE LOOKS"],
        "card_sub": "都市即秀场",
    },
    {
        "id": "06_outfit_morph", "kind": "t2v", "dur": 5,
        "prompt": "创意换装转场：女模特在旋转中，身上的米色风衣通勤装如流动的布料般无缝变化为一条"
                  "黑色针织修身连衣裙，布料粒子飘散重组，背景光影同步从白昼变为暖色黄昏，"
                  "超现实时尚感，丝滑过渡，高级质感。"
                  "Creative outfit-morph transition: as the model spins, her beige trench office look "
                  "seamlessly transforms into a black fitted knit dress, fabric dissolving into "
                  "particles and re-forming, background light shifting from daylight to warm dusk, "
                  "surreal fashion feel, silky transition, premium quality, vertical 9:16.",
    },
    {
        "id": "07_night_look", "kind": "i2v", "dur": 4,
        "image": "look2.jpg",
        "prompt": "都市夜景，霓虹与橱窗灯光虚化成光斑，女模特身穿缎面吊带长裙倚靠在街边，缎面反射"
                  "霓虹光泽，回眸看向镜头，眼神自信，夜色时尚氛围大片，电影级打光。"
                  "Urban night scene, neon and shop-window lights blurred into bokeh, the female model "
                  "in a satin slip dress leaning by the street, satin catching neon reflections, "
                  "glancing back at the camera with confidence, night fashion editorial, cinematic "
                  "lighting, vertical 9:16.",
    },
    {
        "id": "08_look_montage", "kind": "t2v", "dur": 5,
        "prompt": "快节奏剪辑感的走秀式合集：同一位女模特的三套造型（米色风衣、黑色针织连衣裙、"
                  "缎面吊带裙）在纯色影棚背景前依次亮相定格，每次定格伴随灯光频闪，最后她面向镜头"
                  "自信微笑，双手插兜，时尚杂志封面感。"
                  "Runway-style fast montage: the same female model appears in three looks — beige "
                  "trench, black knit dress, satin slip dress — posing in sequence against a clean "
                  "studio backdrop, strobe light on each freeze, ending with her smiling confidently "
                  "at the camera, hands in pockets, magazine-cover feel, vertical 9:16.",
    },
    {
        "id": "09_logo", "kind": "card", "dur": 3,
        "card_lines": ["URBAN REVIVO"],
        "card_sub": "新装上市 · 都市即秀场",
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
        img = HERE / shot.get("image", "")
        if not img.exists():
            print(f"  [!] 缺少 {img.name}，镜头 {shot['id']} 降级为文生视频")
        else:
            body["image_url"] = img_data_uri(img)

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
    """用 ffmpeg 生成纯色文字卡片（标题卡 / 收尾Logo）。"""
    dur = shot["dur"]
    lines = shot.get("card_lines", [])
    sub = shot.get("card_sub", "")
    # 竖屏 720x1280 黑底白字（UR 黑白极简风）
    filters = []
    n = len(lines)
    for i, line in enumerate(lines):
        # 多行主标题垂直居中排布
        offset = (i - (n - 1) / 2) * 130 - 60
        filters.append(
            f"drawtext=text='{line}':fontcolor=0xF2F0EC:fontsize=96:"
            f"x=(w-text_w)/2:y=(h-text_h)/2+{offset:.0f}"
        )
    if sub:
        filters.append(
            f"drawtext=text='{sub}':fontcolor=0x8E8A84:fontsize=40:"
            f"x=(w-text_w)/2:y=(h-text_h)/2+{(n - 1) / 2 * 130 + 90:.0f}"
        )
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=0x0A0A0B:s=720x1280:d={dur}:r=30",
        "-vf", ",".join(filters),
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
