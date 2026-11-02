import fs from 'node:fs';
import Ajv from 'ajv';
import standaloneCode from 'ajv/dist/standalone/index.js';
import {TOOLS} from '../lib/academy-tools.ts';
const ajv=new Ajv({allErrors:true,strict:false,useDefaults:true,validateFormats:false,code:{source:true,esm:true}});
const names={};
for(const tool of TOOLS){if(tool.name==='import_session')continue;const name=tool.name==='preview_import'?'validate_import':'validate_'+tool.name;ajv.addSchema(tool.inputSchema,name);names[name]=name;}
let code=standaloneCode(ajv,names);
const imports=[];
code=code.replace(/const (\w+) = require\("([^\"]+)"\)\.default;/g,(_,name,path)=>{const local='import_'+name;imports.push(`import ${local} from ${JSON.stringify(path+'.js')};\nconst ${name}=${local}.default??${local};`);return '';});
if(code.includes('require('))throw new Error('Generated validators contain an unsupported runtime require.');
fs.writeFileSync('lib/generated-validators.mjs',imports.join('\n')+'\n'+code+'\n');
fs.writeFileSync('lib/generated-validators.d.mts',Object.keys(names).map(name=>`export const ${name}: { (value:any): boolean; errors?: any };`).join('\n')+'\n');
console.log('Generated standalone validators; no runtime code generation.');
