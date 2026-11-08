import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

// Hidden terminal input, as used by the Sites source helper. Secrets never enter argv.
const token=await new Promise((resolve,reject)=>{
 let value='';const terminal=process.stdin.isTTY;
 const finish=(error)=>{process.stdin.removeListener('data',onData);process.stdin.removeListener('end',onEnd);if(terminal)process.stdin.setRawMode(false);process.stdin.pause();error?reject(error):resolve(value.trim());};
 const onData=chunk=>{value+=chunk;if(value.includes('\u0003'))finish(new Error('Configuración cancelada.'));else if(value.length>65536)finish(new Error('Entrada demasiado grande.'));else if(/[\r\n]/.test(value))finish();};
 const onEnd=()=>finish();
 if(terminal)process.stdin.setRawMode(true);
 process.stderr.write('Ready for private service credential on stdin (input is hidden).\n');
 process.stdin.setEncoding('utf8');process.stdin.on('data',onData);process.stdin.once('end',onEnd);process.stdin.resume();
});
if(!token||/[\r\n\0]/.test(token))throw new Error('Credencial inválida.');
const project=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const child=spawn(path.join(project,'.venv','Scripts','python.exe'),['-m','academia.install_sync','--vault',process.argv[2]||''],{cwd:project,windowsHide:true,stdio:['pipe','inherit','inherit']});
child.stdin.end(token+'\n');
child.once('error',()=>{process.exitCode=1;});
child.once('exit',code=>{process.exitCode=code||0;});
