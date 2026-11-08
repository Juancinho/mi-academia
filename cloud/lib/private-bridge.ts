import {AcademyError} from './academy-contract.ts';
/** Sites dispatch enforces this project's sole-owner policy before requests reach this route.
 * Service tokens are validated/consumed by Sites and carry no visitor identity.
 * NEVER make this Site public or shared while this bridge is enabled.
 */
export function requirePrivateBridge(request:Request){
 const host=new URL(request.url).hostname;
 if(host!=='mi-academia-juancinho.juan-el-g.chatgpt.site'&&!(request.headers.get('oai-authenticated-user-id')&&['localhost','127.0.0.1'].includes(host)))throw new AcademyError('Puente disponible solo en el sitio privado del propietario.',403);
}
