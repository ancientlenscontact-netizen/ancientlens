"""Bound request bytes before JSON or multipart parsing, including chunked bodies."""
import asyncio
from starlette.responses import JSONResponse

class BodyLimit:
    def __init__(self,app,image_inspector=False):
        self.app=app
        self.image_inspector=image_inspector

    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or scope['method'] not in ('POST','PUT','PATCH'):
            return await self.app(scope,receive,send)
        limit=11*1024*1024 if self.image_inspector and scope['path']=='/api/inscriptions' else 256*1024
        headers=dict(scope.get('headers',[]))
        try:
            if b'content-length' in headers and int(headers[b'content-length'])>limit:
                return await JSONResponse({'detail':'Request body exceeds service limit'},status_code=413)(scope,receive,send)
        except ValueError:
            return await JSONResponse({'detail':'Invalid content length'},status_code=400)(scope,receive,send)
        async def read_body():
            chunks=[];size=0
            while True:
                message=await receive()
                if message['type']=='http.disconnect': return None
                chunk=message.get('body',b'');size+=len(chunk)
                if size>limit: raise OverflowError
                chunks.append(chunk)
                if not message.get('more_body',False): return b''.join(chunks)
        try: body=await asyncio.wait_for(read_body(),timeout=15)
        except OverflowError:
            return await JSONResponse({'detail':'Request body exceeds service limit'},status_code=413)(scope,receive,send)
        except asyncio.TimeoutError:
            return await JSONResponse({'detail':'Request body timed out'},status_code=408)(scope,receive,send)
        if body is None: return
        delivered=False
        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered=True
                return {'type':'http.request','body':body,'more_body':False}
            return await receive()
        await self.app(scope,bounded_receive,send)
