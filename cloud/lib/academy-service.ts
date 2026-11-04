import {DefaultScheduler} from 'ts-fsrs';
import {AcademyError,CONFIG,STAGES,hash,knowledgeIdentity,normalized,parseBundle,parseNotes,scoreToRating,text} from './academy-contract.ts';
import {notesFromSession} from './academy-notes.ts';

const schedulerPromise=DefaultScheduler(CONFIG as any);
export async function scheduler(){return schedulerPromise;}
export function cardFromJSON(raw:string){return JSON.parse(raw,(key,value)=>typeof value==='string'&&['dueAt','lastReviewAt','createdAt'].includes(key)?new Date(value):value);}
const js=JSON.stringify;
const at=()=>new Date().toISOString();
const TABLES=['library_state','sessions','knowledge','evidence','knowledge_tags','tasks','task_sessions','relations','exposures','attempts','reviews','notebooks'];

export class AcademyCloud{
 db:D1Database;constructor(db:D1Database){this.db=db;}
 q(sql:string,...args:any[]){return this.db.prepare(sql).bind(...args);}
 async rows(sql:string,...args:any[]):Promise<any[]>{return (await this.q(sql,...args).all()).results;}
 async row(sql:string,...args:any[]):Promise<any>{return this.q(sql,...args).first();}
 async guard(sql:string,args:any[],statements:D1PreparedStatement[]){
  const token=crypto.randomUUID();
  try{return await this.db.batch([this.q(`INSERT INTO transaction_guards(id) SELECT CASE WHEN (${sql}) THEN ? ELSE NULL END`,...args,token),...statements,this.q('DELETE FROM transaction_guards WHERE id=?',token)]);}
  catch(e:any){if(String(e.message).includes('transaction_guards.id'))throw new AcademyError('Los datos cambiaron en otra sesión. Actualiza y vuelve a intentarlo.',409);throw e;}
 }
 async import(value:unknown,dryRun=false){
  const bundle=parseBundle(value);
  const [existing,known,tasks,version]=await Promise.all([this.rows('SELECT external_id,hash FROM sessions'),this.rows('SELECT id FROM knowledge'),this.rows('SELECT id FROM tasks'),this.row('SELECT revision FROM library_state WHERE id=1')]);
  const sessions=new Map(existing.map(s=>[s.external_id,s.hash])),knownIds=new Set(known.map(k=>k.id)),taskIds=new Set(tasks.map(t=>t.id));
  const summary={sessions:0,skipped:0,knowledge:0,reused:0,tasks:0};const statements:D1PreparedStatement[]=[];const now=at(),sch=await scheduler();
  for(const s of bundle.sessions){
   const fingerprint=await hash(s),sid=await hash(['session',s.external_id]);
   if(sessions.has(s.external_id)){if(sessions.get(s.external_id)!==fingerprint)throw new AcademyError(`La sesión ${s.external_id} ya tiene otro contenido. Usa un external_id nuevo.`);summary.skipped++;continue;}
   summary.sessions++;
   statements.push(this.q('INSERT INTO sessions(id,external_id,hash,payload,imported_at) VALUES(?,?,?,?,?)',sid,s.external_id,fingerprint,js(s),now));
   const ids=new Map<string,string>(),sources=new Map(s.sources.map((x:any)=>[x.id,x]));
   for(const k of s.knowledge){
    const kid=await hash(knowledgeIdentity(k));ids.set(k.id,kid);
    if(!knownIds.has(kid)){knownIds.add(kid);summary.knowledge++;const {evidence,tasks,topics,id,...body}=k;
     statements.push(this.q('INSERT INTO knowledge(id,data,created_at) VALUES(?,?,?)',kid,js(body),now));
     statements.push(this.q('INSERT INTO exposures(id,knowledge_id,level,note,created_at) VALUES(?,?,?,?,?)',crypto.randomUUID(),kid,'registrado','Registrado por importación.',now));
    }else summary.reused++;
    for(const topic of k.topics)statements.push(this.q('INSERT OR IGNORE INTO knowledge_tags(knowledge_id,normalized,label) VALUES(?,?,?)',kid,normalized(topic),topic));
    for(const ev of k.evidence){const data={...ev,source:sources.get(ev.source_id),session_title:s.title};statements.push(this.q('INSERT OR IGNORE INTO evidence(id,knowledge_id,session_id,data) VALUES(?,?,?,?)',await hash([kid,sid,data]),kid,sid,js(data)));}
    for(const task of k.tasks){
     const tid=await hash([kid,task.mode,normalized(task.prompt),normalized(task.expected_answer),task.rubric.map(normalized)]);
     if(!taskIds.has(tid)){taskIds.add(tid);summary.tasks++;const card=sch.newCard({cardId:tid,now:new Date(now)});statements.push(this.q('INSERT INTO tasks(id,knowledge_id,data,card,due,version) VALUES(?,?,?,?,?,0)',tid,kid,js(task),js(card),now));}
     statements.push(this.q('INSERT OR IGNORE INTO task_sessions(task_id,session_id) VALUES(?,?)',tid,sid));
    }
   }
   for(const r of s.relations){const from=ids.get(r.from_id)!,to=ids.get(r.to_id)!;if(from===to)throw new AcademyError('La deduplicación crearía una autorreferencia.');statements.push(this.q('INSERT OR IGNORE INTO relations(id,from_id,to_id,label,explanation,session_id) VALUES(?,?,?,?,?,?)',await hash([from,to,r.label,r.explanation]),from,to,r.label,r.explanation,sid));}
  }
  if(statements.length>900)throw new AcademyError('Demasiados elementos en el lote. Divídelo en sesiones más pequeñas.');
  if(!dryRun&&statements.length){statements.push(this.q('INSERT INTO library_state(id,revision) VALUES(1,1) ON CONFLICT(id) DO UPDATE SET revision=revision+1'));await this.guard('COALESCE((SELECT revision FROM library_state WHERE id=1),0)=?',[version?.revision??0],statements);}
  return summary;
 }
 async library(query='',topic=''){
  const results=await this.db.batch([this.q('SELECT * FROM knowledge ORDER BY created_at DESC,id'),this.q('SELECT * FROM knowledge_tags'),this.q('SELECT id,knowledge_id,card,due,version FROM tasks'),this.q('SELECT task_id,data,created_at FROM reviews ORDER BY created_at,id'),this.q('SELECT knowledge_id,level FROM exposures')]);
  const [knowledge,tags,tasks,reviews,exposures]=results.map(r=>r.results as any[]);const sch=await scheduler(),now=new Date();
  return knowledge.map(k=>{
   const data=JSON.parse(k.data),ktags=tags.filter(t=>t.knowledge_id===k.id).map(t=>t.label),ktasks=tasks.filter(t=>t.knowledge_id===k.id),seen=exposures.filter(e=>e.knowledge_id===k.id);
   let stage=seen.some(e=>e.level==='comprendido')?STAGES[2]:seen.some(e=>e.level==='leido')?STAGES[1]:STAGES[0];let total=0,mastered=ktasks.length>0;const recalls:number[]=[];
   for(const task of ktasks){
    const history=reviews.filter(r=>r.task_id===task.id).map(r=>JSON.parse(r.data));total+=history.length;if(history.length)stage=STAGES[3];
    const passes=history.filter(r=>r.score>=3&&!r.assisted),card=cardFromJSON(task.card);let recall=0;
    if(card.lastReviewAt){recall=sch.model.forgettingCurve(card,sch.chrono.difference(card.lastReviewAt,now));recalls.push(recall);}
    const last=history.at(-1);mastered=mastered&&passes.length>=2&&new Date(passes.at(-1).reviewed_at).getTime()-new Date(passes[0].reviewed_at).getTime()>=86400000&&!!last&&last.score>=3&&!last.assisted&&recall>=0.8;
   }
   if(mastered)stage=STAGES[4];
   return {...data,id:k.id,topics:ktags,stage,task_count:ktasks.length,review_count:total,recall:recalls.length?recalls.reduce((a,b)=>a+b,0)/recalls.length:null,created_at:k.created_at};
  }).filter(k=>(!query||normalized([k.title,k.content,...k.topics].join(' ')).includes(normalized(query)))&&(!topic||k.topics.includes(topic)));
 }
 async detail(id:string){
  const k=await this.row('SELECT * FROM knowledge WHERE id=?',id);if(!k)throw new AcademyError('Conocimiento no encontrado.',404);
  const [evidence,tasks,reviews,exposures]=await Promise.all([this.rows('SELECT * FROM evidence WHERE knowledge_id=?',id),this.rows('SELECT id,data,due,version FROM tasks WHERE knowledge_id=?',id),this.rows('SELECT r.* FROM reviews r JOIN tasks t ON t.id=r.task_id WHERE t.knowledge_id=? ORDER BY r.created_at DESC',id),this.rows('SELECT * FROM exposures WHERE knowledge_id=? ORDER BY created_at DESC',id)]);
  return {...JSON.parse(k.data),id,evidence:evidence.map(e=>({...JSON.parse(e.data),session_id:e.session_id})),tasks:tasks.map(t=>({...JSON.parse(t.data),id:t.id,due:t.due,version:t.version})),reviews:reviews.map(r=>JSON.parse(r.data)),exposures};
 }
 async listTasks(dueOnly=true){
  const rows=await this.rows('SELECT t.*,k.data AS knowledge FROM tasks t JOIN knowledge k ON k.id=t.knowledge_id '+(dueOnly?'WHERE t.due<=? ':'')+'ORDER BY t.due,t.id',...(dueOnly?[at()]:[]));
  return rows.map(t=>{const {expected_answer,rubric,...safe}=JSON.parse(t.data),k=JSON.parse(t.knowledge);return {...safe,id:t.id,knowledge_id:t.knowledge_id,title:k.title,epistemic:k.epistemic,as_of:k.as_of,recheck_on:k.recheck_on,due:t.due,version:t.version};});
 }
 async submitAnswer(input:any){
  const id=text(input.task_id,'Ejercicio',100),answer=text(input.answer,'Respuesta'),token=text(input.attempt_id,'Identificador del intento',100);
  if(typeof input.assisted!=='boolean')throw new AcademyError('Indica si has usado ayuda.');
  const existing=await this.row('SELECT * FROM attempts WHERE id=?',token),task=await this.row('SELECT * FROM tasks WHERE id=?',id);if(!task)throw new AcademyError('Ejercicio no encontrado.',404);
  if(existing){if(existing.task_id!==id||existing.answer!==answer||existing.assisted!==Number(input.assisted))throw new AcademyError('Identificador utilizado para otra respuesta.',409);}
  else{if(task.version!==input.expected_version)throw new AcademyError('El ejercicio cambió; actualiza antes de responder.',409);
   try{await this.q('INSERT INTO attempts(id,task_id,answer,assisted,version,created_at) VALUES(?,?,?,?,?,?)',token,id,answer,Number(input.assisted),task.version,at()).run();}
   catch(e){const again=await this.row('SELECT * FROM attempts WHERE id=?',token);if(!again||again.task_id!==id||again.answer!==answer||again.assisted!==Number(input.assisted))throw e;}
  }
  const data=JSON.parse(task.data);return {attempt_id:token,answer,assisted:input.assisted,prompt:data.prompt,expected_answer:data.expected_answer,rubric:data.rubric,notice:'Respuesta fijada. Revisa la rúbrica y confirma la puntuación. Todavía no se ha registrado un repaso ni cambiado FSRS.'};
 }
 async recordReview(input:any){
  if(input.confirmed!==true)throw new AcademyError('El usuario debe confirmar la puntuación para registrar el repaso.');
  const attempt=await this.row('SELECT * FROM attempts WHERE id=?',text(input.attempt_id,'Intento',100));if(!attempt)throw new AcademyError('Primero fija una respuesta al ejercicio.',404);
  const assisted=Boolean(attempt.assisted)||input.assisted===true,rating=scoreToRating(input.score,assisted),feedback=typeof input.feedback==='string'?input.feedback.trim():'',errors=typeof input.errors==='string'?input.errors.trim():'';
  if(feedback.length>50000||errors.length>50000)throw new AcademyError('Comentario demasiado largo.');
  const previous=await this.row('SELECT data FROM reviews WHERE id=?',attempt.id);
  if(previous){const r=JSON.parse(previous.data);if(r.score!==input.score||r.assisted!==assisted||r.feedback!==feedback||r.errors!==errors)throw new AcademyError('El intento ya tiene otra evaluación.',409);return r;}
  const task=await this.row('SELECT * FROM tasks WHERE id=?',attempt.task_id);if(task.version!==attempt.version)throw new AcademyError('Otra sesión ya evaluó el ejercicio. Actualiza para un nuevo intento.',409);
  const now=new Date(),sch=await scheduler(),card=cardFromJSON(task.card),result=sch.review({card,now,grade:rating as any}),nextDue=(result.card as any).dueAt;
  if(!(nextDue instanceof Date)||!Number.isFinite(nextDue.getTime()))throw new Error('FSRS produjo una fecha inválida.');
  const review={id:attempt.id,task_id:task.id,answer:attempt.answer,score:input.score,assisted,rating,feedback,errors,reviewed_at:now.toISOString(),answer_fixed_at:attempt.created_at,card_before:JSON.parse(task.card),card_after:result.card,log:result.revlog,scheduler:CONFIG,engine:'ts-fsrs@6.0.0',evaluator:'user_confirmed',due:nextDue.toISOString()};
  await this.guard('(SELECT version FROM tasks WHERE id=?)=?',[task.id,attempt.version],[this.q('INSERT INTO reviews(id,task_id,version,data,created_at) VALUES(?,?,?,?,?)',attempt.id,task.id,attempt.version,js(review),review.reviewed_at),this.q('UPDATE tasks SET card=?,due=?,version=version+1 WHERE id=? AND version=?',js(result.card),review.due,task.id,attempt.version)]);
  return review;
 }
 async exposure(input:any){
  if(!['leido','comprendido'].includes(input.level))throw new AcademyError('Valoración inválida.');if(!await this.row('SELECT id FROM knowledge WHERE id=?',input.knowledge_id))throw new AcademyError('Conocimiento no encontrado.',404);
  const note=String(input.note||'').trim();if(note.length>10000)throw new AcademyError('Nota demasiado larga.');await this.q('INSERT INTO exposures(id,knowledge_id,level,note,created_at) VALUES(?,?,?,?,?)',crypto.randomUUID(),input.knowledge_id,input.level,note,at()).run();return {saved:true,notice:'Valoración personal registrada; no equivale a dominio.'};
 }
 async connect(input:any){
  if(input.from_id===input.to_id)throw new AcademyError('Elige conocimientos distintos.');const label=text(input.label,'Relación',300),explanation=String(input.explanation||'').trim();if(explanation.length>10000)throw new AcademyError('Explicación demasiado larga.');
  if((await this.rows('SELECT id FROM knowledge WHERE id IN (?,?)',input.from_id,input.to_id)).length!==2)throw new AcademyError('Conocimiento no encontrado.',404);
  await this.q('INSERT OR IGNORE INTO relations(id,from_id,to_id,label,explanation,session_id) VALUES(?,?,?,?,?,NULL)',await hash([input.from_id,input.to_id,label,explanation]),input.from_id,input.to_id,label,explanation).run();return {saved:true};
 }
 async sessions(){return (await this.rows('SELECT * FROM sessions ORDER BY imported_at DESC')).map(s=>({...JSON.parse(s.payload),id:s.id,imported_at:s.imported_at}));}
 async notebooks(query=''){
  const [sessions,edits]=await Promise.all([this.sessions(),this.rows('SELECT * FROM notebooks')]);
  return sessions.map(s=>{
   const edited=edits.find(n=>n.session_id===s.id),notes=edited?JSON.parse(edited.data):notesFromSession(s);
   return {id:s.id,title:s.title,summary:s.summary,occurred_at:s.occurred_at,topics:[...new Set(s.knowledge.flatMap((k:any)=>k.topics))],section_count:notes.sections.length,knowledge_count:s.knowledge.length,task_count:s.knowledge.reduce((n:number,k:any)=>n+k.tasks.length,0),source_count:s.sources.length,edited:!!edited,updated_at:edited?.updated_at||s.imported_at,_search:normalized([s.title,s.summary,...s.sources.map((r:any)=>r.title),JSON.stringify(notes),...s.knowledge.flatMap((k:any)=>k.topics)].join(' '))};
  }).filter(s=>!query||s._search.includes(normalized(query))).map(({_search,...s})=>s);
 }
 async notebook(id:string){
  const row=await this.row('SELECT * FROM sessions WHERE id=?',id);if(!row)throw new AcademyError('Cuaderno no encontrado.',404);
  const session=JSON.parse(row.payload),edited=await this.row('SELECT * FROM notebooks WHERE session_id=?',id);
  const [links,allTasks]=await Promise.all([this.rows('SELECT task_id FROM task_sessions WHERE session_id=?',id),this.listTasks(false)]),taskIds=new Set(links.map(t=>t.task_id));
  const concepts=await Promise.all(session.knowledge.map(async(k:any)=>({...k,id:await hash(knowledgeIdentity(k))})));
  const {study_notes,knowledge:originalKnowledge,...original}=session;
  return {id,...original,knowledge:originalKnowledge.map(({tasks,...k}:any)=>k),notes:edited?JSON.parse(edited.data):notesFromSession(session),version:edited?.version||0,origin:edited?'edited':study_notes?'imported':'assembled',updated_at:edited?.updated_at||row.imported_at,concepts:concepts.map(({tasks,...k}:any)=>k),tasks:allTasks.filter(t=>taskIds.has(t.id))};
 }
 async saveNotebook(input:any){
  const id=text(input.session_id,'Cuaderno',100),row=await this.row('SELECT payload FROM sessions WHERE id=?',id);if(!row)throw new AcademyError('Cuaderno no encontrado.',404);
  if(!Number.isInteger(input.expected_version)||input.expected_version<0)throw new AcademyError('Versión del cuaderno inválida.');
  const notes=parseNotes(input.notes,JSON.parse(row.payload)),existing=await this.row('SELECT * FROM notebooks WHERE session_id=?',id);
  if(existing&&await hash(JSON.parse(existing.data))===await hash(notes))return {saved:true,version:existing.version,updated_at:existing.updated_at};
  const version=(existing?.version||0)+1,now=at();
  await this.guard('COALESCE((SELECT version FROM notebooks WHERE session_id=?),0)=?',[id,input.expected_version],[this.q('INSERT INTO notebooks(session_id,data,version,updated_at) VALUES(?,?,?,?) ON CONFLICT(session_id) DO UPDATE SET data=excluded.data,version=excluded.version,updated_at=excluded.updated_at',id,js(notes),version,now)]);
  return {saved:true,version,updated_at:now};
 }
 async relations(){return (await this.rows('SELECT r.*,a.data AS from_data,b.data AS to_data FROM relations r JOIN knowledge a ON a.id=r.from_id JOIN knowledge b ON b.id=r.to_id')).map(r=>({...r,from_title:JSON.parse(r.from_data).title,to_title:JSON.parse(r.to_data).title,from_data:undefined,to_data:undefined}));}
 async dashboard(){
  const [items,tasks,sessions,reviews,relations]=await Promise.all([this.library(),this.listTasks(false),this.sessions(),this.rows('SELECT data FROM reviews ORDER BY created_at'),this.relations()]);const now=at(),all=reviews.map(r=>JSON.parse(r.data)),today=new Date().toLocaleDateString('en-CA',{timeZone:'Europe/Madrid'}),calendar=[];
  for(let n=0;n<30;n++){const date=new Date(today+'T12:00:00Z');date.setUTCDate(date.getUTCDate()+n);const key=date.toISOString().slice(0,10);calendar.push({date:key,count:tasks.filter(t=>new Date(t.due).toLocaleDateString('en-CA',{timeZone:'Europe/Madrid'})===key).length});}
  return {knowledge:items.length,sessions:sessions.length,tasks:tasks.length,due:tasks.filter(t=>t.due<=now).length,demonstrated:items.filter(k=>k.stage===STAGES[4]).length,without_tasks:items.filter(k=>!k.task_count).length,reviews:all.length,success:all.length?all.filter(r=>r.score>=3&&!r.assisted).length/all.length:null,overdue:tasks.filter(t=>new Date(t.due).toLocaleDateString('en-CA',{timeZone:'Europe/Madrid'})<today).length,recheck:items.filter(k=>k.recheck_on&&k.recheck_on<=today).length,counts:STAGES.map(stage=>({stage,count:items.filter(k=>k.stage===stage).length})),calendar,recent:items.slice(0,5),relations:relations.length,activity:all.slice(-30).map(r=>({at:r.reviewed_at,score:r.score,assisted:r.assisted})),engine:'FSRS-6 / ts-fsrs 6.0.0'};
 }
 async export(sessionsOnly=false){
  if(sessionsOnly)return {schema_version:1,sessions:(await this.sessions()).map(({id,imported_at,...s})=>s)};
  const rows=await this.db.batch(TABLES.map(t=>this.q(`SELECT * FROM ${t}`)));return {format:'mi-academia-cloud-backup',schema_version:1,created_at:at(),scheduler:CONFIG,tables:Object.fromEntries(TABLES.map((t,i)=>[t,rows[i].results]))};
 }
 async restore(backup:any){
  if(backup?.format!=='mi-academia-cloud-backup'||backup.schema_version!==1||!backup.tables)throw new AcademyError('No es un respaldo compatible de Mi Academia en la nube.');
  const columns:Record<string,string[]>={knowledge:['id','data','created_at'],sessions:['id','external_id','hash','payload','imported_at'],knowledge_tags:['knowledge_id','normalized','label'],evidence:['id','knowledge_id','session_id','data'],tasks:['id','knowledge_id','data','card','due','version'],task_sessions:['task_id','session_id'],relations:['id','from_id','to_id','label','explanation','session_id'],exposures:['id','knowledge_id','level','note','created_at'],attempts:['id','task_id','answer','assisted','version','created_at'],reviews:['id','task_id','version','data','created_at'],library_state:['id','revision']};
  columns.notebooks=['session_id','data','version','updated_at'];
  const tables={...backup.tables};
  // Older snapshots predate notebooks; restore them without changing their session hashes.
  if(!('notebooks' in tables))tables.notebooks=[];
  if(Object.keys(tables).sort().join('|')!==Object.keys(columns).sort().join('|'))throw new AcademyError('El respaldo no contiene las tablas esperadas.');
  const statements:D1PreparedStatement[]=[];const sch=await scheduler();
  for(const [table,keys] of Object.entries(columns)){
   const rows=tables[table];if(!Array.isArray(rows))throw new AcademyError('Tabla de respaldo inválida.');
   for(const row of rows){
    if(!row||Object.keys(row).sort().join('|')!==[...keys].sort().join('|')||Object.values(row).some(v=>v!==null&&typeof v!=='string'&&typeof v!=='number'))throw new AcademyError('Fila de respaldo inválida.');
    if(table==='sessions')parseBundle({schema_version:1,sessions:[JSON.parse(row.payload)]});
    if(table==='tasks'){const card=cardFromJSON(row.card);const checked=await (sch as any).schema.card['~standard'].validate(card);if(checked.issues||new Date(row.due).toISOString()!==card.dueAt.toISOString())throw new AcademyError('Estado FSRS inválido en el respaldo.');}
    if(table==='reviews'){const r=JSON.parse(row.data);scoreToRating(r.score,r.assisted);if(r.id!==row.id||r.task_id!==row.task_id)throw new AcademyError('Historial inconsistente.');}
    if(table==='notebooks'){
     const session=tables.sessions.find((s:any)=>s.id===row.session_id);
     if(!session||!Number.isInteger(row.version)||row.version<1||!Number.isFinite(Date.parse(row.updated_at)))throw new AcademyError('Cuaderno inconsistente en el respaldo.');
     parseNotes(JSON.parse(row.data),JSON.parse(session.payload));
    }
    statements.push(this.q(`INSERT INTO ${table}(${keys.join(',')}) VALUES(${keys.map(()=>'?').join(',')})`,...keys.map(k=>row[k])));
   }
  }
  if(statements.length>900)throw new AcademyError('El respaldo supera el tamaño de restauración de esta versión; consérvalo para una migración asistida.');
  if(!statements.length)return {restored:true};
  await this.guard(TABLES.map(t=>`(SELECT count(*) FROM ${t})=0`).join(' AND '),[],statements);
  return {restored:true,rows:statements.length};
 }
}
