export type ChatMessage={id:string;role:'user'|'assistant'|'material';text:string;created_at?:string};
export type IndexedConversation={id:string;title:string;url?:string;messages:ChatMessage[];coverage:'active_branch'|'provided'|'extracts';updated_at?:string;session_ids?:string[]};
const str=(maxLength:number)=>({type:'string',minLength:1,maxLength});
export const conversationSchema={type:'object',additionalProperties:false,properties:{id:str(150),title:str(300),url:{type:'string',maxLength:2000},coverage:{enum:['active_branch','provided','extracts']},updated_at:{type:'string',maxLength:40},session_ids:{type:'array',items:str(100),maxItems:100,default:[]},messages:{type:'array',minItems:1,maxItems:2000,items:{type:'object',additionalProperties:false,properties:{id:str(150),role:{enum:['user','assistant','material']},text:str(200000),created_at:{type:'string',maxLength:40}},required:['id','role','text']}}},required:['id','title','messages','coverage']};
/** Parse only the selected active branch, never concatenate alternative assistant drafts. */
export function parseChatGPTExport(value:any):{conversations:IndexedConversation[];warnings:string[]}{
 const source=Array.isArray(value)?value:Array.isArray(value?.conversations)?value.conversations:[value],warnings:string[]=[],conversations:IndexedConversation[]=[];
 if(source.length>5000)throw new Error('Máximo 5000 conversaciones por archivo. Divide la exportación.');
 for(const c of source){
  if(!c?.mapping||typeof c.mapping!=='object')throw new Error('Se necesita una exportación de ChatGPT con mapping y mensajes.');
  const mapping=c.mapping,ids=Object.keys(mapping);if(ids.length>50000)throw new Error('Una conversación supera 50000 nodos.');
  let node=c.current_node;
  if(!node||!mapping[node]){const leaves=ids.filter(id=>!mapping[id]?.children?.length).sort((a,b)=>(mapping[b]?.message?.create_time||0)-(mapping[a]?.message?.create_time||0));node=leaves[0];warnings.push('Sin current_node: se ha elegido la rama terminal más reciente en '+String(c.title||'Sin título'));}
  const seen=new Set<string>(),branch:any[]=[];
  while(node){if(seen.has(node))throw new Error('El árbol de conversación contiene un ciclo.');seen.add(node);const n=mapping[node];if(!n)throw new Error('La rama referencia un nodo ausente.');branch.push(n.message);node=n.parent;}
  const messages:ChatMessage[]=[];
  for(const m of branch.reverse()){
   if(!m||!['user','assistant'].includes(m.author?.role))continue;
   const parts=m.content?.parts,body=Array.isArray(parts)?parts.filter((s:any)=>typeof s==='string').join('\n'):typeof m.content?.text==='string'?m.content.text:'';
   if(!body.trim()){warnings.push('Mensaje sin texto omitido en '+String(c.title||'Sin título'));continue;}
   messages.push({id:String(m.id||'message-'+messages.length),role:m.author.role,text:body,...(Number.isFinite(m.create_time)&&m.create_time>0?{created_at:new Date(m.create_time*1000).toISOString()}:{})});
  }
  if(!messages.length){warnings.push('Conversación sin texto omitida: '+String(c.title||'Sin título'));continue;}
  const id=String(c.id||c.conversation_id||'');if(!id)throw new Error('Conversación sin identificador estable.');
  conversations.push({id:'chatgpt:'+id,title:String(c.title||'Conversación sin título'),coverage:'active_branch',...( /^[a-f0-9-]{20,}$/i.test(id)?{url:'https://chatgpt.com/c/'+id}:{}),...(Number.isFinite(c.update_time)&&c.update_time>0?{updated_at:new Date(c.update_time*1000).toISOString()}:{}),messages});
 }
 return {conversations,warnings};
}
