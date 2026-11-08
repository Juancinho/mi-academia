import {test} from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync,readdirSync} from 'node:fs';
import {AcademyCloud} from '../lib/academy-service.ts';
import {parseBundle} from '../lib/academy-contract.ts';
import {notesFromSession,notebookMarkdown} from '../lib/academy-notes.ts';
import {executeTool} from '../lib/academy-mcp.ts';
import {safeStudyUrl} from '../lib/study-urls.ts';
import studyExample from '../lib/example-study-session.json' with {type:'json'};
import example from '../lib/example-session.json' with {type:'json'};
class TestD1{
 db=new DatabaseSync(':memory:');
 constructor(latest=true){this.db.exec('PRAGMA foreign_keys=ON');for(const file of readdirSync(new URL('../drizzle/',import.meta.url)).filter(f=>f.endsWith('.sql')&&(latest||f.startsWith('0000'))).sort())this.db.exec(readFileSync(new URL('../drizzle/'+file,import.meta.url),'utf8'));}
 prepare(sql:string){const self=this;let args:any[]=[];const statement={bind(...v:any[]){args=v;return statement;},async first(){return self.db.prepare(sql).get(...args)||null;},async all(){return {results:self.db.prepare(sql).all(...args)};},async run(){const r=self.db.prepare(sql).run(...args);return {meta:{changes:Number(r.changes)}};},_sql:sql,_args:()=>args};return statement;}
 async batch(statements:any[]){this.db.exec('BEGIN');try{const out=statements.map(s=>({results:this.db.prepare(s._sql).all(...s._args())}));this.db.exec('COMMIT');return out;}catch(e){this.db.exec('ROLLBACK');throw e;}}
}
const clone=()=>structuredClone(example) as any;
test('study example imports a complete notebook and remains pending consolidation',async()=>{
 const s=new AcademyCloud(new TestD1() as any);assert.equal((await s.import(studyExample)).tasks,7);const book=await s.notebook((await s.notebooks())[0].id);
 assert.equal(book.origin,'imported');assert.equal(book.notes.sections.length,4);assert.ok(book.notes.glossary.length);assert.ok((await s.library()).every(k=>k.stage==='Registrado'));
});
test('study links reject executable schemes, credential URLs and remote relative paths',()=>{
 for(const url of ['javascript:alert(1)','data:text/html,evil','file:///C:/secret','//tracker.test/x','https://user:pass@example.test','/api/academy?action=export'])assert.equal(safeStudyUrl(url),'');
 for(const url of ['https://example.test/source','http://example.test/source','#section'])assert.equal(safeStudyUrl(url),url);
});
async function setup(){const s=new AcademyCloud(new TestD1() as any);await s.import(clone());const books=await s.notebooks();return {s,id:books[0].id};}
test('existing sessions gain notebooks after migration without rewriting original data or FSRS',async()=>{
 const seed=new AcademyCloud(new TestD1() as any);await seed.import(clone());const snapshot:any=await seed.export();const db=new TestD1(false),s=new AcademyCloud(db as any);for(const name of ['library_state','sessions','knowledge','evidence','knowledge_tags','tasks','task_sessions','relations','exposures','attempts','reviews'])for(const row of snapshot.tables[name]){const keys=Object.keys(row);db.db.prepare('INSERT INTO '+name+'('+keys.join(',')+') VALUES('+keys.map(()=>'?').join(',')+')').run(...keys.map(k=>row[k]));}
 const original=await s.sessions(),tasks=await s.rows('SELECT * FROM tasks');
 for(const file of readdirSync(new URL('../drizzle/',import.meta.url)).filter(f=>f.endsWith('.sql')&&!f.startsWith('0000')).sort())db.db.exec(readFileSync(new URL('../drizzle/'+file,import.meta.url),'utf8'));
 const book=await s.notebook(original[0].id);assert.equal(book.origin,original[0].study_notes?'imported':'assembled');assert.ok(book.notes.sections.length);assert.equal(book.tasks.length,7);
 assert.deepEqual(await s.sessions(),original);assert.deepEqual(await s.rows('SELECT * FROM tasks'),tasks);assert.equal((await s.rows('SELECT * FROM notebooks')).length,0);
});
test('structured notes validate sources, concept references and mandatory provenance',()=>{
 const p=clone(),session=p.sessions[0];session.study_notes=notesFromSession(session);
 assert.ok(parseBundle(p).sessions[0].study_notes.sections.length);
 for(const mutate of [(s:any)=>s.study_notes.sections[0].source_ids=['absent'],(s:any)=>s.study_notes.sections[0].knowledge_ids=['absent'],(s:any)=>s.study_notes.sections[0].body=' ',(s:any)=>s.study_notes.sections[0].source_ids=[]]){
  const v=structuredClone(p);mutate(v.sessions[0]);assert.throws(()=>parseBundle(v));
 }
 const v=structuredClone(p);v.sessions[0].study_notes.glossary=[{term:'Término',definition:'Definición',source_ids:['absent']}];assert.throws(()=>parseBundle(v));
});
test('notebooks expose scoped activities without leaking assessment solutions or rubrics',async()=>{
 const {s,id}=await setup(),book=await s.notebook(id);
 assert.ok(book.knowledge.every((k:any)=>!('tasks' in k)));assert.ok(book.concepts.every((k:any)=>!('tasks' in k)));
 assert.ok(book.tasks.every((t:any)=>!('expected_answer' in t)&&!('rubric' in t)));assert.equal(new Set(book.tasks.map((t:any)=>t.mode)).size,7);
 const p=clone();p.sessions[0].external_id='logic-only';p.sessions[0].knowledge=p.sessions[0].knowledge.slice(0,1);p.sessions[0].relations=[];delete p.sessions[0].study_notes;
 await s.import(p);const other=(await s.notebooks()).find(b=>b.id!==id)!;assert.equal((await s.notebook(other.id)).tasks.length,3);
});
test('notes can be edited idempotently without changing original session hashes or study states',async()=>{
 const {s,id}=await setup(),before=await s.export() as any,book=await s.notebook(id);
 book.notes.sections[0].body+='\nMi explicación personal.';const args={session_id:id,expected_version:0,notes:book.notes};
 const saved=await s.saveNotebook(args);assert.equal(saved.version,1);assert.deepEqual(await s.saveNotebook(args),saved);
 const after=await s.export() as any;for(const table of Object.keys(before.tables).filter(t=>t!=='notebooks'))assert.deepEqual(after.tables[table],before.tables[table],table);
 assert.equal((await s.import(clone())).skipped,1);assert.equal((await s.notebook(id)).origin,'edited');
});
test('concurrent edits cannot overwrite another notebook revision',async()=>{
 const {s,id}=await setup(),book=await s.notebook(id),first=structuredClone(book.notes),second=structuredClone(book.notes);
 first.sections[0].body='Edición A';second.sections[0].body='Edición B';
 await s.saveNotebook({session_id:id,expected_version:0,notes:first});
 await assert.rejects(()=>s.saveNotebook({session_id:id,expected_version:0,notes:second}),/cambiaron/);
 assert.equal((await s.notebook(id)).notes.sections[0].body,'Edición A');
 await s.saveNotebook({session_id:id,expected_version:1,notes:second});assert.equal((await s.notebook(id)).version,2);
});
test('invalid edits leave saved notes untouched and search includes edited prose',async()=>{
 const {s,id}=await setup(),book=await s.notebook(id);book.notes.sections[0].body='Una explicación con palabra singular arquitrabe.';
 await s.saveNotebook({session_id:id,expected_version:0,notes:book.notes});assert.equal((await s.notebooks('ARQUITRABE')).length,1);
 book.notes.sections[0].source_ids=['missing'];await assert.rejects(()=>s.saveNotebook({session_id:id,expected_version:1,notes:book.notes}));
 assert.equal((await s.notebook(id)).version,1);assert.equal((await s.notebooks('missing')).length,0);
});
test('backups preserve revised notebooks and restore older snapshots without notebooks',async()=>{
 const {s,id}=await setup(),book=await s.notebook(id);book.notes.open_questions=['¿Qué evidencia me falta?'];await s.saveNotebook({session_id:id,expected_version:0,notes:book.notes});
 const backup:any=await s.export(),target=new AcademyCloud(new TestD1() as any);await target.restore(backup);assert.deepEqual((await target.notebook(id)).notes,book.notes);
 const older=structuredClone(backup);delete older.tables.notebooks;const oldTarget=new AcademyCloud(new TestD1() as any);await oldTarget.restore(older);assert.equal((await oldTarget.notebook(id)).version,0);
 backup.tables.notebooks[0].data=JSON.stringify({...book.notes,sections:[{...book.notes.sections[0],source_ids:['missing']}]});const broken=new AcademyCloud(new TestD1() as any);await assert.rejects(()=>broken.restore(backup));assert.equal((await broken.sessions()).length,0);
});
test('multiple scoped exercises record independent attempts and FSRS schedules',async()=>{
 const {s,id}=await setup(),book=await s.notebook(id);const answered=book.tasks.slice(0,3);
 for(const [i,t] of answered.entries()){
  await s.submitAnswer({task_id:t.id,attempt_id:'study-'+i,answer:'Respuesta de práctica '+i,assisted:false,expected_version:0});
  await s.recordReview({attempt_id:'study-'+i,score:i===0?2:3,errors:i===0?'Me falta justificar':'',confirmed:true});
 }
 const after=await s.notebook(id);assert.equal(after.tasks.filter((t:any)=>t.version===1).length,3);assert.equal(after.tasks.filter((t:any)=>t.version===0).length,4);assert.equal((await s.dashboard()).reviews,3);assert.equal((await s.dashboard()).demonstrated,0);
});
test('MCP supports reading and writing structured notebooks with validated arguments',async()=>{
 const {s,id}=await setup(),books=await executeTool(s,'search_notebooks',{query:'lógica'}) as any;assert.equal(books.length,1);
 const book=await executeTool(s,'get_notebook',{session_id:id}) as any;book.notes.objectives=['Explicar con mis palabras'];
 assert.equal((await executeTool(s,'save_notebook',{session_id:id,expected_version:0,notes:book.notes}) as any).version,1);
 await assert.rejects(()=>executeTool(s,'save_notebook',{session_id:id,notes:book.notes}),/Argumentos/);
});
test('downloadable notes include objectives, references and provenance without inventing links',async()=>{
 const {s,id}=await setup(),book=await s.notebook(id),md=notebookMarkdown(book,book.notes);
 for(const expected of [book.title,book.notes.sections[0].body,book.sources[0].title,book.external_id,'no implican verificación externa'])assert.ok(md.includes(expected));
});
