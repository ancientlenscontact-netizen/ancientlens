from typing import Literal
from fastapi import APIRouter, HTTPException, Depends, Request, Response, Query
from pydantic import BaseModel, ConfigDict, Field
from app.data.contributions import Contributions, NewDraft, Revision, Conflict, Evidence
from app.api.auth import Auth
from app.data.reports import Reports
from app.data.removals import Removals
from app.data.quotas import QuotaExceeded

class LibraryChange(BaseModel):
    model_config=ConfigDict(extra="forbid")
    notes:str=Field(default="",max_length=4000)
    version:int=Field(ge=0,strict=True)
    remove:bool=Field(default=False,strict=True)

class Moderation(BaseModel):
    model_config=ConfigDict(extra='forbid')
    revision: int=Field(ge=1,strict=True)
    base_event: int=Field(ge=0,strict=True)
    action: Literal['allowed','changes_requested','hidden']
    reason: Evidence

class Report(BaseModel):
    model_config=ConfigDict(extra='forbid')
    revision:int=Field(ge=1,strict=True)
    reason:Evidence

class Resolution(BaseModel):
    model_config=ConfigDict(extra='forbid')
    outcome:Literal['action_taken','dismissed']
    reason:Evidence

def contribution_router(path):
    repository=Contributions(path)
    auth=Auth(path)
    reports=Reports(path)
    router=APIRouter()
    router.include_router(auth.router())

    @router.get('/api/catalog/passages')
    def passages(): return repository.passages()

    @router.get('/api/contributions')
    def contributions(passage_id:str,request:Request,response:Response,limit:int=Query(10,ge=1,le=10),offset:int=Query(0,ge=0,le=100000)):
        response.headers['Cache-Control']='no-store'
        return repository.list(passage_id,auth.optional(request),limit,offset)

    def execute(operation):
        try: return operation()
        except QuotaExceeded as error: raise HTTPException(429,str(error),headers={'Retry-After':'3600'})
        except KeyError as error: raise HTTPException(404,error.args[0])
        except Conflict as error: raise HTTPException(409,str(error))
        except PermissionError as error: raise HTTPException(403,str(error))

    from app.data.library import Library
    library=Library(path)

    @router.get('/api/library')
    def saved_items(response:Response,user=Depends(auth.required)):
        response.headers['Cache-Control']='no-store'
        return library.list(user)

    @router.get('/api/library/{artifact}')
    def saved_item(artifact:str,response:Response,user=Depends(auth.required)):
        response.headers['Cache-Control']='no-store'
        return execute(lambda:library.get(user,artifact))

    @router.put('/api/library/{artifact}',dependencies=[Depends(auth.origin)])
    def save_item(artifact:str,data:LibraryChange,response:Response,user=Depends(auth.required)):
        response.headers['Cache-Control']='no-store'
        return execute(lambda:library.save(user,artifact,data.notes,data.version,data.remove))

    @router.post('/api/contributions',status_code=201,dependencies=[Depends(auth.origin)])
    def create(draft:NewDraft,user=Depends(auth.required)):
        return execute(lambda:repository.save(draft,user=user))

    @router.post('/api/contributions/{id}/revisions',status_code=201,dependencies=[Depends(auth.origin)])
    def revise(id:str,draft:Revision,user=Depends(auth.required)):
        return execute(lambda:repository.save(draft,id,user))

    @router.post('/api/contributions/{id}/moderation',status_code=201,dependencies=[Depends(auth.origin)])
    def moderate(id:str,data:Moderation,user=Depends(auth.required)):
        return execute(lambda:repository.moderate(id,data.revision,data.action,data.reason,user,data.base_event))

    @router.post('/api/contributions/{id}/reports',status_code=201,dependencies=[Depends(auth.origin)])
    def report(id:str,data:Report,user=Depends(auth.required)):
        return execute(lambda:reports.submit(id,data.revision,data.reason,user))

    @router.post('/api/contributions/{id}/withdraw',dependencies=[Depends(auth.origin)])
    def withdraw(id:str,user=Depends(auth.required)):
        return execute(lambda:Removals(path).request(user,id))

    @router.get('/api/removal-requests')
    def removals(response:Response,after:int=Query(0,ge=0),user=Depends(auth.required)):
        response.headers['Cache-Control']='no-store'
        return execute(lambda:Removals(path).list(user,after))

    @router.get('/api/reports')
    def report_queue(response:Response,after:int=Query(0,ge=0),user=Depends(auth.required)):
        response.headers['Cache-Control']='no-store'
        return execute(lambda:reports.list(user,after))

    @router.post('/api/reports/{id}/resolve',dependencies=[Depends(auth.origin)])
    def resolve_report(id:int,data:Resolution,user=Depends(auth.required)):
        return execute(lambda:reports.resolve(id,data.outcome,data.reason,user))

    return router
