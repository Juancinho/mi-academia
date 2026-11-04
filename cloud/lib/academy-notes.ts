/** Structured material assembled only from stored session content, without an AI call. */
export type NoteSection={title:string;body:string;kind:string;source_ids:string[];knowledge_ids:string[]};
export type StudyNotes={objectives:string[];sections:NoteSection[];glossary:{term:string;definition:string;source_ids:string[]}[];open_questions:string[]};
export const SECTION_KINDS:Record<string,string>={explicacion:'Explicación',ejemplo:'Ejemplo',procedimiento:'Paso a paso',comparacion:'Comparación',contexto:'Contexto',sintesis:'Síntesis'};
export function notesFromSession(session:any):StudyNotes{
 if(session.study_notes)return structuredClone(session.study_notes);
 return {objectives:[],sections:session.knowledge.map((k:any)=>({title:k.title,body:k.content,kind:k.kind==='procedimiento'?'procedimiento':'explicacion',source_ids:[...new Set(k.evidence.map((e:any)=>e.source_id))],knowledge_ids:[k.id]})),glossary:[],open_questions:[]};
}
export function notebookMarkdown(session:any,notes:StudyNotes){
 const lines=['# '+session.title,'',session.summary,'','## Objetivos','',...notes.objectives.map(s=>'- '+s),''];
 for(const section of notes.sections){
  lines.push('## '+section.title,'',section.body,'','Fuentes: '+section.source_ids.map(id=>'['+id+']').join(', '),'');
 }
 if(notes.glossary.length)lines.push('## Glosario','',...notes.glossary.flatMap(g=>['**'+g.term+'**: '+g.definition+' ('+g.source_ids.join(', ')+')','']));
 if(notes.open_questions.length)lines.push('## Dudas abiertas','',...notes.open_questions.map(s=>'- '+s),'');
 lines.push('## Referencias','');
 for(const source of session.sources)lines.push('- ['+source.id+'] '+source.title+(source.url?' — '+source.url:'')+(source.citation?' — '+source.citation:''),'');
 lines.push('## Procedencia','','Sesión: '+session.external_id,'Fecha: '+session.occurred_at,'','Apuntes de estudio. La lectura no demuestra dominio. Las referencias indican procedencia; no implican verificación externa.');
 return lines.join('\n');
}
