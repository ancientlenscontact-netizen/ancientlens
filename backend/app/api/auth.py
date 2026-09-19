import os
from typing import Annotated
from fastapi import APIRouter, HTTPException, Request, Response, Depends
from pydantic import BaseModel, ConfigDict, StringConstraints
from app.data.removals import Removals
from app.data.accounts import Accounts, RateLimited, SESSION_SECONDS

COOKIE='ancientlens_session'

class Credentials(BaseModel):
    model_config=ConfigDict(extra='forbid')
    username: Annotated[str, StringConstraints(strip_whitespace=True,to_lower=True,pattern=r'^[a-z0-9_]{3,40}$')]
    password: Annotated[str, StringConstraints(min_length=15,max_length=128)]

class Recovery(Credentials):
    recovery_code: Annotated[str,StringConstraints(min_length=64,max_length=64,pattern=r'^[a-f0-9]{64}$')]

class RecoveryIssue(BaseModel):
    model_config=ConfigDict(extra='forbid')
    password: Annotated[str,StringConstraints(min_length=15,max_length=128)]

class Auth:
    def __init__(self,path):
        self.accounts=Accounts(path)
        self.origins=set(os.environ.get('ANCIENTLENS_ALLOWED_ORIGINS','http://127.0.0.1:5173,http://localhost:5173').split(','))
        self.secure=os.environ.get('ANCIENTLENS_SECURE_COOKIES','0')=='1'

    def origin(self,request:Request):
        if request.headers.get('origin') not in self.origins:
            raise HTTPException(403,'Request origin is not allowed')

    def optional(self,request:Request):
        return self.accounts.user(request.cookies.get(COOKIE))

    def required(self,request:Request):
        user=self.optional(request)
        if user is None: raise HTTPException(401,'Sign in to continue')
        return user

    def limit(self,request:Request,username):
        try:
            self.accounts.throttle('client:'+(request.client.host if request.client else 'unknown'),40)
            self.accounts.throttle('account:'+username,10)
        except RateLimited:
            raise HTTPException(429,'Too many attempts. Try again in 15 minutes.')

    def set_session(self,request,response,user):
        self.accounts.logout(request.cookies.get(COOKIE))
        try: token=self.accounts.session(user['id'],user.get('credential_version'))
        except ValueError: raise HTTPException(401,'Account is closed')
        response.set_cookie(COOKIE,token,max_age=SESSION_SECONDS,httponly=True,secure=self.secure,samesite='strict',path='/api')
        response.headers['Cache-Control']='no-store'
        return {key:user[key] for key in ('id','username','role')}

    def router(self):
        router=APIRouter(prefix='/api/auth')

        @router.get('/me')
        def me(request:Request,response:Response):
            response.headers['Cache-Control']='no-store'
            return self.optional(request)

        @router.post('/register',status_code=201,dependencies=[Depends(self.origin)])
        def register(data:Credentials,request:Request,response:Response):
            self.limit(request,data.username)
            try: user=self.accounts.register(data.username,data.password)
            except ValueError as error: raise HTTPException(409,str(error))
            result=self.set_session(request,response,user)
            return {**result,'recovery_code':self.accounts.issue_recovery(user['id'])}

        @router.post('/login',dependencies=[Depends(self.origin)])
        def login(data:Credentials,request:Request,response:Response):
            self.limit(request,data.username)
            user=self.accounts.login(data.username,data.password)
            if user is None: raise HTTPException(401,'Invalid username or password')
            return self.set_session(request,response,user)

        @router.post('/recovery-code',dependencies=[Depends(self.origin)])
        def recovery_code(data:RecoveryIssue,request:Request,response:Response,user=Depends(self.required)):
            self.limit(request,user['username'])
            checked=self.accounts.login(user['username'],data.password)
            if not checked: raise HTTPException(401,'Invalid password')
            response.headers['Cache-Control']='no-store'
            try: code=self.accounts.issue_recovery(user['id'],checked['credential_version'])
            except ValueError: raise HTTPException(401,'Password changed; sign in again')
            return {'recovery_code':code}

        @router.post('/recover',dependencies=[Depends(self.origin)])
        def recover(data:Recovery,request:Request,response:Response):
            self.limit(request,data.username)
            code=self.accounts.recover(data.username,data.recovery_code,data.password)
            if code is None: raise HTTPException(401,'Invalid username or recovery code')
            self.accounts.logout(request.cookies.get(COOKIE))
            response.delete_cookie(COOKIE,path='/api',httponly=True,secure=self.secure,samesite='strict')
            response.headers['Cache-Control']='no-store'
            return {'status':'password_reset','recovery_code':code}

        @router.post('/close',dependencies=[Depends(self.origin)])
        def close(data:RecoveryIssue,request:Request,response:Response,user=Depends(self.required)):
            self.limit(request,user['username'])
            checked=self.accounts.login(user['username'],data.password)
            if not checked: raise HTTPException(401,'Invalid password')
            try: result=Removals(self.accounts.path).request(user,credential_version=checked['credential_version'])
            except PermissionError as error: raise HTTPException(403,str(error))
            response.delete_cookie(COOKIE,path='/api',httponly=True,secure=self.secure,samesite='strict')
            response.headers['Cache-Control']='no-store'
            return result

        @router.post('/logout',dependencies=[Depends(self.origin)])
        def logout(request:Request,response:Response):
            self.accounts.logout(request.cookies.get(COOKIE))
            response.delete_cookie(COOKIE,path='/api',httponly=True,secure=self.secure,samesite='strict')
            response.headers['Cache-Control']='no-store'
            return {'status':'signed_out'}

        return router
