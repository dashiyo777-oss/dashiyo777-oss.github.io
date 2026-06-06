import re

with open('women-history.html', 'r', encoding='utf-8-sig') as f:
    s = f.read()

# 1. Add data-theme="dark" to html tag
s = s.replace('<html lang="ja">', '<html lang="ja" data-theme="dark">', 1)

# 2. Add light theme CSS after :root block closing brace
light_css = '''    [data-theme="light"] {
      --white: #2c1810;
      --gold: #c8860a;
      --amber: #a06000;
      --gray: #6a4a2a;
      --bg-dark: #fdf6ec;
      --bg-mid: #f0e4d0;
    }
    [data-theme="light"] body { background: #fdf6ec; color: #2c1810; }
    [data-theme="light"] .site-header { background: rgba(253,246,236,0.95); }
    [data-theme="light"] .filter-nav { background: rgba(240,228,208,0.97); }
    [data-theme="light"] .profile-card { background: linear-gradient(135deg, rgba(240,228,208,0.8), rgba(253,246,236,0.8)); border-color: rgba(200,134,10,0.2); }
    [data-theme="light"] footer { background: #f0e4d0; }
'''
marker = '    }\n\n    html { scroll-behavior'
s = s.replace(marker, '    }\n\n' + light_css + '\n    html { scroll-behavior', 1)

# 3. Fix hero font size and style
s = s.replace('      font-size: 1.6rem;\n', '      font-size: 2.8rem;\n', 1)
s = s.replace(
    '      color: rgba(253,246,236,0.7);\n      text-shadow: 0 2px 8px rgba(0,0,0,0.5);',
    '      color: rgba(253,246,236,0.9);\n      text-shadow: 0 2px 12px rgba(0,0,0,0.6), 0 0 30px rgba(200,134,10,0.3);',
    1
)

# 4. Remove Portfolio nav link and add theme button
old_nav = '  <nav style="display:flex; gap:2rem;">\n    <a href="index.html">Portfolio</a>\n'
new_nav = '  <nav style="display:flex; gap:2rem; align-items:center;">\n'
s = s.replace(old_nav, new_nav, 1)

theme_btn = '''    <button id="themeBtn" style="background:none;border:1px solid rgba(200,134,10,0.4);border-radius:50px;padding:0.28rem 0.9rem;font-size:0.65rem;letter-spacing:0.12em;color:var(--gray);cursor:pointer;display:flex;align-items:center;gap:0.4rem;transition:all 0.3s;">
      <span id="themeIcon">☀️</span><span id="themeLabel">ライト</span>
    </button>
'''
old_nav_end = '  </nav>\n</header>'
new_nav_end = theme_btn + '  </nav>\n</header>'
s = s.replace(old_nav_end, new_nav_end, 1)

# 5. Remove footer portfolio link
s = s.replace('    <a href="index.html">← Portfolio Top</a>\n', '', 1)

# 6. Add timeline and supervisor comments section before footer
timeline_section = '''<div style="max-width:960px;margin:0 auto;padding:3rem 2rem;">
  <div style="height:1px;background:linear-gradient(to right,transparent,rgba(200,134,10,0.2),transparent);margin-bottom:3rem;"></div>
  <p style="font-size:0.58rem;letter-spacing:0.45em;text-transform:uppercase;color:var(--amber);margin-bottom:0.75rem;">Chronology</p>
  <h2 style="font-family:'Cormorant Garamond',serif;font-size:1.9rem;font-weight:300;margin-bottom:2rem;">時代別<em style="font-style:italic;background:linear-gradient(135deg,var(--gold),var(--amber));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;">㹴表</em></h2>
  <div id="timelineWrap" style="position:relative;padding-left:2rem;">
    <div style="position:absolute;left:0.5rem;top:0;bottom:0;width:1px;background:linear-gradient(to bottom,rgba(200,134,10,0.4),rgba(200,134,10,0.1));"></div>
  </div>
</div>

<div style="max-width:960px;margin:0 auto;padding:0 2rem 4rem;">
  <div style="height:1px;background:linear-gradient(to right,transparent,rgba(200,134,10,0.2),transparent);margin-bottom:3rem;"></div>
  <p style="font-size:0.58rem;letter-spacing:0.45em;text-transform:uppercase;color:var(--amber);margin-bottom:0.75rem;">Supervisor Note</p>
  <h2 style="font-family:'Cormorant Garamond',serif;font-size:1.9rem;font-weight:300;margin-bottom:0.75rem;">監修者<em style="font-style:italic;background:linear-gradient(135deg,var(--gold),var(--amber));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;">コメント</em></h2>
  <p style="font-size:0.72rem;color:var(--gray);margin-bottom:2rem;line-height:1.9;">監修者・専門家からのご意見をお寄せください。最新3件を公開表示します。</p>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:2rem;">
    <div style="padding:1.5rem;background:rgba(58,34,16,0.4);border:1px solid rgba(200,134,10,0.15);">
      <div style="font-size:0.6rem;letter-spacing:0.25em;text-transform:uppercase;color:var(--amber);margin-bottom:1rem;">コメントを投稿する</div>
      <input id="cmtName" type="text" placeholder="お名前 *" style="width:100%;background:rgba(200,134,10,0.05);border:1px solid rgba(200,134,10,0.2);color:var(--white);padding:0.5rem 0.75rem;font-size:0.72rem;margin-bottom:0.75rem;outline:none;font-family:inherit;">
      <input id="cmtRole" type="text" placeholder="役職・肩書き" style="width:100%;background:rgba(200,134,10,0.05);border:1px solid rgba(200,134,10,0.2);color:var(--white);padding:0.5rem 0.75rem;font-size:0.72rem;margin-bottom:0.75rem;outline:none;font-family:inherit;">
      <textarea id="cmtText" placeholder="コメント *" rows="4" style="width:100%;background:rgba(200,134,10,0.05);border:1px solid rgba(200,134,10,0.2);color:var(--white);padding:0.5rem 0.75rem;font-size:0.72rem;margin-bottom:0.75rem;outline:none;font-family:inherit;resize:vertical;"></textarea>
      <button id="cmtSubmit" style="background:rgba(200,134,10,0.2);border:1px solid rgba(200,134,10,0.4);color:var(--amber);padding:0.5rem 1.5rem;font-size:0.65rem;letter-spacing:0.2em;cursor:pointer;font-family:inherit;transition:all 0.3s;">投稿する</button>
      <div id="cmtMsg" style="font-size:0.65rem;margin-top:0.5rem;"></div>
    </div>
    <div style="padding:1.5rem;background:rgba(58,34,16,0.4);border:1px solid rgba(200,134,10,0.15);">
      <div style="font-size:0.6rem;letter-spacing:0.25em;text-transform:uppercase;color:var(--amber);margin-bottom:1rem;">最新コメント</div>
      <div id="cmtList"></div>
    </div>
  </div>
</div>

'''
s = s.replace('<footer', timeline_section + '<footer', 1)

# 7. Add JS before last </script>
js_code = '''
  // Timeline generation
  const timelineData = [
    {era:'弥生時代',years:'〜3世紀',names:['卑弥呼'],color:'#8b5e2a'},
    {era:'飛鳥時代',years:'593〜710',names:['推古天皇'],color:'#6b4c30'},
    {era:'平安時代',years:'794〜1185',names:['紫式部','清少納言','巴御前'],color:'#6b4570'},
    {era:'鎌倉時代',years:'1185〜1333',names:['北条政子'],color:'#2a4a60'},
    {era:'安土桃山時代',years:'1568〜1600',names:['北政所','お市の方','細川ガラシャ'],color:'#705010'},
    {era:'幕末',years:'1853〜1868',names:['新島八重'],color:'#2a2a50'},
    {era:'明治時代',yea\s:'1868〜1912',names:['津田梅子','樋口一葉','与謝野晶子','平塚らいてう'],color:'#5a4030'},
    {era:'大正〜昭和',years:'1912〜',names:['川島芳子','宮本百合子','松井須磨子','伊藤野枝','神近市子'],color:'#3a5050'},
    {era:'現代',years:'1945〜',names:['緒方貞子','水谷八重子'],color:'#303050'},
  ];
  const tlWrap = document.getElementById('timelineWrap');
  if(tlWrap){
    timelineData.forEach(item=>{
      const div = document.createElement('div');
      div.style.cssText='margin-bottom:1.5rem;padding-left:1rem;position:relative;';
      div.innerHTML=`
        <div style="position:absolute;left:-1.75rem;top:0.3rem;width:10px;height:10px;border-radius:50%;background:${item.color};border:2px solid rgba(200,134,10,0.4);"></div>
        <div style="font-size:0.6rem;letter-spacing:0.2em;color:var(--amber);text-transform:uppercase;margin-bottom:0.2rem;">${item.years}</div>
        <div style="font-family:'Noto Serif JP',serif;font-size:0.9rem;font-weight:700;color:var(--white);margin-bottom:0.3rem;">${item.era}</div>
        <div style="font-size:0.72rem;color:var(--gray);">${item.names.join('・')}</div>
      `;
      tlWrap.appendChild(div);
    });
  }

  // Supervisor comments
  function renderComments(){
    const list = document.getElementById('cmtList');
    if(!list) return;
    const cmts = JSON.parse(localStorage.getItem('supervisorComments')||'[]');
    const recent = cmts.slice(-3).reverse();
    if(recent.length===0){
      list.innerHTML='<p style="font-size:0.72rem;color:var(--gray);">まだコメントはありません。</p>';
      return;
    }
    list.innerHTML = recent.map(c=>`
      <div style="border-bottom:1px solid rgba(200,134,10,0.1);padding-bottom:1rem;margin-bottom:1rem;">
        <div style="font-size:0.72rem;color:var(--white);font-weight:500;">${c.name}${c.role?' <span style="font-size:0.62rem;color:var(--gray);">('+c.role+')</span>':''}</div>
        <p style="font-size:0.72rem;color:var(--gray);line-height:1.8;margin-top:0.3rem;">${c.text}</p>
        <div style="font-size:0.55rem;color:rgba(160,128,96,0.5);margin-top:0.3rem;">${c.date}</div>
      </div>
    `).join('');
  }
  renderComments();
  const cmtSubmit = document.getElementById('cmtSubmit');
  if(cmtSubmit){
    cmtSubmit.addEventListener('click',()=>{
      const name = document.getElementById('cmtName').value.trim();
      const role = document.getElementById('cmtRole').value.trim();
      const text = document.getElementById('cmtText').value.trim();
      const msg = document.getElementById('cmtMsg');
      if(!name||!text){msg.style.color='#c04040';msg.textContent='お名前とコメントは必須です。';return;}
      const cmts = JSON.parse(localStorage.getItem('supervisorComments')||'[]');
      cmts.push({name,role,text,date:new Date().toLocaleDateString('ja-JP')});
      localStorage.setItem('supervisorComments',JSON.stringify(cmts));
      document.getElementById('cmtName').value='';
      document.getElementById('cmtRole').value='';
      document.getElementById('cmtText').value='';
      msg.style.color='var(--amber)';msg.textContent='投稿しました。ありがとうございます。';
      renderComments();
      setTimeout(()=>msg.textContent='',3000);
    });
  }

  // Theme toggle
  function applyTheme(light){
    document.documentElement.setAttribute('data-theme', light?'light':'dark');
    document.getElementById('themeIcon').textContent = light?'🌙':'☀️';
    document.getElementById('themeLabel').textContent = light?'ダーク':'ライト';
    localStorage.setItem('theme', light?'light':'dark');
  }
  const savedTh = localStorage.getItem('theme');
  applyTheme(savedTh==='light');
  document.getElementById('themeBtn').addEventListener('click', ()=>{
    applyTheme(document.documentElement.getAttribute('data-theme')==='dark');
  });
'''
last_script = s.rfind('</script>')
s = s[:last_script] + js_code + '\n' + s[last_script:]

with open('women-history.html', 'w', encoding='utf-8') as f:
    f.write(s)
print("Done!")
