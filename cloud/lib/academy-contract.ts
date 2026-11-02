import {validate_import as validate} from './generated-validators.mjs';
export {MODES,EPI,STAGES} from './academy-labels.ts';
export const CONFIG={version:'FSRS-6' as const,desiredRetention:0.9,enableShortTerm:true,learningSteps:['1m','10m'],relearningSteps:['10m'],enableFuzz:false,maximumInterval:36500};
export type Bundle={schema_version:1;sessions:any[]};
export class AcademyError extends Error{status:number;constructor(message:string,status=400){super(message);this.status=status;}}
export function parseBundle(value:unknown):Bundle{
 const clean=JSON.parse(JSON.stringify(value));
 if(!validate(clean))throw new AcademyError('JSON no válido: '+JSON.stringify(validate.errors).slice(0,1800));
 if(clean.sessions.reduce((n:number,s:any)=>n+s.knowledge.length,0)>100)throw new AcademyError('Máximo 100 conocimientos por lote alojado. Divide el archivo.');
 const seen=new Set();
 for(const s of clean.sessions){
  if(!/(?:Z|[+-]\d{2}:\d{2})$/.test(s.occurred_at)||!Number.isFinite(Date.parse(s.occurred_at)))throw new AcademyError('occurred_at necesita fecha, hora y zona horaria.');
  s.title=text(s.title,'Título de sesión',300);s.summary=text(s.summary,'Resumen');
  if(seen.has(s.external_id))throw new AcademyError('external_id repetido.');seen.add(s.external_id);
  if(new TextEncoder().encode(JSON.stringify(s)).length>900000)throw new AcademyError('Máximo 900 KB por sesión alojada.');
  const sources=new Set(s.sources.map((x:any)=>x.id)),ids=new Set(s.knowledge.map((x:any)=>x.id));
  if(sources.size!==s.sources.length||ids.size!==s.knowledge.length)throw new AcademyError('Identificadores locales repetidos.');
  for(const source of s.sources)if(source.url){let url:URL;try{url=new URL(source.url);}catch{throw new AcademyError('URL inválida.');}if(!['https:','http:'].includes(url.protocol)||url.username||url.password)throw new AcademyError('Las fuentes necesitan URL HTTP(S) sin credenciales.');}
  for(const k of s.knowledge){
   k.title=text(k.title,'Título de conocimiento',300);k.content=text(k.content,'Contenido');
   k.topics=k.topics.map((topic:string)=>text(topic,'Tema',300));
   for(const task of k.tasks){task.prompt=text(task.prompt,'Ejercicio');task.expected_answer=text(task.expected_answer,'Referencia');task.rubric=task.rubric.map((r:string)=>text(r,'Criterio',300));}
   if(k.epistemic==='cambiante'&&!k.as_of)throw new AcademyError('El conocimiento cambiante necesita as_of.');
   for(const d of [k.as_of,k.recheck_on])if(d&&(!/^\d{4}-\d{2}-\d{2}$/.test(d)||!Number.isFinite(Date.parse(d))||new Date(d).toISOString().slice(0,10)!==d))throw new AcademyError('Fecha de conocimiento inválida.');
   if(k.recheck_on&&k.as_of&&k.recheck_on<k.as_of)throw new AcademyError('recheck_on es anterior a as_of.');
   for(const e of k.evidence)if(!sources.has(e.source_id)||(!e.locator.trim()&&!e.excerpt.trim()))throw new AcademyError('Evidencia sin fuente, fragmento ni localizador válidos.');
  }
  for(const r of s.relations)if(!ids.has(r.from_id)||!ids.has(r.to_id)||r.from_id===r.to_id)throw new AcademyError('Relación con referencias inválidas.');
 }
 return clean;
}
export function canonical(v:any):string{if(Array.isArray(v))return '['+v.map(canonical).join(',')+']';if(v!==null&&typeof v==='object')return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}';return JSON.stringify(v);}
export async function hash(v:any){return [...new Uint8Array(await crypto.subtle.digest('SHA-256',new TextEncoder().encode(canonical(v))))].map(b=>b.toString(16).padStart(2,'0')).join('');}
export function normalized(s:string){return s.normalize('NFKC').toLowerCase().trim().replace(/\s+/g,' ');}
export function knowledgeIdentity(k:any){return [normalized(k.title),normalized(k.content),k.kind,k.epistemic,k.as_of||'',k.recheck_on||''];}
export function text(v:any,name:string,max=50000){if(typeof v!=='string'||!v.trim()||v.length>max)throw new AcademyError(`${name}: escribe entre 1 y ${max} caracteres.`);return v.trim();}
export function requireIdentity(request:Request){const id=request.headers.get('oai-authenticated-user-id');if(!id)throw new AcademyError('Inicia sesión con ChatGPT para acceder a Mi Academia.',401);return id;}
export function assertSameOrigin(request:Request){const origin=request.headers.get('origin');if(!origin||origin!==new URL(request.url).origin)throw new AcademyError('Origen de petición no permitido.',403);}
export function scoreToRating(score:unknown,assisted:boolean){if(!Number.isInteger(score)||Number(score)<0||Number(score)>4)throw new AcademyError('Puntuación entre 0 y 4.');if(assisted&&Number(score)>2)throw new AcademyError('Con ayuda la puntuación máxima es 2.');return assisted||Number(score)<=1?1:Number(score);}
