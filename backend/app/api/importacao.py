from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Perfil, User, Zona
from app.security import current_user
from app.services import importacao as imp

router = APIRouter(prefix="/importacao", tags=["importação"])

PERFIS = {
    "clientes": {Perfil.administrador, Perfil.gestor},
    "lojas": {Perfil.administrador, Perfil.gestor, Perfil.gestor_conta},
    "contratos": {Perfil.administrador, Perfil.gestor},
    "colaboradores": {Perfil.administrador, Perfil.gestor, Perfil.rh},
}
MAX_BYTES = 10 * 1024 * 1024


def _check(tipo: str, user: User) -> None:
    if tipo not in imp.MODELOS:
        raise HTTPException(404, "Tipo de importação desconhecido")
    if user.perfil not in PERFIS[tipo]:
        raise HTTPException(403, "Sem permissão para importar este tipo de dados")


@router.get("/contagens")
def contagens(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return imp.contagens(db, user.tenant_id)


@router.get("/modelo/{tipo}")
def modelo(tipo: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    _check(tipo, user)
    zonas = db.scalars(select(Zona.nome).where(Zona.tenant_id == user.tenant_id).order_by(Zona.nome)).all()
    return Response(imp.modelo_xlsx(tipo, list(zonas)),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="modelo-{tipo}.xlsx"'})


@router.post("/{tipo}")
async def importar(tipo: str, confirmar: bool = False, ficheiro: UploadFile = File(...),
                   user: User = Depends(current_user), db: Session = Depends(get_db)):
    _check(tipo, user)
    conteudo = await ficheiro.read(MAX_BYTES + 1)
    if len(conteudo) > MAX_BYTES:
        raise HTTPException(413, "O ficheiro excede 10 MB")
    try:
        res = imp.importar(db, user, tipo, conteudo, confirmar)
    except ValueError as e:
        db.rollback()
        raise HTTPException(422, str(e))
    if confirmar:
        db.commit()
    else:
        db.rollback()
    return res
