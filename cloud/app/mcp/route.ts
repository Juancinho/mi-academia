import {env} from 'cloudflare:workers';
import {handleMcp} from '../../lib/academy-mcp';
import {AcademyCloud} from '../../lib/academy-service';
export const dynamic='force-dynamic';
export async function POST(request:Request){return handleMcp(request,()=>{if(!env.DB)throw new Error('DB no disponible.');return new AcademyCloud(env.DB);});}
