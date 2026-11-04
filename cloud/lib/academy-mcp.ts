import importSchema from './import-schema.json' with {type:'json'};
import {AcademyCloud} from './academy-service.ts';
import {AcademyError,requireIdentity} from './academy-contract.ts';

import {TOOLS,INSTRUCTIONS} from './academy-tools.ts';
export {TOOLS,INSTRUCTIONS};
import * as validators from './generated-validators.mjs';
export async function executeTool(service:AcademyCloud,name:string,args:any){
 const validate=(validators as any)[name==='preview_import'||name==='import_session'?'validate_import':'validate_'+name];if(!validate)throw new AcademyError('Herramienta desconocida.');if(!validate(args))throw new AcademyError('Argumentos inválidos: '+JSON.stringify(validate.errors).slice(0,1200));
 switch(name){
  case 'academy_status':return service.dashboard();case 'search_knowledge':return service.library(args.query,args.topic);case 'get_knowledge':return service.detail(args.knowledge_id);
  case 'get_due_reviews':return service.listTasks(!args.include_future);case 'get_connections':return service.relations();case 'get_import_schema':return importSchema;
  case 'search_notebooks':return service.notebooks(args.query);case 'get_notebook':return service.notebook(args.session_id);case 'save_notebook':return service.saveNotebook(args);
  case 'preview_import':return service.import(args,true);case 'import_session':return service.import(args);case 'submit_answer':return service.submitAnswer(args);
  case 'record_review':return service.recordReview(args);case 'mark_understanding':return service.exposure(args);case 'connect_knowledge':return service.connect(args);
 }
}
export async function handleMcp(request:Request,getService:()=>AcademyCloud){
 let msg:any;
 try{const raw=await request.text();if(new TextEncoder().encode(raw).length>10485760)throw new AcademyError('Petición demasiado grande.');msg=JSON.parse(raw);}catch{return Response.json({jsonrpc:'2.0',id:null,error:{code:-32700,message:'JSON no válido.'}},{status:400});}
 const id=msg.id??null,reply=(result:any)=>Response.json({jsonrpc:'2.0',id,result},{headers:{'Cache-Control':'no-store'}});
 if(msg.method==='server/discover')return reply({supportedVersions:['2026-07-28'],capabilities:{tools:{}},serverInfo:{name:'mi-academia',version:'0.3.0'},instructions:INSTRUCTIONS});
 if(msg.method==='initialize')return reply({protocolVersion:['2026-07-28','2025-06-18','2025-03-26','2024-11-05'].includes(msg.params?.protocolVersion)?msg.params.protocolVersion:'2025-03-26',capabilities:{tools:{}},serverInfo:{name:'mi-academia',version:'0.3.0'},instructions:INSTRUCTIONS});
 if(msg.method==='notifications/initialized'||msg.method==='notifications/cancelled')return new Response(null,{status:202});
 if(msg.method==='ping')return reply({});
 if(msg.method==='tools/list')return reply({tools:TOOLS});
 if(msg.method!=='tools/call')return Response.json({jsonrpc:'2.0',id,error:{code:-32601,message:'Método no disponible.'}});
 try{requireIdentity(request);const result=await executeTool(getService(),msg.params?.name,msg.params?.arguments||{});return reply({content:[{type:'text',text:JSON.stringify(result)}],isError:false});}
 catch(e:any){return reply({content:[{type:'text',text:e instanceof AcademyError?e.message:'No se pudo completar la operación. Inténtalo de nuevo.'}],isError:true});}
}
