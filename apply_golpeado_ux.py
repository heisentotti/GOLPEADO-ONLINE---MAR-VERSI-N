from pathlib import Path

p = Path('web/index.html')
if not p.exists():
    raise SystemExit('ERROR: ejecuta este script desde la raíz de golpeado-github-temp')

s = p.read_text()

# 1) Estilos de estados temporales y ganador.
s = s.replace(
    '.status{color:var(--muted);min-height:24px}',
    '.status{color:var(--muted);min-height:24px;transition:opacity .2s ease}.status.status-hidden{opacity:0;visibility:hidden}.status.error{color:#ff9a9a}.status.success{color:#9ce2b5}',
    1,
)
s = s.replace('.error{color:#ff9a9a}.success{color:#9ce2b5}.title', '.title', 1)
s = s.replace(
    '.turn-name strong{color:var(--red2)}',
    '.turn-name strong{color:var(--red2)}\n.turn-banner.won{border-color:var(--gold2);box-shadow:0 0 30px rgba(217,180,90,.28)}\n.turn-banner.won .turn-label{background:var(--gold);color:#17201d}\n.turn-banner.won .turn-name strong{color:var(--gold2)}',
    1,
)

# 2) Cartas más limpias, especialmente J/Q/K.
s = s.replace(
    '.card-center{position:absolute;inset:26px 12px 26px;display:flex;align-items:center;justify-content:center}',
    '.card-center{position:absolute;inset:27px 10px 27px;display:flex;align-items:center;justify-content:center}\n.face-card .face-frame{width:56px;height:70px;border:1px solid #d8cfae;border-radius:9px;display:flex;flex-direction:column;align-items:center;justify-content:center;background:linear-gradient(145deg,#f1e7c4,#fffdf7 52%,#eadcae);box-shadow:inset 0 0 0 2px rgba(255,255,255,.45)}\n.face-card .face-letter{font-size:39px;font-weight:1000;line-height:.9}\n.face-card .face-suit{font-size:24px;line-height:1;margin-top:5px}',
    1,
)
s = s.replace(
    '.face-card .face-frame{width:52px;height:62px;border:2px solid currentColor;border-radius:7px;display:flex;flex-direction:column;align-items:center;justify-content:center;background:linear-gradient(135deg,#f4e7b6,#fffdf7 45%,#e7c969)}\n.face-card .face-letter{font-size:31px;font-weight:1000;line-height:1}\n.face-card .face-suit{font-size:23px;line-height:1;margin-top:2px}\n',
    '',
    1,
)

# 3) Área visible para los grupos bajados.
if 'id="tableGroups"' not in s:
    s = s.replace(
        '<div id="discard" class="discard-slot"></div><div id="message"',
        '<div id="discard" class="discard-slot"></div><div id="tableGroups" class="table-groups"></div><div id="message"',
        1,
    )

if '.table-groups{' not in s:
    s = s.replace(
        '.board-head .meta b{color:var(--gold2)}',
        '''.board-head .meta b{color:var(--gold2)}
.table-groups{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px;margin:10px 0 4px}
.lowered-group{padding:10px 12px;border:1px solid rgba(217,180,90,.28);border-radius:12px;background:rgba(5,24,19,.46)}
.lowered-group-head{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:8px}
.lowered-group-name{font-weight:850}.lowered-group-badge{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px}
.group-cards{display:flex;align-items:flex-end;gap:6px;min-height:76px}.group-cards .card{width:48px;height:68px;border-radius:8px;cursor:default;box-shadow:0 3px 8px #0004}.group-cards .card:hover{transform:none}
.group-cards .card-corner{left:4px;top:3px}.group-cards .card-corner.bottom{right:4px;bottom:3px}.group-cards .card-rank{font-size:13px}.group-cards .card-suit-small{font-size:11px;margin-top:1px}
.group-cards .card-center{inset:17px 6px 17px}.group-cards .pips{font-size:11px}.group-cards .ace-pip{font-size:27px}.group-cards .face-card .face-frame{width:32px;height:42px;border-radius:6px}.group-cards .face-card .face-letter{font-size:22px}.group-cards .face-card .face-suit{font-size:14px;margin-top:2px}
''',
        1,
    )

# 4) Temporizador de mensajes.
s = s.replace(
    'let autoSort=true, reconnectTimer=null, reconnectDelay=1000, pingTimer=null, intentionallyClosed=false;',
    'let autoSort=true, reconnectTimer=null, reconnectDelay=1000, pingTimer=null, intentionallyClosed=false, statusTimer=null;',
    1,
)
old_status = "function setStatus(t,c=''){$('message').textContent=t;$('message').className='status '+c;$('lobbyStatus').textContent=t}"
new_status = '''function setStatus(t,c='',duration=10000){
 clearTimeout(statusTimer);
 $('message').textContent=t||'';
 $('message').className='status '+(c||'');
 $('lobbyStatus').textContent=t||'';
 if(t&&duration>0){
   statusTimer=setTimeout(()=>{
     $('message').textContent='';
     $('message').className='status status-hidden';
     $('lobbyStatus').textContent='';
   },duration);
 }
}'''
if old_status in s:
    s = s.replace(old_status, new_status, 1)

# Successful state updates clear stale error messages.
s = s.replace(
    "function render(s){state=s;if(s.game_state){",
    "function render(s){state=s;clearTimeout(statusTimer);$('message').textContent='';$('message').className='status status-hidden';$('lobbyStatus').textContent='';if(s.game_state){",
    1,
)

# 5) Mostrar nombre real del ganador. current_player_id pasa a null al terminar.
old_header = '''function renderGame(){
 const ps=state.players||[];
 const activePlayer=ps.find(p=>p.id===state.current_player_id);
 const activeName=activePlayer?.name||'—';
 const myTurn=state.current_player_id===me && state.game_state==='playing';
 const won=state.game_state==='WON'||state.game_state==='won';
 $('turnStatus').textContent=won
   ? `Partida terminada · ganó ${state.winner?.reason||activeName||''}`
   : (myTurn?'Es tu turno.':'Turno de otro jugador.');
 $('turnName').innerHTML=`Turno de <strong>${esc(activeName)}</strong>`;
 $('turnSub').textContent=won?'Partida terminada.':(myTurn?'¡ES TU TURNO! Juega ahora.':'Espera a que termine su turno.');
 $('turnBanner').className=`turn-banner ${myTurn?'active':''}`;
'''
new_header = '''function renderGame(){
 const ps=state.players||[];
 const activePlayer=ps.find(p=>p.id===state.current_player_id);
 const winnerPlayer=ps.find(p=>p.id===state.winner?.player_id);
 const activeName=activePlayer?.name||'—';
 const winnerName=winnerPlayer?.name||'—';
 const myTurn=state.current_player_id===me && state.game_state==='playing';
 const won=state.game_state==='WON'||state.game_state==='won';
 $('turnStatus').textContent=won
   ? `Partida terminada · ${winnerName} ganó`
   : (myTurn?'Es tu turno.':'Turno de otro jugador.');
 $('turnName').innerHTML=won
   ? `¡GANÓ <strong>${esc(winnerName)}</strong>!`
   : `Turno de <strong>${esc(activeName)}</strong>`;
 $('turnSub').textContent=won
   ? 'Partida terminada.'
   : (myTurn?'¡ES TU TURNO! Juega ahora.':'Espera a que termine su turno.');
 $('turnBanner').className=`turn-banner ${myTurn?'active':''} ${won?'won':''}`;
'''
if old_header in s:
    s = s.replace(old_header, new_header, 1)

# 6) Sacar los grupos del sidebar y ponerlos sobre la mesa.
old_group_line = "     ${p.lowered_group?`<br><small>Grupo: ${p.lowered_group.cards.map(c=>displayRank(c.rank)+c.symbol).join(' ')}</small>`:''}\n"
s = s.replace(old_group_line, '', 1)
needle = """ }).join('');

 const mine=ps.find(p=>p.id===me);
"""
insert = """ }).join('');

 $('tableGroups').innerHTML=ps.filter(p=>p.lowered_group).map(p=>`<div class="lowered-group">
   <div class="lowered-group-head"><span class="lowered-group-name">${esc(p.name)}</span><span class="lowered-group-badge">Grupo ${p.lowered_group.cards.length}</span></div>
   <div class="group-cards">${p.lowered_group.cards.map(c=>cardHtml(c,true)).join('')}</div>
 </div>`).join('') || '<div class="card-caption">Aún no hay grupos bajados.</div>';

 const mine=ps.find(p=>p.id===me);
"""
if '$(\'tableGroups\').innerHTML=' not in s:
    if needle not in s:
        raise SystemExit('ERROR: no encontré el bloque de renderGame esperado.')
    s = s.replace(needle, insert, 1)

# 7) Pip layouts 8 y 10 más regulares.
s = s.replace(
    '  8:[[1,1],[3,1],[2,2],[1,3],[3,3],[2,4],[1,5],[3,5]],\n  9:[[1,1],[3,1],[1,2],[3,2],[2,3],[1,4],[3,4],[1,5],[3,5]],\n  10:[[1,1],[3,1],[2,2],[1,3],[3,3],[2,4],[1,5],[3,5],[1,4],[3,4]]',
    '  8:[[1,1],[3,1],[1,2],[3,2],[2,3],[1,4],[3,4],[1,5],[3,5]],\n  9:[[1,1],[3,1],[1,2],[3,2],[2,3],[1,4],[3,4],[1,5],[3,5]],\n  10:[[1,1],[3,1],[1,2],[3,2],[1,3],[3,3],[1,4],[3,4],[1,5],[3,5]]',
    1,
)

p.write_text(s)
print('OK: web/index.html actualizado.')
print('Cambios: mensajes 10s + grupos visibles + ganador por nombre + cartas refinadas.')
