const players=[
{name:'이준호',no:1,pos:'GK',x:50,y:91,shoot:20,pass:72,speed:58,dribble:45,defence:82,physical:80},
{name:'박지훈',no:3,pos:'LB',x:18,y:73,shoot:48,pass:75,speed:84,dribble:72,defence:79,physical:77},
{name:'최현우',no:4,pos:'CB',x:39,y:78,shoot:35,pass:70,speed:69,dribble:55,defence:88,physical:86},
{name:'정우진',no:5,pos:'CB',x:61,y:78,shoot:38,pass:68,speed:67,dribble:52,defence:87,physical:88},
{name:'김도윤',no:2,pos:'RB',x:82,y:73,shoot:50,pass:74,speed:86,dribble:73,defence:78,physical:76},
{name:'한승민',no:6,pos:'CM',x:35,y:55,shoot:70,pass:86,speed:76,dribble:80,defence:75,physical:79},
{name:'오세진',no:8,pos:'CM',x:65,y:55,shoot:75,pass:88,speed:77,dribble:84,defence:72,physical:76},
{name:'이태양',no:11,pos:'LW',x:20,y:31,shoot:82,pass:78,speed:92,dribble:89,defence:45,physical:72},
{name:'김민준',no:10,pos:'FW',x:50,y:22,shoot:88,pass:80,speed:91,dribble:86,defence:54,physical:78},
{name:'박건우',no:7,pos:'RW',x:80,y:31,shoot:84,pass:79,speed:90,dribble:87,defence:48,physical:73},
{name:'윤재혁',no:9,pos:'ST',x:50,y:10,shoot:91,pass:72,speed:85,dribble:81,defence:40,physical:84}
];
const pitch=document.getElementById('pitch'); let selected=8;
function renderPlayers(){pitch.querySelectorAll('.player').forEach(e=>e.remove());players.forEach((p,i)=>{let el=document.createElement('div');el.className='player'+(i===selected?' active':'');el.style.left=p.x+'%';el.style.top=p.y+'%';el.innerHTML=`<div class="circle">${p.no}</div><span>${p.pos} · ${p.name}</span>`;el.onclick=()=>{selected=i;renderPlayers();showPlayer(p)};pitch.appendChild(el)})}
function showPlayer(p){document.getElementById('playerName').textContent=p.name;document.getElementById('playerMeta').textContent=`${p.pos} · No.${p.no} · SEOUL`;['shoot','pass','speed','dribble','defence','physical'].forEach(k=>document.getElementById(k).textContent=p[k]);document.getElementById('overall').textContent=Math.round((p.shoot+p.pass+p.speed+p.dribble+p.defence+p.physical)/6);document.getElementById('playerPhoto').innerHTML=`<span>${p.no}</span>`;drawRadar(p)}
function drawRadar(p){const c=document.getElementById('radar'),ctx=c.getContext('2d'),cx=c.width/2,cy=c.height/2+4,r=82,vals=[p.shoot,p.pass,p.speed,p.dribble,p.defence,p.physical],labels=['슈팅','패스','스피드','드리블','수비','피지컬'];ctx.clearRect(0,0,c.width,c.height);ctx.strokeStyle='#29463a';ctx.fillStyle='#90a49a';ctx.font='11px Arial';for(let ring=1;ring<=4;ring++){ctx.beginPath();for(let i=0;i<6;i++){let a=-Math.PI/2+i*Math.PI/3,rr=r*ring/4,x=cx+Math.cos(a)*rr,y=cy+Math.sin(a)*rr;i?ctx.lineTo(x,y):ctx.moveTo(x,y)}ctx.closePath();ctx.stroke()}for(let i=0;i<6;i++){let a=-Math.PI/2+i*Math.PI/3;ctx.beginPath();ctx.moveTo(cx,cy);ctx.lineTo(cx+Math.cos(a)*r,cy+Math.sin(a)*r);ctx.stroke();ctx.fillText(labels[i],cx+Math.cos(a)*(r+20)-12,cy+Math.sin(a)*(r+20)+4)}ctx.beginPath();vals.forEach((v,i)=>{let a=-Math.PI/2+i*Math.PI/3,rr=r*v/100,x=cx+Math.cos(a)*rr,y=cy+Math.sin(a)*rr;i?ctx.lineTo(x,y):ctx.moveTo(x,y)});ctx.closePath();ctx.fillStyle='rgba(53,232,132,.24)';ctx.strokeStyle='#35e884';ctx.lineWidth=2;ctx.fill();ctx.stroke()}
document.getElementById('simulateBtn').onclick=()=>{let h=Math.floor(Math.random()*5),a=Math.floor(Math.random()*5);document.getElementById('score').textContent=`${h} : ${a}`};document.getElementById('resetBtn').onclick=()=>{selected=8;renderPlayers();showPlayer(players[selected])};document.getElementById('applyBtn').onclick=()=>alert(document.getElementById('formation').value+' 포메이션을 적용했습니다.');renderPlayers();showPlayer(players[selected]);
