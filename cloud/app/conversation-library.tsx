'use client';
import {useEffect,useState} from 'react';
import {ArrowLeft,BookOpen,Search,Upload} from 'lucide-react';
import {academyApi as api} from '../lib/academy-api';
import {parseChatGPTExport,IndexedConversation,conversationSchema} from '../lib/conversation-contract';
import {validate_index_conversations} from '../lib/generated-validators.mjs';
import StudyText from './study-text';
export const COVERAGE:Record<string,string>={active_branch:'Rama activa de la exportación',provided:'Texto original aportado',extracts:'Solo fragmentos o resumen conservado'};
export function ConversationReader({id,onNotebook}:{id:string;onNotebook?:(id:string)=>void}){
 const [chat,setChat]=useState<any>(null),[error,setError]=useState(''),[find,setFind]=useState('');
 useEffect(()=>{let active=true;api('action=conversation&id='+encodeURIComponent(id)).then(v=>{if(active)setChat(v);}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};},[id]);
 if(error)return <div className="alert error">{error}</div>;if(!chat)return <p role="status">Cargando conversación…</p>;
 return <div className="conversation-reader"><div className="section-heading"><div><h2>{chat.title}</h2><span className="badge">{COVERAGE[chat.coverage]}</span></div>{chat.url&&<a className="secondary" href={chat.url} target="_blank" rel="noreferrer">Abrir en ChatGPT ↗</a>}</div>
  {chat.coverage==='extracts'&&<div className="alert">No se guardó la transcripción completa. Este registro contiene únicamente el material que se aportó a la academia.</div>}
  <label className="search"><Search size={16}/><input aria-label="Buscar dentro de la conversación" placeholder="Filtrar turnos por texto…" value={find} onChange={e=>setFind(e.target.value)}/></label>
  {chat.messages.filter((m:any)=>!find||m.text.toLocaleLowerCase().includes(find.toLocaleLowerCase())).map((m:any)=><article id={'message-'+m.id} className={'panel chat-message '+m.role} key={m.id}><p className="eyebrow">{m.role==='user'?'TÚ':m.role==='assistant'?'CHATGPT':'MATERIAL CONSERVADO'}{m.created_at?' · '+new Date(m.created_at).toLocaleString('es-ES'):''}</p><StudyText>{m.text}</StudyText></article>)}
  {!!onNotebook&&chat.session_ids.length>0&&<section className="panel"><h3>Cuadernos relacionados</h3>{chat.session_ids.map((sid:string)=><button className="secondary" key={sid} onClick={()=>onNotebook(sid)}><BookOpen size={15}/> Abrir cuaderno</button>)}</section>}
 </div>;
}
export default function ConversationLibrary({onNotebook,initialId=''}:{onNotebook:(id:string)=>void;initialId?:string}){
 const [query,setQuery]=useState(''),[offset,setOffset]=useState(0),[list,setList]=useState<any>({items:[],total:0}),[selected,setSelected]=useState(initialId),[tick,setTick]=useState(0),[error,setError]=useState(''),[busy,setBusy]=useState(false),[notice,setNotice]=useState('');
 const [incoming,setIncoming]=useState<IndexedConversation[]>([]),[checked,setChecked]=useState<Set<string>>(new Set()),[warnings,setWarnings]=useState<string[]>([]);
 useEffect(()=>{
  const registry=(document as Document&{modelContext?:{registerTool:(tool:any,options:{signal:AbortSignal})=>unknown}}).modelContext;
  if(!registry?.registerTool)return;const lifecycle=new AbortController();
  const tool={name:'index_conversations',title:'Indexar conversaciones aportadas',description:'Valida e indexa mensajes aportados, con su enlace de ChatGPT y los identificadores de los cuadernos relacionados. No recupera chats ausentes ni cambia el dominio demostrado.',inputSchema:{type:'object',additionalProperties:false,properties:{conversations:{type:'array',minItems:1,maxItems:50,items:conversationSchema}},required:['conversations']},async execute(input:unknown){
   const clean=structuredClone(input);if(!validate_index_conversations(clean))throw new Error('Conversaciones inválidas. Revisa mensajes, cobertura e identificadores.');
   setError('');try{const result=await api('index_conversations',clean);setTick(t=>t+1);setNotice(result.created+' conversaciones nuevas, '+result.updated+' actualizadas y '+result.skipped+' ya registradas.'+(result.complete?'':' '+result.error));return result;}catch(e:any){setError(e.message);throw e;}
  }};
  try{void Promise.resolve(registry.registerTool(tool,{signal:lifecycle.signal})).catch(()=>{});}catch{/* The ordinary interface remains available. */}
  return()=>lifecycle.abort();
 },[]);
 useEffect(()=>{let active=true;const timer=setTimeout(()=>api('action=conversations&query='+encodeURIComponent(query)+'&offset='+offset).then(v=>{if(active)setList(v);}).catch(e=>{if(active)setError(e.message);}),180);return()=>{active=false;clearTimeout(timer);};},[query,offset,tick]);
 useEffect(()=>{const url=new URL(window.location.href);url.searchParams.delete('notebook');if(selected)url.searchParams.set('conversation',selected);else url.searchParams.delete('conversation');window.history.replaceState(null,'',url);},[selected]);
 async function runImport(){setBusy(true);setError('');let saved=0;try{
  const chosen=incoming.filter(c=>checked.has(c.id));
  for(let n=0;n<chosen.length;n+=5){const result=await api('index_conversations',{conversations:chosen.slice(n,n+5)});saved+=result.created+result.updated+result.skipped;if(!result.complete)throw new Error(result.error+' · '+saved+' conversaciones procesadas; puedes reintentar sin duplicarlas.');setNotice(saved+' de '+chosen.length+' conversaciones indexadas.');}
  setIncoming([]);setChecked(new Set());setTick(t=>t+1);
 }catch(e:any){setError(e.message);}finally{setBusy(false);}}
 return <div><p className="eyebrow">EL ORIGEN, SIEMPRE A MANO</p><h1>Índice de conversaciones.</h1><p className="subtitle">Busca lo que preguntaste y vuelve al material que dio origen a tus apuntes.</p>{error&&<div className="alert error" role="alert">{error}</div>}{notice&&<div className="alert success" role="status">{notice}</div>}
  {selected?<><button className="text-button" onClick={()=>setSelected('')}><ArrowLeft size={16}/> Volver al índice</button><ConversationReader id={selected} onNotebook={onNotebook}/></>:<>
   <div className="button-row"><button className="secondary" disabled={busy} onClick={async()=>{setBusy(true);setError('');try{const r=await api('index_existing',{});setNotice(r.total+' sesiones revisadas: '+r.created+' registros nuevos; '+r.already_linked+' ya enlazadas.');setTick(t=>t+1);}catch(e:any){setError(e.message);}finally{setBusy(false);}}}>Indexar sesiones anteriores</button></div>
   <label className="search notebook-search"><Search size={16}/><input aria-label="Buscar conversaciones" value={query} placeholder="Busca en títulos y mensajes…" onChange={e=>{setQuery(e.target.value);setOffset(0);}}/></label><p className="caption">{list.total} conversaciones o registros de origen</p>
   <div className="notebook-grid">{list.items.map((c:any)=><button className="panel conversation-card" key={c.id} onClick={()=>setSelected(c.id)}><span className="badge">{COVERAGE[c.coverage]}</span><h2>{c.title}</h2><p>{c.snippet}…</p><span className="caption">{c.messages} turnos o bloques · versión {c.revision}</span></button>)}</div>
   {!list.total&&<div className="empty">Indexa las sesiones existentes o importa una exportación seleccionada. No hay acceso automático a otros chats privados.</div>}
   <div className="button-row"><button className="secondary" disabled={!offset} onClick={()=>setOffset(o=>Math.max(0,o-100))}>Anterior</button><button className="secondary" disabled={offset+100>=list.total} onClick={()=>setOffset(o=>o+100)}>Siguiente</button></div>
   <details className="panel"><summary>Importar conversaciones de ChatGPT</summary><p>Selecciona conversations.json de tu exportación y elige los chats que quieras indexar. El archivo se analiza en este navegador; solo se envían las conversaciones seleccionadas. Se conserva la rama activa y se omiten adjuntos sin texto.</p>
    <label className="upload"><Upload size={18}/> Elegir exportación JSON<input type="file" accept=".json,application/json" disabled={busy} onChange={async e=>{const f=e.target.files?.[0];if(!f)return;setError('');try{if(f.size>52428800)throw new Error('Máximo 50 MB por archivo. Divide la exportación.');const parsed=parseChatGPTExport(JSON.parse(await f.text()));setIncoming(parsed.conversations);setWarnings(parsed.warnings);setChecked(new Set());}catch(e:any){setError(e.message);}}}/></label>
    {!!warnings.length&&<details><summary>{warnings.length} avisos del archivo</summary><ul>{warnings.slice(0,30).map((w,i)=><li key={i}>{w}</li>)}</ul></details>}
    {!!incoming.length&&<><p>{incoming.length} conversaciones detectadas · {checked.size} seleccionadas</p><button className="secondary" disabled={busy} onClick={()=>setChecked(new Set(incoming.map(c=>c.id)))}>Seleccionar todas</button><button className="secondary" disabled={busy} onClick={()=>setChecked(new Set())}>Quitar selección</button><div className="import-chat-list">{incoming.map(c=><label className="checkbox" key={c.id}><input type="checkbox" disabled={busy} checked={checked.has(c.id)} onChange={e=>setChecked(ids=>{const next=new Set(ids);if(e.target.checked)next.add(c.id);else next.delete(c.id);return next;})}/>{c.title} · {c.messages.length} mensajes</label>)}</div><button className="primary" disabled={busy||!checked.size} onClick={runImport}>Indexar selección</button></>}
   </details>
  </>}
 </div>;
}
