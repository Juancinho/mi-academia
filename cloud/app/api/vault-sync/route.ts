import {env} from 'cloudflare:workers';
import {AcademyCloud} from '../../../lib/academy-service';
import {requirePrivateBridge} from '../../../lib/private-bridge';
import {assertSameOrigin} from '../../../lib/academy-contract';
export const dynamic='force-dynamic';
export async function GET(request:Request){
 try{requirePrivateBridge(request);if(!env.DB)throw new Error("DB no disponible");return Response.json(await new AcademyCloud(env.DB).vaultSnapshot(),{headers:{'Cache-Control':'no-store'}});}catch{return Response.json({error:'No se pudo obtener la copia privada.'},{status:403});}
}
export async function POST(request:Request){
 try{requirePrivateBridge(request);if(!env.DB)throw new Error("DB no disponible");if(request.headers.get('origin'))assertSameOrigin(request);
  return Response.json(await new AcademyCloud(env.DB).indexExisting(),{headers:{'Cache-Control':'no-store'}});
 }catch{return Response.json({error:'No se pudo indexar el material existente.'},{status:403});}
}
