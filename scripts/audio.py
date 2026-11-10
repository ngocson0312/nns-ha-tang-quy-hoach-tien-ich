"""Âm thanh: nhạc nền của người dùng (lặp nối mượt nếu ngắn) + SFX bám sự kiện hình → master −14 LUFS.

  python audio.py --plan work/plan.json --music nhac.mp3 --out work/audio.wav [--stems work/stems]

* Nhạc: tự đo nhịp (BPM) để cắt vòng lặp đúng ô nhịp, nối bằng crossfade 60 ms → KHÔNG có khe im
  (video mẫu hở 0,4 s im tuyệt đối ở mỗi mối nối vòng). Vào 0,25 s, ra 1,6 s.
* SFX: đo onset từng file (nhiều file có im ở đầu), chuẩn hoá theo đỉnh RMS 50 ms, đặt sao cho ONSET trùng mốc hình.
  Mức: đỉnh SFX cao hơn mức nhạc tại chỗ đó +3 dB (user chê SFX nhỏ không nghe thấy ở BDS bản 1).
* Master: tăng giảm TUYẾN TÍNH về −14 LUFS rồi alimiter (level=disabled) trần −1,5 dBTP. Không dùng loudnorm
  một lượt (nó âm thầm chuyển sang chế độ động).
Ghi kèm stems/music.wav, stems/sfx.wav và stems/cues.json (mốc onset thật từng SFX) để verify.py so.
"""
import argparse, json, math, os, subprocess, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C
import geo

SR = 48000


def load(path, sr=SR):
    cmd = ["ffmpeg", "-v", "error", "-i", path, "-f", "f32le", "-ac", "2", "-ar", str(sr), "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()


def save(path, x, sr=SR):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ac", "2", "-ar", str(sr), "-i", "-", "-c:a", "pcm_s24le", path]
    subprocess.run(cmd, input=np.ascontiguousarray(x, np.float32).tobytes(), check=True)


def lufs(path):
    out = subprocess.run(["ffmpeg", "-v", "info", "-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    I = TP = None
    for line in out.splitlines()[::-1]:
        s = line.strip()
        if s.startswith("I:") and I is None:
            I = float(s.split()[1])
        if s.startswith("Peak:") and TP is None:
            TP = float(s.split()[1])
    return I, TP


def momentary_max(path):
    # mỗi khung 100 ms ebur128 in "M:<giá trị>" (dòng có cả chữ TARGET — đừng lọc theo nó, lỗi 17/10 làm hàm luôn trả −70)
    out = subprocess.run(["ffmpeg", "-nostats", "-i", path, "-af", "ebur128=metadata=1,ametadata=print:key=lavfi.r128.M",
                          "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    vals = []
    for line in out.splitlines():
        if "lavfi.r128.M=" in line:
            try:
                vals.append(float(line.split("lavfi.r128.M=")[1].strip()))
            except Exception:
                pass
    return max(vals) if vals else -70.0


def env_db(x, sr=SR, win=0.05):
    m = x.mean(1) if x.ndim == 2 else x
    n = max(1, int(win * sr))
    k = len(m) // n
    e = np.sqrt(np.mean(m[:k * n].reshape(k, n) ** 2, axis=1) + 1e-12)
    return 20 * np.log10(e)


def onset(x, sr=SR):
    """onset = khung 5 ms đầu tiên vượt (đỉnh − 30 dB)."""
    m = np.abs(x).max(1)
    n = int(0.005 * sr)
    k = len(m) // n
    e = m[:k * n].reshape(k, n).max(1)
    thr = e.max() * 10 ** (-30 / 20)
    i = int(np.argmax(e > thr))
    return i * n / sr


def beat_period(x, sr=SR):
    m = x.mean(1)
    hop, nfft = 512, 2048
    win = np.hanning(nfft)
    frames = np.lib.stride_tricks.sliding_window_view(m, nfft)[::hop] * win
    S = np.abs(np.fft.rfft(frames, axis=1))
    flux = np.maximum(np.diff(np.log1p(S), axis=0), 0).sum(1)
    flux -= flux.mean()
    ac = np.correlate(flux, flux, "full")[len(flux) - 1:]
    fps = sr / hop
    lags = np.arange(len(ac)) / fps
    sel = (lags > 60 / 180) & (lags < 60 / 70)
    return float(lags[sel][np.argmax(ac[sel])])


def music_bed(path, dur, sr=SR):
    x = load(path, sr)
    need = int(dur * sr)
    if len(x) >= need:
        y = x[:need].copy()
    else:
        # lặp NGUYÊN FILE (file nhạc ngắn hầu hết là vòng lặp tròn ô nhịp). Không cắt theo BPM đo được: trên
        # nhạc mẫu KB5 máy đo ra 130,8 BPM trong khi thật là 125,6 → vòng cắt lệch giữa ô nhịp, nghe giật.
        xf = int(0.08 * sr)
        y = x.copy()
        n = 1
        while len(y) < need + xf:
            a = y[-xf:] * np.linspace(1, 0, xf)[:, None]
            b = x[:xf] * np.linspace(0, 1, xf)[:, None]
            y = np.vstack([y[:-xf], a + b, x[xf:]])
            n += 1
        y = y[:need]
        print(f"  nhạc {len(x) / sr:.1f} s < video {dur:.1f} s → lặp nguyên file {n} lần, nối crossfade 80 ms")
    fi, fo = int(0.25 * sr), int(1.6 * sr)
    y[:fi] *= np.linspace(0, 1, fi)[:, None]
    y[-fo:] *= np.linspace(1, 0, fo)[:, None] ** 1.5
    return y


def build(plan, music_path, out, stems):
    T = plan["meta"]["duration"]
    N = int(round(T * SR))
    mus = music_bed(music_path, T) if music_path else np.zeros((N, 2), np.float32)
    mus = mus[:N] if len(mus) >= N else np.vstack([mus, np.zeros((N - len(mus), 2), np.float32)])
    # nhạc về khoảng −16 LUFS (ước bằng RMS khối 400 ms) trước khi trộn
    e = env_db(mus, win=0.4)
    act = e[e > e.max() - 20]
    if len(act):
        mus *= 10 ** ((-19.0 - float(np.median(act))) / 20)
    mus *= 10 ** (C.MUSIC_REL_DB / 20)
    sfx = np.zeros_like(mus)
    cues = []
    cache = {}
    has_music = bool(music_path)
    mus_env = env_db(mus, win=0.05) if has_music else None
    for ev in plan["sfx"]:
        name = ev["name"]
        if name not in C.SFX:
            continue
        f, gain_db, dt = C.SFX[name]
        if f not in cache:
            y = load(os.path.join(C.SFX_DIR, f))
            on = onset(y)
            y = y[int(on * SR):]
            ev_ = env_db(y)
            pk = ev_.max()
            pk_t = float(np.argmax(ev_)) * 0.05                  # whoosh dâng chậm: đỉnh có thể ở giây thứ 0,5–1
            cache[f] = (y * 10 ** ((-12.0 - pk) / 20), pk_t)     # đỉnh RMS 50 ms về −12 dBFS
        y, pk_t = cache[f]
        t = ev["t"] + dt
        skip = 0.0
        if name in C.SFX_PEAK:                           # đỉnh tiếng rơi đúng mốc hình (giữa cú bay / lúc ghim bật)
            t = t - pk_t
            if t < 0:                                    # cú bay quá sớm (nhịp nhanh 18/10): cắt bớt ĐẦU tiếng, giữ đỉnh đúng chỗ
                skip, t = -t, 0.0
        y_use = y[int(round(skip * SR)):]
        i0 = int(round(t * SR))
        if i0 >= N or i0 < 0:
            continue
        j = min(N, i0 + len(y_use))
        # mức nhạc quanh mốc → đỉnh SFX = nhạc + 3 dB + gain riêng
        a, b = int((t + pk_t - 0.2) / 0.05), int((t + pk_t + 0.2) / 0.05) + 1   # mức nhạc quanh ĐỈNH của SFX
        mloc = float(np.max(mus_env[max(0, a):max(a + 1, b)])) if has_music else C.SFX_NO_MUSIC_REF
        g = 10 ** ((mloc + C.SFX_OVER_MUSIC + gain_db - (-12.0)) / 20)
        sfx[i0:j] += y_use[:j - i0] * g
        cues.append(dict(name=name, file=f, t=round(t, 4), skip=round(skip, 4), gain_db=round(20 * math.log10(g), 2)))
    mix = mus + sfx
    tmp = out + ".pre.wav"
    save(tmp, mix)
    I, TP = lufs(tmp)
    if has_music:
        gain = C.LUFS - I
    else:
        # chỉ có SFX: độ to tích phân vô nghĩa (đa phần là lặng) — kéo theo độ to TỨC THỜI lớn nhất
        mmax = momentary_max(tmp)
        gain = C.SFX_ONLY_PEAK_LUFS_M - mmax
        print(f"  (không có nhạc — chuẩn theo độ to tức thời lớn nhất {mmax:.1f} → {C.SFX_ONLY_PEAK_LUFS_M} LUFS-M)")
    mix *= 10 ** (gain / 20)
    save(tmp, mix)
    # giới hạn ở 4× tần số lấy mẫu để chặn cả đỉnh giữa mẫu (true peak); SFX pop/ting có quá độ cao tần
    # vọt +1,7 dB nếu chỉ giới hạn đỉnh mẫu ở 48 kHz
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", tmp, "-af",
           f"aresample={4 * SR},alimiter=limit={10 ** ((C.TP - C.AAC_HEADROOM) / 20):.4f}:attack=2:release=60:level=disabled,aresample={SR}",
           "-c:a", "pcm_s24le", out]
    subprocess.run(cmd, check=True)
    os.remove(tmp)
    I2, TP2 = lufs(out)
    if stems:
        os.makedirs(stems, exist_ok=True)
        save(os.path.join(stems, "music.wav"), mus * 10 ** (gain / 20))
        save(os.path.join(stems, "sfx.wav"), sfx * 10 ** (gain / 20))
        geo.save_json(os.path.join(stems, "cues.json"), dict(cues=cues, master_gain_db=gain, has_music=has_music))
    print(f"  ✓ âm thanh: {len(cues)} SFX, master {gain:+.1f} dB → {I2:.1f} LUFS, đỉnh {TP2:.1f} dBTP")
    return I2, TP2


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--music")
    ap.add_argument("--out", required=True)
    ap.add_argument("--stems")
    a = ap.parse_args()
    build(geo.load_json(a.plan), a.music, a.out, a.stems)


if __name__ == "__main__":
    main()
