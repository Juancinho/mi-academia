import {env} from 'cloudflare:workers';
import {AcademyCloud} from '../../../lib/academy-service';
import {AcademyError,assertSameOrigin,requireIdentity} from '../../../lib/academy-contract';
export const dynamic='force-dynamic';
const json=(value:any,status=200)=>Response.json(value,{status,headers:{'Cache-Control':'no-store'}});
export async function GET(request:Request){
 try{requireIdentity(request);if(!env.DB)throw new Error('DB no disponible');const s=new AcademyCloud(env.DB),u=new URL(request.url),action=u.searchParams.get('action');
  switch(action){
   case 'dashboard':return json(await s.dashboard());case 'library':return json(await s.library(u.searchParams.get('query')||'',u.searchParams.get('topic')||''));case 'detail':return json(await s.detail(u.searchParams.get('id')||''));
   case 'tasks':return json(await s.listTasks(u.searchParams.get('all')!=='1'));case 'sessions':return json(await s.sessions());case 'relations':return json(await s.relations());
   case 'notebooks':return json(await s.notebooks(u.searchParams.get('query')||''));case 'notebook':return json(await s.notebook(u.searchParams.get('id')||''));
   case 'conversations':return json(await s.conversations(u.searchParams.get('query')||'',Math.max(0,Number(u.searchParams.get('offset'))||0)));case 'conversation':return json(await s.conversation(u.searchParams.get('id')||''));
   case 'graph':return json(await s.graph());case 'study_brief':return json(await s.studyBrief(u.searchParams.get('id')||''));
   case 'export':{const output=await s.export(u.searchParams.get('sessions')==='1');return new Response(JSON.stringify(output,null,2),{headers:{'Content-Type':'application/json; charset=utf-8','Content-Disposition':`attachment; filename="mi-academia-${u.searchParams.get('sessions')==='1'?'sesiones':'cloud-backup'}.json"`,'Cache-Control':'no-store'}});}
   default:throw new AcademyError('Consulta no disponible.',404);
  }
 }catch(e:any){console.error('Academy read failed',e instanceof AcademyError?e.message:e.name);return json({error:e instanceof AcademyError?e.message:'No se pudieron consultar los datos.'},e instanceof AcademyError?e.status:500);}
}
export async function POST(request:Request){
 try{requireIdentity(request);assertSameOrigin(request);if(!request.headers.get('content-type')?.startsWith('application/json'))throw new AcademyError('Se necesita JSON.');const raw=await request.text();if(new TextEncoder().encode(raw).length>10485760)throw new AcademyError('Máximo 10 MB.');const input=JSON.parse(raw);if(!env.DB)throw new Error('DB no disponible');const s=new AcademyCloud(env.DB);
  switch(input.action){case 'index_existing':return json(await s.indexExisting());case 'index_conversations':return json(await s.indexConversations({conversations:input.conversations}));case 'save_notebook':return json(await s.saveNotebook(input));case 'preview':return json(await s.import(input.bundle,true));case 'import':return json(await s.import(input.bundle));case 'restore':return json(await s.restore(input.backup));case 'answer':return json(await s.submitAnswer(input));case 'review':return json(await s.recordReview(input));case 'exposure':return json(await s.exposure(input));case 'connect':return json(await s.connect(input));default:throw new AcademyError('Acción no disponible.',404);}
 }catch(e:any){console.error('Academy write failed',e instanceof AcademyError?e.message:e.name);return json({error:e instanceof AcademyError?e.message:e instanceof SyntaxError?'JSON no válido.':'No se pudo guardar la operación.'},e instanceof AcademyError?e.status:400);}
}
