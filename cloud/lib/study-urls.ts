/** Notes cannot load remote images or execute application schemes. */
export function safeStudyUrl(url:string){
 if(url.startsWith('#'))return url;
 try{const value=new URL(url);return ['https:','http:'].includes(value.protocol)&&!value.username&&!value.password?url:'';}catch{return '';}
}
