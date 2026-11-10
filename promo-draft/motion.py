#!/usr/bin/env python3
"""パチおばの縦の宣伝動画（動く文字つき）。HTML の render(t) で1コマずつ描いて、headless Chrome で撮り、ffmpeg でつなぐ。
python3 motion.py <出力.mp4> [秒の上限]
"""
import asyncio, json, random, subprocess, sys, shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
FONTS = Path("/home/claude/ios-kobo/build/pachioba/project/Game/fonts")
SHOTS = Path("/home/claude/ios-kobo/build/pachioba/fastlane/screenshots/ja")
W, H, FPS = 1080, 1920, 30

# 場面：見出し2行・スクショ・2行目の出かた（pop＝1文字ずつ / neon＝チカチカ点く / slam＝ドーン / spin＝数字がまわる）
SCENES = [
    {"h1": "パチンコの台で", "h2": "タワーディフェンス", "shot": "1-title", "fx": "neon", "len": 3.2},
    {"h1": "まん中に入ると", "h2": "FEVER", "shot": "2-fever", "fx": "slam", "len": 3.0},
    {"h1": "杭にタワーを建てて", "h2": "おばけを止める", "shot": "3-boss", "fx": "pop", "len": 2.8},
    {"h1": "草原から天国まで", "h2": "9つの台", "shot": "4-heaven", "fx": "spin", "len": 2.8, "num": "9"},
    {"h1": "1つの台に", "h2": "10のWAVE", "shot": "5-boards", "fx": "spin", "len": 2.8, "num": "10"},
    {"h1": "持っていく玉を", "h2": "えらんでセット", "shot": "6-set", "fx": "pop", "len": 2.8},
]
END_LEN = 3.4
SWIPE = 0.36  # 切りかえの長さ


def stars(n, seed):
    r = random.Random(seed)
    out = []
    for _ in range(n):
        out.append({"x": r.random() * W, "y": r.random() * H, "s": r.choice([2, 2, 3, 3, 4, 5]),
                    "a": round(r.uniform(.35, .95), 2), "p": r.random() * 6.28,
                    "c": r.choice(["255,255,255", "255,214,250", "190,240,255", "255,240,170"])})
    return out


def page():
    scenes = []
    t = 0.0
    for i, s in enumerate(SCENES):
        s = dict(s)
        s["t0"] = t
        s["src"] = (SHOTS / f"{s['shot']}-iphone.png").as_uri()
        scenes.append(s)
        t += s["len"]
    end_t0 = t
    total = t + END_LEN
    data = {"scenes": scenes, "end_t0": end_t0, "total": total, "swipe": SWIPE, "stars": stars(110, 7),
            "logo": (HERE / "vid/logo.png").as_uri(), "ghosts": (HERE / "vid/ghosts.png").as_uri()}
    f = lambda n: (FONTS / n).as_uri()
    return total, f"""<!doctype html><html><head><meta charset=utf-8><style>
@font-face{{font-family:R;src:url('{f('MPLUSRounded1c-800.ttf')}');font-weight:800}}
html,body{{margin:0;width:{W}px;height:{H}px;overflow:hidden;background:#05030f}}
body{{font-family:R;position:relative}}
#bg{{position:absolute;inset:0;background:radial-gradient(ellipse at 50% 26%,#4a1a9a 0%,#1d0c4a 38%,#0a0520 72%,#05030f 100%)}}
.star{{position:absolute;border-radius:50%}}
svg.arch{{position:absolute;left:0;top:0}}
.scene{{position:absolute;inset:0;will-change:transform}}
.hd{{position:absolute;top:118px;left:0;right:0;text-align:center;white-space:nowrap}}
.l1{{font-size:78px;color:#ffe873;letter-spacing:.04em;text-shadow:0 0 10px #ffb800,0 0 34px #ff8a00;height:96px}}
.l2wrap{{position:relative;display:inline-block;margin-top:12px}}
.l2{{color:#ffd3f5;letter-spacing:.02em;text-shadow:0 0 7px #fff,0 0 22px #ff4fd8,0 0 50px #ff4fd8,0 0 90px #8a5cff}}
.shine{{position:absolute;inset:0;color:transparent;-webkit-background-clip:text;background-clip:text;background-repeat:no-repeat;background-size:40% 100%;background-image:linear-gradient(100deg,transparent 0%,rgba(255,255,255,.95) 50%,transparent 100%);letter-spacing:.02em}}
.ch{{display:inline-block;will-change:transform}}
.fr{{position:absolute;left:50%;top:524px;padding:8px;border-radius:64px;background:linear-gradient(140deg,#ff5fd8,#8a5cff 45%,#5ce1ff 75%,#ffe873);transform-origin:50% 0}}
.fr img{{display:block;border-radius:56px}}
.ring{{position:absolute;border-radius:50%;border:10px solid #ffe873;box-shadow:0 0 40px #ff4fd8,inset 0 0 40px #5ce1ff}}
#flash{{position:absolute;inset:0;background:#fff;opacity:0;pointer-events:none}}
#end{{position:absolute;inset:0;opacity:0}}
#end .logo{{position:absolute;top:250px;left:0;width:1080px}}
#end .gh{{position:absolute;top:600px;left:0;width:1080px}}
#end .t1{{position:absolute;top:1520px;left:0;right:0;text-align:center;font-size:76px;color:#ffe873;text-shadow:0 0 12px #ffb800,0 0 40px #ff8a00}}
#end .t2{{position:absolute;top:1640px;left:0;right:0;text-align:center;font-size:50px;color:#fff;letter-spacing:.06em;text-shadow:0 0 10px #ff4fd8,0 0 30px #8a5cff}}
.spark{{position:absolute;width:6px;height:6px;border-radius:50%;background:#fff}}
</style></head><body>
<div id=bg></div><div id=stars></div>
<svg class=arch width={W} height={H}><path id=a2 d="" fill=none stroke="#5ce1ff" stroke-width=5 /><path id=a1 d="" fill=none stroke="#ff5fd8" stroke-width=8 /></svg>
<div id=scenes></div><div id=sparks></div>
<div id=end><img class=logo src="{data['logo']}"><img class=gh src="{data['ghosts']}"><div class=t1>App Storeで配信予定</div><div class=t2>iPhone・iPad</div></div>
<div id=flash></div>
<script>
const D={json.dumps(data, ensure_ascii=False)};
const W={W},H={H};
const clamp=(x,a=0,b=1)=>Math.max(a,Math.min(b,x));
const lin=(t,a,b)=>clamp((t-a)/(b-a));
const eOut=x=>1-Math.pow(1-x,3);
const eIn=x=>x*x*x;
const eBack=x=>{{const c=1.9;return 1+(c+1)*Math.pow(x-1,3)+c*Math.pow(x-1,2)}};
const eElastic=x=>x<=0?0:x>=1?1:Math.pow(2,-10*x)*Math.sin((x*10-.75)*2*Math.PI/3)+1;
// 星
const st=document.getElementById('stars');
D.stars.forEach(s=>{{const e=document.createElement('i');e.className='star';Object.assign(e.style,{{left:s.x+'px',top:s.y+'px',width:s.s+'px',height:s.s+'px',background:`rgba(${{s.c}},${{s.a}})`,boxShadow:`0 0 ${{s.s*3}}px rgba(${{s.c}},${{s.a}})`}});s.el=e;st.appendChild(e)}});
// アーチ
function archPath(m,top){{const r=(W-2*m)/2;return `M ${{m}} ${{H+20}} L ${{m}} ${{top+r}} A ${{r}} ${{r}} 0 0 1 ${{W-m}} ${{top+r}} L ${{W-m}} ${{H+20}}`}}
const a1=document.getElementById('a1'),a2=document.getElementById('a2');
a1.setAttribute('d',archPath(57,458));a2.setAttribute('d',archPath(25,417));
const L1=a1.getTotalLength(),L2=a2.getTotalLength();
[a1,a2].forEach((a,i)=>{{a.style.strokeDasharray=(i?L2:L1);a.style.filter=`drop-shadow(0 0 ${{i?14:22}}px ${{i?'#5ce1ff':'#ff5fd8'}})`}});
// 場面
const box=document.getElementById('scenes');
function chars(t){{return [...t].map(c=>`<span class=ch>${{c==' '?'&nbsp;':c}}</span>`).join('')}}
D.scenes.forEach((s,i)=>{{
  const n2=[...s.h2].length, f2=Math.min(105,Math.floor((W-115)/n2));
  const el=document.createElement('div');el.className='scene';
  el.innerHTML=`<div class=hd><div class=l1>${{chars(s.h1)}}</div><div class=l2wrap style="font-size:${{f2}}px"><div class=l2>${{chars(s.h2)}}</div><div class=shine>${{s.h2}}</div></div></div>
  <div class=fr><img src="${{s.src}}"></div><div class=rings></div>`;
  box.appendChild(el);s.el=el;s.c1=[...el.querySelectorAll('.l1 .ch')];s.c2=[...el.querySelectorAll('.l2 .ch')];
  s.l2=el.querySelector('.l2');s.wrap=el.querySelector('.l2wrap');s.shine=el.querySelector('.shine');s.fr=el.querySelector('.fr');s.img=el.querySelector('.fr img');s.rings=el.querySelector('.rings');
  // 画面の大きさ（下にはみ出さない）
  const iw=1320,ih=2868,top=524,pad=8;const sw=Math.min(818,(H-top-33)*iw/ih+2*pad);s.img.style.width=(sw-2*pad)+'px';s.fr.style.width=sw+'px';s.fr.style.marginLeft=(-sw/2)+'px';
  for(let k=0;k<3;k++){{const r=document.createElement('div');r.className='ring';s.rings.appendChild(r)}}
}});
const sp=document.getElementById('sparks');const SP=[];
for(let i=0;i<26;i++){{const e=document.createElement('i');e.className='spark';sp.appendChild(e);SP.push({{el:e,x:Math.random()*W,s:Math.random()*.6+.4,ph:Math.random()*10,c:['#ffe873','#ff9cf0','#9cf2ff','#fff'][i%4]}})}}

function sceneAt(t){{for(let i=D.scenes.length-1;i>=0;i--)if(t>=D.scenes[i].t0)return i;return 0}}

function drawScene(s,lt,xoff,blur){{
  const el=s.el;el.style.display='block';if(s.fx!=='slam')s.wrap.style.transform='none';el.style.transform=`translateX(${{xoff}}px)`;el.style.filter=blur?`blur(${{blur}}px)`:'none';
  // 1行目：1文字ずつ上から弾んで
  s.c1.forEach((c,k)=>{{const p=lin(lt,.10+k*.035,.10+k*.035+.32);const y=(1-eBack(p))*-70;c.style.transform=`translateY(${{y}}px) scale(${{.6+.4*eBack(p)}})`;c.style.opacity=clamp(p*3)}});
  // 2行目
  const base=.35;
  if(s.fx==='neon'){{
    const p=lin(lt,base,base+.6);const fl=[0,1,.15,1,.4,1,.8,1];const v=p>=1?1:fl[Math.floor(p*fl.length)];
    s.c2.forEach(c=>{{c.style.transform='none';c.style.opacity=v}});
    s.l2.style.filter=`brightness(${{.6+.6*v}})`;
  }} else if(s.fx==='slam'){{
    const p=lin(lt,base+.1,base+.45);const sc=p<=0?0:3.2-2.2*eOut(p);
    s.c2.forEach(c=>{{c.style.opacity=p>0?1:0;c.style.transform='none'}});s.wrap.style.transform=`scale(${{sc}})`;
    s.l2.style.filter=`hue-rotate(${{(lt*240)%360}}deg) brightness(1.2)`;
    // 画面ゆれ
    const sh=lin(lt,base+.45,base+.85);const amp=sh>0&&sh<1?(1-sh)*16:0;
    el.style.transform=`translateX(${{xoff+Math.sin(lt*95)*amp}}px) translateY(${{Math.cos(lt*83)*amp}}px)`;
    // 光の輪
    [...s.rings.children].forEach((r,k)=>{{const q=lin(lt,base+.45+k*.12,base+1.25+k*.12);const R=120+q*900;
      Object.assign(r.style,{{left:(W/2-R/2)+'px',top:(250-R/2)+'px',width:R+'px',height:R+'px',opacity:q>0&&q<1?(1-q)*.9:0}})}});
  }} else if(s.fx==='spin'){{
    // 数字がスロットのようにまわって止まる。ほかの文字は1文字ずつ
    s.c2.forEach((c,k)=>{{const isNum=/[0-9]/.test(c.textContent);
      if(isNum){{const p=lin(lt,base,base+.75);
        if(p<1){{c.textContent=String(Math.floor(lt*40+k*3)%10);c.style.transform=`translateY(${{Math.sin(lt*60)*6}}px)`;c.style.opacity=p>0?1:0}}
        else{{const want=[...s.h2][k];c.textContent=want;const q=lin(lt,base+.75,base+1.05);c.style.transform=`scale(${{1+.5*(1-eOut(q))}})`;c.style.opacity=1}}
      }} else {{const p=lin(lt,base+.2+k*.05,base+.5+k*.05);c.style.opacity=clamp(p*2);c.style.transform=`translateY(${{(1-eBack(p))*50}}px)`}}
    }});
    s.l2.style.filter='none';
  }} else {{
    s.c2.forEach((c,k)=>{{const p=lin(lt,base+k*.05,base+k*.05+.35);c.style.opacity=clamp(p*2);c.style.transform=`translateY(${{(1-eBack(p))*60}}px) scale(${{.4+.6*eBack(p)}})`}});
    s.l2.style.filter='none';
  }}
  // 光のすじ
  const sw=lin(lt,1.15,1.75);s.shine.style.backgroundPosition=`${{-60+sw*220}}% 0`;s.shine.style.opacity=sw>0&&sw<1?1:0;
  // 画面：下からすっと上がって、ゆっくり寄る
  const up=eOut(lin(lt,.15,.7));const push=1+.045*lin(lt,.7,s.len);
  s.fr.style.transform=`translateY(${{(1-up)*700}}px) scale(${{push}})`;
  const glow=.55+.25*Math.sin(lt*6);s.fr.style.boxShadow=`0 0 ${{40+20*glow}}px rgba(255,95,216,${{glow}}),0 0 120px rgba(92,225,255,.35)`;
}}

window.render=function(t){{
  // 星のまたたき
  D.stars.forEach(s=>{{s.el.style.opacity=.55+.45*Math.sin(t*2.2+s.p)}});
  // アーチが光で描かれる（はじめの0.8秒）
  const ad=eOut(lin(t,.05,.85));a1.style.strokeDashoffset=L1*(1-ad);a2.style.strokeDashoffset=L2*(1-eOut(lin(t,.15,1.0)));
  a1.style.opacity=.6;a2.style.opacity=.45;
  // 場面
  D.scenes.forEach(s=>s.el.style.display='none');
  const sw=D.swipe;let flash=0;
  const i=sceneAt(t);const s=D.scenes[i];const lt=t-s.t0;
  const nextT=(i+1<D.scenes.length)?D.scenes[i+1].t0:D.end_t0;
  if(t>=D.end_t0-sw/2 && i===D.scenes.length-1){{
    // おわりへ：白く光って切りかえ
  }}
  if(i+1<D.scenes.length && t>nextT-sw){{
    const p=lin(t,nextT-sw,nextT);const e=eIn(p);drawScene(s,lt,-W*e,p*14);flash=Math.sin(p*Math.PI)*.35;
  }} else if(t<D.end_t0) {{ drawScene(s,lt,0,0); }}
  if(i>0 && lt<sw){{ const p=lin(lt,0,sw);drawScene(s,lt,W*(1-eOut(p)),(1-p)*14);flash=Math.max(flash,(1-p)*.35); }}
  // おわりの1枚
  const end=document.getElementById('end');
  if(t>=D.end_t0-sw){{
    const p=lin(t,D.end_t0-sw,D.end_t0);flash=Math.max(flash,Math.sin(Math.min(p,1)*Math.PI/2)*1.0);
    if(t<D.end_t0){{drawScene(s,lt,0,0);end.style.opacity=0}}
    else{{D.scenes.forEach(x=>x.el.style.display='none');const q=t-D.end_t0;flash=Math.max(0,1-q/.45);
      end.style.opacity=1;const lg=end.querySelector('.logo');const pl=eElastic(lin(q,.05,.9));lg.style.transform=`scale(${{.3+.7*pl}})`;lg.style.opacity=clamp(q*4);
      const g=end.querySelector('.gh');g.style.transform=`translateY(${{(1-eOut(lin(q,.2,.9)))*400}}px)`;g.style.opacity=clamp((q-.2)*3);
      const t1=end.querySelector('.t1'),t2=end.querySelector('.t2');const p1=lin(q,.8,1.2);t1.style.opacity=p1;t1.style.transform=`translateY(${{(1-eOut(p1))*40}}px)`;
      t2.style.opacity=lin(q,1.0,1.4);
      // 最後に暗く
      const out=lin(t,D.total-.5,D.total);document.getElementById('flash').style.background=out>0?'#000':'#fff';if(out>0)flash=out;}}
  }} else end.style.opacity=0;
  // はじめは黒から
  if(t<.35){{document.getElementById('flash').style.background='#000';flash=1-t/.35}}
  else if(t<D.total-.5)document.getElementById('flash').style.background='#fff';
  document.getElementById('flash').style.opacity=flash;
  // 光のつぶ（下からふわっと）
  SP.forEach(p=>{{const y=H-((t*120*p.s+p.ph*200)%(H+100));Object.assign(p.el.style,{{left:(p.x+Math.sin(t*1.5+p.ph)*30)+'px',top:y+'px',opacity:.5+.4*Math.sin(t*3+p.ph),background:p.c,boxShadow:`0 0 14px ${{p.c}}`}})}});
}};
</script></body></html>"""


async def main():
    out = sys.argv[1]
    limit = float(sys.argv[2]) if len(sys.argv) > 2 else None
    total, html = page()
    if limit:
        total = min(total, limit)
    tmp = HERE / "_motion.html"
    tmp.write_text(html, encoding="utf-8")
    fdir = HERE / "_frames"
    shutil.rmtree(fdir, ignore_errors=True)
    fdir.mkdir()
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--allow-file-access-from-files"])
        pg = await b.new_page(viewport={"width": W, "height": H})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.goto(tmp.as_uri())
        await pg.wait_for_timeout(800)
        n = int(round(total * FPS))
        for i in range(n):
            await pg.evaluate(f"render({i / FPS})")
            await pg.screenshot(path=str(fdir / f"f{i:04d}.jpg"), type="jpeg", quality=93)
        await b.close()
        if errs:
            print("ERR", errs[:3])
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-framerate", str(FPS), "-i", str(fdir / "f%04d.jpg"),
                    "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(FPS),
                    "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", out], check=True)
    print(out, n, "frames")

if __name__ == "__main__":
    asyncio.run(main())
