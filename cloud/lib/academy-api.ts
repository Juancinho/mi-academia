export async function academyApi(action:string,input?:any){
 const response=await fetch(input?'/api/academy':'/api/academy?'+action,{method:input?'POST':'GET',headers:input?{'Content-Type':'application/json'}:undefined,body:input?JSON.stringify({action,...input}):undefined,cache:'no-store'});
 const data:any=await response.json();if(!response.ok)throw new Error(data.error||'No se pudo completar la operación.');return data;
}
