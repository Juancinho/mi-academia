import type {AcademyCloud} from './academy-service.ts';
import {AcademyError,hash,knowledgeIdentity,normalized,text} from './academy-contract.ts';
import {validate_index_conversations} from './generated-validators.mjs';
import {notesFromSession} from './academy-notes.ts';
import type {IndexedConversation} from './conversation-contract.ts';
const at=()=>new Date().toISOString();
export async function indexConversations(s:AcademyCloud,input:any){
 const clean=structuredClone(input);if(!validate_index_conversations(clean))throw new AcademyError('Conversaciones inválidas: '+JSON.stringify(validate_index_conversations.errors).slice(0,800));
 let created=0,updated=0,skipped=0;const seen=new Set();
 // Each conversation is independently atomic. Report partial batch failure explicitly.
 const results:any[]=[];
 for(const c of clean.conversations as IndexedConversation[]){
  if(seen.has(c.id))throw new AcademyError('Conversación repetida en el lote.');seen.add(c.id);text(c.title,'Título',300);
  if(new TextEncoder().encode(JSON.stringify(c)).length>1500000)throw new AcademyError('Máximo 1,5 MB por conversación. Divide el material.');
  if(new Set(c.messages.map(m=>m.id)).size!==c.messages.length||c.messages.some(m=>!m.text.trim()))throw new AcademyError('Mensajes vacíos o con identificadores repetidos.');
  if(c.url){const u=new URL(c.url);if(u.protocol!=='https:'||u.username||u.password||!['chatgpt.com','chat.openai.com'].includes(u.hostname))throw new AcademyError('El enlace de conversación debe ser HTTPS de ChatGPT, sin credenciales.');}
  for(const d of [c.updated_at,...c.messages.map(m=>m.created_at)])if(d&&!Number.isFinite(Date.parse(d)))throw new AcademyError('Fecha de conversación inválida.');
  for(const id of c.session_ids||[])if(!await s.row('SELECT id FROM sessions WHERE id=?',id))throw new AcademyError('La conversación referencia una sesión inexistente.');
 }
 for(const c of clean.conversations as IndexedConversation[]){
  try{
   const {session_ids,...body}=c,identity=await hash(body),old=await s.row('SELECT * FROM conversations WHERE id=?',c.id),now=at(),statements:D1PreparedStatement[]=[];
   if(old?.hash===identity)skipped++;
   else{
    if(old){const previous=JSON.parse(old.data);if(previous.updated_at&&c.updated_at&&c.updated_at<previous.updated_at)throw new AcademyError('La exportación es anterior a la conversación guardada.',409);}
    statements.push(s.q('INSERT INTO conversations(id,data,hash,revision,updated_at) VALUES(?,?,?,1,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data,hash=excluded.hash,revision=conversations.revision+1,updated_at=excluded.updated_at',c.id,JSON.stringify(body),identity,now));
    statements.push(s.q('INSERT OR IGNORE INTO conversation_versions(id,conversation_id,data,created_at) VALUES(?,?,?,?)',await hash([c.id,identity]),c.id,JSON.stringify(body),now));
   }
   for(const sid of session_ids||[])statements.push(s.q('INSERT OR IGNORE INTO conversation_sessions(conversation_id,session_id) VALUES(?,?)',c.id,sid));
   if(statements.length)await s.guard('COALESCE((SELECT revision FROM conversations WHERE id=?),0)=?',[c.id,old?.revision||0],statements);
   if(old?.hash!==identity){if(old)updated++;else created++;}results.push({id:c.id,saved:true});
  }catch(e:any){return {created,updated,skipped,results,complete:false,error:e instanceof AcademyError?e.message:'No se pudo indexar una conversación.'};}
 }
 return {created,updated,skipped,complete:true,results};
}
export async function indexExisting(s:AcademyCloud){
 const sessions=await s.sessions();let created=0,linked=0;
 for(const session of sessions){
  if(await s.row('SELECT session_id FROM conversation_sessions WHERE session_id=?',session.id)){linked++;continue;}
  const source=session.sources.find((r:any)=>r.kind==='chatgpt'&&r.url&&/^https:\/\/(chatgpt.com|chat.openai.com)\//.test(r.url));
  const original=session.original_text?.trim(),extracts=session.knowledge.flatMap((k:any)=>k.evidence.filter((e:any)=>e.excerpt.trim()).map((e:any)=>k.title+' · '+e.locator+'\n'+e.excerpt)).join('\n\n');
  const body=original||extracts||('Resumen conservado de la sesión (no es una transcripción):\n'+session.summary);
  const result=await indexConversations(s,{conversations:[{id:'session:'+session.id,title:session.title,coverage:original?'provided':'extracts',...(source?{url:source.url}:{}),messages:Array.from({length:Math.ceil(body.length/200000)},(_,i)=>({id:'material-'+i,role:'material' as const,text:body.slice(i*200000,(i+1)*200000)})),session_ids:[session.id]}]});
  if(!result.complete)throw new AcademyError(result.error||'Indexación incompleta.');created+=result.created;
 }
 return {created,already_linked:linked,total:sessions.length};
}
export async function searchConversations(s:AcademyCloud,query='',offset=0){
 const tokens=query.normalize('NFKC').match(/[\p{L}\p{N}]+/gu)?.slice(0,12)||[];
 const match=tokens.map(t=>'"'+t.replaceAll('"','""')+'"*').join(' AND ');
 const rows=match?await s.rows('SELECT c.* FROM conversations c JOIN conversation_fts f ON f.id=c.id WHERE conversation_fts MATCH ? ORDER BY rank LIMIT 100 OFFSET ?',match,offset):await s.rows('SELECT * FROM conversations ORDER BY updated_at DESC,id LIMIT 100 OFFSET ?',offset);
 const count=match?await s.row('SELECT count(*) AS n FROM conversation_fts WHERE conversation_fts MATCH ?',match):await s.row('SELECT count(*) AS n FROM conversations');
 return {total:count.n,items:rows.map(r=>{const c=JSON.parse(r.data),content=c.messages.map((m:any)=>m.text).join('\n'),found=query?normalized(content).indexOf(normalized(query)):-1;return {id:r.id,title:c.title,url:c.url,coverage:c.coverage,messages:c.messages.length,revision:r.revision,updated_at:r.updated_at,snippet:content.slice(Math.max(0,found-90),Math.max(0,found-90)+240)};})};
}
export async function getConversation(s:AcademyCloud,id:string){
 const row=await s.row('SELECT * FROM conversations WHERE id=?',id);if(!row)throw new AcademyError('Conversación no encontrada.',404);
 const links=await s.rows('SELECT session_id FROM conversation_sessions WHERE conversation_id=?',id);
 return {...JSON.parse(row.data),revision:row.revision,session_ids:links.map(l=>l.session_id)};
}
export function noteCoverage(notes:any){
 const body=notes.sections.map((s:any)=>s.body).join('\n'),words=body.match(/\S+/g)?.length||0,examples=notes.sections.filter((s:any)=>s.kind==='ejemplo').length,diagrams=(body.match(/```mermaid/g)||[]).length;
 return {words,sections:notes.sections.length,examples,diagrams,objectives:notes.objectives.length,glossary:notes.glossary.length,label:words>=900&&notes.sections.length>=4&&notes.objectives.length?'Desarrollo extenso':'Desarrollo inicial',notice:'Indicadores de extensión y estructura; no evalúan exactitud ni comprensión.'};
}
export async function graphData(s:AcademyCloud){
 const [items,relations,books,conversations]=await Promise.all([s.library(),s.relations(),s.notebooks(),s.rows('SELECT conversation_id,session_id FROM conversation_sessions')]);
 const nodes=items.map((k:any)=>({id:k.id,title:k.title,type:'concept',topics:k.topics,stage:k.stage,epistemic:k.epistemic})),edges:any[]=relations.map((r:any)=>({id:r.id,source:r.from_id,target:r.to_id,label:r.label,explanation:r.explanation,type:'explicit'}));
 for(const b of books){nodes.push({id:'book:'+b.id,title:b.title,type:'notebook',topics:b.topics,stage:'',epistemic:''});}
 for(const session of await s.sessions())for(const k of session.knowledge)edges.push({id:'in:'+session.id+':'+k.id,source:await hash(knowledgeIdentity(k)),target:'book:'+session.id,label:'se estudia en',explanation:'Procedencia de la sesión',type:'provenance'});
 return {nodes,edges,conversation_links:conversations};
}
export async function vaultSnapshot(s:AcademyCloud){
 const sessions=await s.sessions(),books=await Promise.all(sessions.map(session=>s.notebook(session.id))),items=await s.library(),conversations=await s.rows('SELECT data FROM conversations'),links=await s.rows('SELECT * FROM conversation_sessions');
 return {format:'mi-academia-vault',version:1,created_at:at(),notebooks:books,knowledge:await Promise.all(items.map(async k=>({...k,...await s.detail(k.id)}))),relations:await s.relations(),conversations:conversations.map(c=>JSON.parse(c.data)),conversation_sessions:links};
}
