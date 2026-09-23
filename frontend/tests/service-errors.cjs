// Compile Contributions.tsx as CommonJS into a temporary directory; see CURRENT_STATE.md.
const assert = require('node:assert/strict');
const path = require('node:path');
const {request} = require(path.resolve(process.argv[2], 'Contributions.js'));
(async () => {
 const original = global.fetch;
 try {
  for (const [status, body, type] of [[503,'Service Unavailable','text/plain'],[502,'<html>Bad gateway</html>','text/html'],[500,'{"detail":"internal diagnostics"}','application/json']]) {
   global.fetch = async () => new Response(body,{status,headers:{'Content-Type':type}});
   await assert.rejects(request('/api/catalog/passages'),{message:'The service is temporarily unavailable. Please try again shortly.'});
  }
  global.fetch = async () => new Response('{"detail":"Please sign in"}',{status:401});
  await assert.rejects(request('/api/contributions'),{message:'Please sign in'});
  global.fetch = async () => new Response('{"detail":[{"msg":"required"}]}',{status:422});
  await assert.rejects(request('/api/contributions'),{message:'Check the required fields and length limits.'});
  global.fetch = async () => new Response('not JSON',{status:200});
  await assert.rejects(request('/api/catalog/passages'),{message:'The service returned an unreadable response. Please try again shortly.'});
  global.fetch = async () => new Response('null',{status:200});
  assert.equal(await request('/api/auth/me'),null);
  global.fetch = async () => new Response('[{"id":"passage"}]',{status:200});
  assert.deepEqual(await request('/api/catalog/passages'),[{id:'passage'}]);
  console.log('PASS: 8 response cases (proxy outages, API errors, invalid JSON, guest and catalog success)');
 } finally {global.fetch=original;}
})().catch(e=>{console.error(e);process.exitCode=1;});
