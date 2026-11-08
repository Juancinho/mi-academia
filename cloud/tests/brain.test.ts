import {test} from 'node:test';
import assert from 'node:assert/strict';
import {DatabaseSync} from 'node:sqlite';
import {readFileSync,readdirSync} from 'node:fs';
import {AcademyCloud} from '../lib/academy-service.ts';
import {parseChatGPTExport} from '../lib/conversation-contract.ts';
import {noteCoverage} from '../lib/brain-service.ts';
import {graphNeighbors,layoutGraph} from '../lib/graph-layout.ts';
import {requirePrivateBridge} from '../lib/private-bridge.ts';
import example from '../lib/example-session.json' with {type:'json'};
class TestD1{
 db=new DatabaseSync(':memory:');
 constructor(){this.db.exec('PRAGMA foreign_keys=ON');for(const file of readdirSync(new URL('../drizzle/',import.meta.url)).filter(f=>f.endsWith('.sql')).sort())this.db.exec(readFileSync(new URL('../drizzle/'+file,import.meta.url),'utf8'));}
 prepare(sql:string){let args:any[]=[];const db=this.db;const stmt={bind(...v:any[]){args=v;return stmt;},async first(){return db.prepare(sql).get(...args)||null;},async all(){return {results:db.prepare(sql).all(...args)};},async run(){return {meta:{changes:Number(db.prepare(sql).run(...args).changes)}};},_sql:sql,_args:()=>args};return stmt;}
 async batch(statements:any[]){this.db.exec('BEGIN');try{const r=statements.map(s=>({results:this.db.prepare(s._sql).all(...s._args())}));this.db.exec('COMMIT');return r;}catch(e){this.db.exec('ROLLBACK');throw e;}}
}
const service=()=>new AcademyCloud(new TestD1() as any);
const chat=(id='test')=>({id,title:'Conversación de física',coverage:'provided',messages:[{id:'1',role:'user',text:'¿Qué es la energía?'},{id:'2',role:'assistant',text:'La energía se conserva. La potencia es energía por unidad de tiempo.'}],updated_at:'2026-11-08T10:00:00Z'});
function exportChat(){const msg=(id:string,role:string,text:string)=>({id,author:{role},create_time:10,content:{parts:[text]}});return {id:'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',title:'Ramas',current_node:'chosen',mapping:{root:{parent:null,children:['question'],message:null},question:{parent:'root',children:['old','chosen'],message:msg('q','user','Pregunta')},old:{parent:'question',children:[],message:msg('old','assistant','Respuesta descartada')},chosen:{parent:'question',children:[],message:msg('new','assistant','Respuesta activa')}}};}
test('export parser retains the active branch in chronological order and excludes discarded drafts',()=>{
 const result=parseChatGPTExport([exportChat()]);assert.deepEqual(result.conversations[0].messages.map(m=>m.text),['Pregunta','Respuesta activa']);assert.equal(result.conversations[0].coverage,'active_branch');assert.match(result.conversations[0].url!,/^https:\/\/chatgpt.com\/c\//);
});
test('export parser reports attachments, missing branch pointers and corrupt cycles',()=>{
 const c:any=exportChat();delete c.current_node;assert.ok(parseChatGPTExport(c).warnings.length);
 c.current_node='chosen';c.mapping.chosen.parent='chosen';assert.throws(()=>parseChatGPTExport(c),/ciclo/);
 const d:any=exportChat();d.mapping.chosen.message.content.parts=[{asset_pointer:'private'}];const parsed=parseChatGPTExport(d);assert.equal(parsed.conversations[0].messages.length,1);assert.ok(parsed.warnings.length);
});
test('conversation indexing validates the complete batch before mutation',async()=>{
 const s=service(),a=chat(),b={...chat('second'),url:'javascript:alert(1)'};await assert.rejects(()=>s.indexConversations({conversations:[a,b]}));assert.equal((await s.conversations()).total,0);
 await assert.rejects(()=>s.indexConversations({conversations:[{...a,messages:[...a.messages,a.messages[0]]}]}));assert.equal((await s.conversations()).total,0);
});
test('full-text search supports accents, prefixes, pagination and hostile query syntax safely',async()=>{
 const s=service();await s.indexConversations({conversations:[chat(),chat('second')]});assert.equal((await s.conversations('fisica energ')).total,2);assert.equal((await s.conversations('energía')).items.length,2);assert.equal((await s.conversations('',1)).items.length,1);assert.equal((await s.conversations('" OR 1=1 --')).total,0);
});
test('conversation reimport is idempotent and preserves earlier revisions when updated',async()=>{
 const s=service(),c=chat();assert.equal((await s.indexConversations({conversations:[c]})).created,1);assert.equal((await s.indexConversations({conversations:[c]})).skipped,1);
 c.messages[1].text+=' Ejemplo ampliado.';c.updated_at='2026-11-08T11:00:00Z';assert.equal((await s.indexConversations({conversations:[c]})).updated,1);assert.equal((await s.conversation(c.id)).revision,2);assert.equal((await s.rows('SELECT * FROM conversation_versions')).length,2);
 const result=await s.indexConversations({conversations:[chat()]});assert.equal(result.complete,false);assert.equal((await s.conversation(c.id)).revision,2);
});
test('existing study sessions are linked idempotently with truthful source coverage',async()=>{
 const s=service();await s.import(example);const records=await s.conversations();assert.equal(records.total,1);assert.equal(records.items[0].coverage,'provided');assert.equal((await s.indexExisting()).created,0);
 const book=await s.notebook((await s.sessions())[0].id);assert.equal(book.conversation_ids.length,1);
 const p=structuredClone(example);p.sessions[0].external_id='no-original';p.sessions[0].original_text='';await s.import(p);assert.ok((await s.conversations()).items.some(c=>c.coverage==='extracts'));
});
test('a conversation can link multiple notebooks without resetting learning states',async()=>{
 const s=service();await s.import(example);const sid=(await s.sessions())[0].id,c={...chat(),session_ids:[sid]};const before=await s.rows('SELECT card,version FROM tasks');await s.indexConversations({conversations:[c]});assert.ok((await s.notebook(sid)).conversation_ids.includes(c.id));assert.deepEqual(await s.rows('SELECT card,version FROM tasks'),before);
});
test('backups restore conversations, revision history, links and full-text index',async()=>{
 const s=service();await s.import(example);await s.indexConversations({conversations:[chat()]});const backup=await s.export(),target=service();await target.restore(backup);assert.equal((await target.conversations('fisica')).total,1);assert.equal((await target.conversations()).total,2);assert.deepEqual((await target.export() as any).tables,(backup as any).tables);
});
test('graph distinguishes explicit knowledge relations from notebook provenance',async()=>{
 const s=service();await s.import(example);const graph=await s.graph();assert.equal(graph.nodes.length,5);assert.equal(graph.edges.filter(e=>e.type==='explicit').length,2);assert.equal(graph.edges.filter(e=>e.type==='provenance').length,4);assert.ok(graph.edges.every(e=>graph.nodes.some(n=>n.id===e.source)&&graph.nodes.some(n=>n.id===e.target)));
 const pos=layoutGraph(graph.nodes,graph.edges);assert.ok(Object.values(pos).every(p=>Number.isFinite(p.x)&&Number.isFinite(p.y)));const first=graph.edges[0];assert.ok(graphNeighbors(first.source,graph.edges,1).has(first.target));
});
test('vault export includes current notes and source messages but no access credentials',async()=>{
 const s=service();await s.import(example);const snapshot=await s.vaultSnapshot();assert.equal(snapshot.format,'mi-academia-vault');assert.equal(snapshot.notebooks.length,1);assert.equal(snapshot.conversations.length,1);assert.equal(snapshot.knowledge.length,4);assert.ok(!JSON.stringify(snapshot).includes('Bearer '));assert.ok(snapshot.notebooks[0].notes.sections.length);
});
test('study coverage is an explicit structural signal and not a correctness or mastery grade',()=>{
 const coverage=noteCoverage({sections:[{body:'Short note',kind:'explicacion'}],objectives:[],glossary:[]});assert.equal(coverage.label,'Desarrollo inicial');assert.match(coverage.notice,/no evalúan exactitud/);
});
test('private bridge rejects alternate hosts and never turns a service credential into visitor identity',()=>{
 assert.throws(()=>requirePrivateBridge(new Request('https://other.example/api/vault-sync')));
 assert.throws(()=>requirePrivateBridge(new Request('http://localhost/api/vault-sync')));
 assert.doesNotThrow(()=>requirePrivateBridge(new Request('http://localhost/api/vault-sync',{headers:{'oai-authenticated-user-id':'local'}})));
});
