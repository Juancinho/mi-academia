'use client';
import {useEffect,useRef,useState} from 'react';
import {Check,ChevronRight,GraduationCap,RefreshCw} from 'lucide-react';
import {academyApi as api} from '../lib/academy-api';
import {MODES} from '../lib/academy-labels';
const when=(v:string)=>new Date(v).toLocaleString('es-ES',{timeZone:'Europe/Madrid'});
export default function StudyPractice({sessionId='',taskId='',onChanged}:{sessionId?:string;taskId?:string;onChanged:()=>void}){
 const [books,setBooks]=useState<any[]>([]),[scope,setScope]=useState(sessionId),[future,setFuture]=useState(!!sessionId||!!taskId),[mode,setMode]=useState(''),[tasks,setTasks]=useState<any[]>([]),[selected,setSelected]=useState(taskId);
 const [run,setRun]=useState(0),[loading,setLoading]=useState(true),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('');
 const [answer,setAnswer]=useState(''),[assisted,setAssisted]=useState(false),[attempt,setAttempt]=useState<any>(null),[score,setScore]=useState(2),[errors,setErrors]=useState(''),[completed,setCompleted]=useState<Record<string,number>>({});
 const attemptId=useRef(''),saving=useRef(false);
 useEffect(()=>{let active=true;api('action=notebooks').then(v=>{if(active)setBooks(v);}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};},[]);
 useEffect(()=>{
  let active=true;setLoading(true);setError('');setAttempt(null);setAnswer('');setCompleted({});setNotice('');attemptId.current='';
  const fetchTasks=async()=>{
   if(scope){const b=await api('action=notebook&id='+encodeURIComponent(scope));return b.tasks.filter((t:any)=>future||t.due<=new Date().toISOString());}
   return api('action=tasks'+(future?'&all=1':''));
  };
  fetchTasks().then(v=>{if(active){setTasks(v);setSelected(v.some((t:any)=>t.id===taskId)?taskId:v[0]?.id||'');}}).catch(e=>{if(active)setError(e.message);}).finally(()=>{if(active)setLoading(false);});return()=>{active=false;};
 },[scope,future,taskId,run]);
 const filtered=tasks.filter(t=>!mode||t.mode===mode),pending=filtered.filter(t=>completed[t.id]===undefined),done=filtered.length-pending.length;
 const task=pending.find(t=>t.id===selected)||pending[0];
 function reset(){setAnswer('');setAssisted(false);setAttempt(null);setScore(2);setErrors('');attemptId.current='';}
 async function fix(){
  if(!task||saving.current)return;saving.current=true;setBusy(true);setError('');
  if(!attemptId.current)attemptId.current=crypto.randomUUID();
  try{const v=await api('answer',{task_id:task.id,attempt_id:attemptId.current,expected_version:task.version,answer,assisted});setAttempt(v);}catch(e:any){setError(e.message);}finally{setBusy(false);saving.current=false;}
 }
 async function grade(){
  if(!task||!attempt||saving.current)return;saving.current=true;setBusy(true);setError('');
  try{const r=await api('review',{attempt_id:attempt.attempt_id,score,assisted:attempt.assisted,confirmed:true,errors});setCompleted(v=>({...v,[task.id]:score}));setNotice('Evaluación guardada · siguiente repaso: '+when(r.due));reset();setSelected(pending.find(t=>t.id!==task.id)?.id||'');onChanged();}catch(e:any){setError(e.message);}finally{setBusy(false);saving.current=false;}
 }
 return <div className="study-practice"><p className="eyebrow">RECUPERAR · EXPLICAR · RAZONAR · APLICAR</p><h1>Una tanda para aprender.</h1><p className="subtitle">Trabaja varias actividades de una sesión o combina temas. Cada respuesta conserva su evaluación y su calendario FSRS.</p>
  {error&&<div className="alert error" role="alert">{error}</div>}{notice&&<div className="alert success" role="status">{notice}</div>}
  <div className="practice-filters"><label>Material de estudio<select aria-label="Material de estudio" disabled={busy||!!attempt} value={scope} onChange={e=>{reset();setScope(e.target.value);}}><option value="">Toda mi academia</option>{books.map(b=><option key={b.id} value={b.id}>{b.title}</option>)}</select></label><label>Tipo de actividad<select aria-label="Tipo de actividad" disabled={busy||!!attempt} value={mode} onChange={e=>{reset();setMode(e.target.value);}}><option value="">Todos los tipos</option>{Object.entries(MODES).map(([id,name])=><option key={id} value={id}>{name}</option>)}</select></label></div>
  <label className="checkbox"><input type="checkbox" checked={future} disabled={busy||!!attempt} onChange={e=>{reset();setFuture(e.target.checked);}}/>Incluir actividades futuras. Evaluarlas recalculará su próxima fecha.</label>
  {!loading&&filtered.length>0&&<div className="practice-progress"><div><strong>{done} de {filtered.length} actividades completadas</strong><span>En esta tanda · {pending.length} pendientes</span></div><progress value={done} max={filtered.length} aria-label="Progreso de la tanda"/></div>}
  {loading?<p role="status">Preparando tu tanda…</p>:filtered.length===0?<section className="panel empty"><GraduationCap size={32}/><h2>No hay actividades con estos filtros.</h2><p>Prueba con otro cuaderno, incluye actividades futuras o registra una ampliación con más ejercicios desde ChatGPT.</p></section>:!pending.length?<section className="panel practice-finished"><GraduationCap size={42}/><p className="eyebrow">TANDA COMPLETADA</p><h2>Has trabajado {done} actividades.</h2><p>{Object.values(completed).filter(s=>s>=3).length} con puntuación 3 o 4. Consulta tus errores en Biblioteca y vuelve cuando toque repasar. Una tanda terminada no demuestra por sí sola dominio.</p><button className="secondary" onClick={()=>{reset();setRun(n=>n+1);}}><RefreshCw size={15}/> Preparar otra tanda</button></section>:<div className="review-layout"><section className="review-queue" aria-label="Actividades de la tanda">{filtered.map(t=><button key={t.id} disabled={busy||!!attempt||completed[t.id]!==undefined} className={'knowledge-row '+(task?.id===t.id?'selected':'')} onClick={()=>{reset();setSelected(t.id);}}><span className="caption">{MODES[t.mode]} {completed[t.id]!==undefined?'· Hecha · '+completed[t.id]+'/4':''}</span><h3>{t.title}</h3><p>{t.prompt}</p></button>)}</section>
   <section className="panel review-work">{task&&<><span className="badge">{MODES[task.mode]}</span><p className="caption">{task.title}</p><h2>{task.prompt}</h2>{task.epistemic==='cambiante'&&<div className="alert">Contenido sujeto a cambios · referencia: {task.as_of}.</div>}
    {!attempt?<><label>Tu respuesta<textarea aria-label="Tu respuesta" rows={8} maxLength={50000} disabled={busy} value={answer} onChange={e=>{setAnswer(e.target.value);attemptId.current='';}} placeholder="Recupera sin mirar, explica tu razonamiento o resuelve el ejercicio…"/></label><label className="checkbox"><input type="checkbox" checked={assisted} disabled={busy} onChange={e=>{setAssisted(e.target.checked);attemptId.current='';}}/>He usado apuntes, fuentes o ayuda.</label><button className="primary" disabled={busy||!answer.trim()} onClick={fix}>Fijar respuesta y contrastar <ChevronRight size={16}/></button></>:<><p className="caption">Respuesta fijada. La referencia se muestra después de tu intento.</p><pre className="answer-fixed">{attempt.answer}</pre><h3>Referencia y criterios</h3><pre>{attempt.expected_answer}</pre><ul className="rubric">{attempt.rubric.map((r:string,i:number)=><li key={i}><Check size={14}/>{r}</li>)}</ul><label>Mi puntuación<select aria-label="Mi puntuación" value={score} disabled={busy} onChange={e=>setScore(Number(e.target.value))}>{['0 · No pude responder','1 · Incorrecta o lagunas esenciales','2 · Parcial o con ayuda','3 · Correcta y autónoma','4 · Completa y fluida'].map((v,i)=><option key={i} value={i} disabled={attempt.assisted&&i>2}>{v}</option>)}</select></label><label>Errores o ideas que debo reforzar<textarea aria-label="Errores o lagunas" rows={3} maxLength={50000} disabled={busy} value={errors} onChange={e=>setErrors(e.target.value)}/></label><p className="caption">La valoración es tuya. Con ayuda: máximo 2. Al confirmar se guarda el intento y se programa el repaso antes de pasar a la siguiente actividad.</p><button className="primary" disabled={busy} onClick={grade}>Confirmar evaluación y continuar <Check size={16}/></button></>}
   </>}</section></div>}
 </div>;
}
