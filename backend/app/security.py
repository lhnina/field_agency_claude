from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Perfil, User

oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_password(pw: str, hashed: str) -> bool:
    return bcrypt.checkpw(pw.encode(), hashed.encode())


def create_token(user: User) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expires_minutes)
    payload = {"sub": str(user.id), "tid": user.tenant_id, "perfil": user.perfil.value, "exp": exp}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def current_user(token: str = Depends(oauth2), db: Session = Depends(get_db)) -> User:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sessão inválida ou expirada")
    user = db.get(User, int(payload["sub"]))
    if not user or not user.ativo:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Utilizador inativo")
    return user


# Permissões por perfil e operação (MVP). O âmbito de dados do supervisor
# (só a sua equipa) é aplicado nas consultas, não aqui.
PERMISSOES: dict[str, set[Perfil]] = {
    "dados_mestre.ler": set(Perfil) - {Perfil.colaborador},
    "dados_mestre.editar": {Perfil.administrador, Perfil.gestor},
    "colaboradores.ler": {Perfil.administrador, Perfil.direcao, Perfil.gestor, Perfil.supervisor, Perfil.rh},
    "colaboradores.editar": {Perfil.administrador, Perfil.gestor, Perfil.rh},
    "contratos.ler": {Perfil.administrador, Perfil.direcao, Perfil.gestor, Perfil.financeiro, Perfil.supervisor},
    "contratos.editar": {Perfil.administrador, Perfil.gestor},
    "planeamento.ler": {Perfil.administrador, Perfil.direcao, Perfil.gestor, Perfil.supervisor},
    "planeamento.editar": {Perfil.administrador, Perfil.gestor, Perfil.supervisor},
    "ausencias.editar": {Perfil.administrador, Perfil.gestor, Perfil.supervisor, Perfil.rh},
}


def requer(permissao: str):
    perfis = PERMISSOES[permissao]

    def dep(user: User = Depends(current_user)) -> User:
        if user.perfil not in perfis:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Sem permissão para esta operação")
        return user

    return dep
