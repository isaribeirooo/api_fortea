import os
from datetime import date, timedelta
from typing import Literal, Optional

import pymysql
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field


API_KEY = os.getenv("TEAFOR_API_KEY")


def exigir_chave(x_api_key: Optional[str] = Header(default=None)):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(401, "Chave da API inválida")


app = FastAPI(title="API ForTEA", dependencies=[Depends(exigir_chave)])


def get_conn():
    return pymysql.connect(
        host="localhost",
        user="root",
        password="",
        database="fortea",
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


@app.get("/")
def raiz():
    return {"mensagem": "API ForTEA funcionando. Veja /docs"}




CAMPOS = [
    "nome", "especialidade", "descricao", "telefone", "whatsapp",
    "endereco", "site", "convenios", "atendimento", "valor_consulta",
    "foto", "ativo",
]


class ProfissionalIn(BaseModel):
    nome: str
    especialidade: Optional[str] = None
    descricao: Optional[str] = None
    telefone: Optional[str] = None
    whatsapp: Optional[str] = None
    endereco: Optional[str] = None
    site: Optional[str] = None
    convenios: Optional[str] = None
    atendimento: Optional[str] = None
    valor_consulta: Optional[str] = None
    foto: Optional[str] = None
    ativo: int = 1


@app.get("/profissionais")
def listar():
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM profissionais ORDER BY nome")
            return cur.fetchall()
    finally:
        conn.close()


@app.get("/profissionais/{id}")
def visualizar(id: int):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM profissionais WHERE id = %s", (id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(404, "Profissional não encontrado")
            return row
    finally:
        conn.close()


@app.post("/profissionais", status_code=201)
def cadastrar(p: ProfissionalIn):
    dados = p.model_dump()
    colunas = ", ".join(CAMPOS)
    marcadores = ", ".join(["%s"] * len(CAMPOS))
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO profissionais ({colunas}) VALUES ({marcadores})",
                [dados[c] for c in CAMPOS],
            )
            conn.commit()
            return {"id": cur.lastrowid, **dados}
    finally:
        conn.close()


@app.put("/profissionais/{id}")
def editar(id: int, p: ProfissionalIn):
    dados = p.model_dump()
    sets = ", ".join(f"{c} = %s" for c in CAMPOS)
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE profissionais SET {sets} WHERE id = %s",
                [dados[c] for c in CAMPOS] + [id],
            )
            conn.commit()
            return {"id": id, **dados}
    finally:
        conn.close()


@app.delete("/profissionais/{id}")
def excluir(id: int):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM profissionais WHERE id = %s", (id,))
            conn.commit()
            if cur.rowcount == 0:
                raise HTTPException(404, "Profissional não encontrado")
            return {"mensagem": "Excluído com sucesso"}
    finally:
        conn.close()



def limpar(linha):
    """Converte o campo TIME do MySQL (timedelta) em texto 'HH:MM'."""
    if linha:
        for chave, valor in linha.items():
            if isinstance(valor, timedelta):
                s = int(valor.total_seconds())
                linha[chave] = f"{s // 3600:02d}:{s % 3600 // 60:02d}"
    return linha


def tratar_integridade(e: pymysql.err.IntegrityError):
    codigo = e.args[0] if e.args else 0
    if codigo == 1062:
        raise HTTPException(409, "Já existe um registro com esses dados")
    if codigo == 1452:
        raise HTTPException(400, "Referência inválida: o usuário/rotina/checklist informado não existe")
    raise HTTPException(400, "Dados não permitidos pelo banco")


def registrar_crud(rota, tabela, Modelo, ordem, filtros=()):
    """
    Cria as 5 rotas padrão (listar, ver, cadastrar, editar, excluir) para uma tabela
    que tem coluna 'id'. Os campos vêm do próprio Modelo.
    'filtros' são colunas que podem ser usadas na listagem: /rotina_itens?rotina_id=3
    """
    campos = list(Modelo.model_fields)
    colunas = ", ".join(campos)
    marcadores = ", ".join(["%s"] * len(campos))
    sets = ", ".join(f"{c} = %s" for c in campos)

    @app.get(f"/{rota}", name=f"listar_{rota}",
             description=f"Filtros opcionais na URL: {', '.join(filtros) or 'nenhum'}")
    def listar_todos(request: Request):
        where, params = [], []
        for f in filtros:
            v = request.query_params.get(f)
            if v is not None:
                where.append(f"{f} = %s")
                params.append(v)
        sql = f"SELECT * FROM {tabela}"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += f" ORDER BY {ordem}"
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return [limpar(r) for r in cur.fetchall()]
        finally:
            conn.close()

    @app.get(f"/{rota}/{{id}}", name=f"ver_{rota}")
    def ver_um(id: int):
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(f"SELECT * FROM {tabela} WHERE id = %s", (id,))
                row = cur.fetchone()
                if not row:
                    raise HTTPException(404, "Registro não encontrado")
                return limpar(row)
        finally:
            conn.close()

    @app.post(f"/{rota}", status_code=201, name=f"cadastrar_{rota}")
    def cadastrar_um(dados: Modelo):
        d = dados.model_dump()
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"INSERT INTO {tabela} ({colunas}) VALUES ({marcadores})",
                    [d[c] for c in campos],
                )
                conn.commit()
                return {"id": cur.lastrowid, **d}
        except pymysql.err.IntegrityError as e:
            tratar_integridade(e)
        finally:
            conn.close()

    @app.put(f"/{rota}/{{id}}", name=f"editar_{rota}")
    def editar_um(id: int, dados: Modelo):
        d = dados.model_dump()
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE {tabela} SET {sets} WHERE id = %s",
                    [d[c] for c in campos] + [id],
                )
                if cur.rowcount == 0:
                    # o MySQL também devolve 0 quando nada mudou; confere se existe
                    cur.execute(f"SELECT id FROM {tabela} WHERE id = %s", (id,))
                    if not cur.fetchone():
                        raise HTTPException(404, "Registro não encontrado")
                conn.commit()
                return {"id": id, **d}
        except pymysql.err.IntegrityError as e:
            tratar_integridade(e)
        finally:
            conn.close()

    @app.delete(f"/{rota}/{{id}}", name=f"excluir_{rota}")
    def excluir_um(id: int):
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(f"DELETE FROM {tabela} WHERE id = %s", (id,))
                conn.commit()
                if cur.rowcount == 0:
                    raise HTTPException(404, "Registro não encontrado")
                return {"mensagem": "Excluído com sucesso"}
        finally:
            conn.close()



class RotinaIn(BaseModel):
    usuario_id: int
    nome: str = Field(max_length=80)


class RotinaItemIn(BaseModel):
    rotina_id: int
    titulo: str = Field(max_length=60)
    emoji: Optional[str] = Field(default=None, max_length=8)
    imagem: Optional[str] = Field(default=None, max_length=80)
    horario: Optional[str] = Field(default=None, pattern=r"^\d{2}:\d{2}(:\d{2})?$")  # "08:30"
    ordem: int = 0


class AtividadePadraoIn(BaseModel):
    nome: str = Field(max_length=60)
    categoria: str = Field(max_length=30)
    emoji: str = Field(max_length=8)


class RotinaProgressoIn(BaseModel):
    item_id: int
    dia: date  # "2026-11-26"


registrar_crud("rotinas", "rotinas", RotinaIn, "id DESC", filtros=("usuario_id",))
registrar_crud("rotina_itens", "rotina_itens", RotinaItemIn, "rotina_id, ordem, id", filtros=("rotina_id",))
registrar_crud("atividades_padrao", "atividades_padrao", AtividadePadraoIn, "categoria, nome", filtros=("categoria",))


# rotina_progresso não tem coluna 'id' (a chave é item_id + dia), por isso é manual
@app.get("/rotina_progresso", description="Filtros opcionais na URL: item_id, dia")
def listar_progresso(request: Request):
    where, params = [], []
    for f in ("item_id", "dia"):
        v = request.query_params.get(f)
        if v is not None:
            where.append(f"{f} = %s")
            params.append(v)
    sql = "SELECT * FROM rotina_progresso"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY dia DESC, item_id"
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()
    finally:
        conn.close()


@app.post("/rotina_progresso", status_code=201)
def marcar_progresso(p: RotinaProgressoIn):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO rotina_progresso (item_id, dia) VALUES (%s, %s)",
                (p.item_id, p.dia),
            )
            conn.commit()
            return p.model_dump()
    except pymysql.err.IntegrityError as e:
        tratar_integridade(e)
    finally:
        conn.close()


@app.delete("/rotina_progresso/{item_id}/{dia}")
def desmarcar_progresso(item_id: int, dia: date):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM rotina_progresso WHERE item_id = %s AND dia = %s",
                (item_id, dia),
            )
            conn.commit()
            if cur.rowcount == 0:
                raise HTTPException(404, "Registro não encontrado")
            return {"mensagem": "Excluído com sucesso"}
    finally:
        conn.close()



class ChecklistJornadaIn(BaseModel):
    usuario_id: int  # cada usuário só pode ter 1 registro (chave única no banco)
    etapa_atual: str = Field(default="buscando_informacoes", max_length=60)


class ChecklistTarefaIn(BaseModel):
    usuario_id: int
    etapa: str = Field(max_length=60)
    titulo: str = Field(max_length=255)
    status: Literal["pendente", "concluido", "andamento", "ajuda", "nao_aplica"] = "pendente"
    personalizada: int = Field(default=0, ge=0, le=1)


registrar_crud("checklist_jornada", "checklist_jornada", ChecklistJornadaIn, "id", filtros=("usuario_id",))
registrar_crud("checklist_tarefas", "checklist_tarefas", ChecklistTarefaIn,
               "usuario_id, etapa, personalizada, id", filtros=("usuario_id", "etapa", "status"))



class TrajetoriaChecklistIn(BaseModel):
    usuario_id: int
    titulo: str = Field(max_length=100)
    descricao: Optional[str] = Field(default=None, max_length=255)
    icone: Optional[str] = Field(default=None, max_length=50)
    ordem: int = 0


class TrajetoriaItemIn(BaseModel):
    checklist_id: int
    etapa: str = Field(max_length=255)
    concluida: int = Field(default=0, ge=0, le=1)
    ordem: int = 0


class TrajetoriaRegistroIn(BaseModel):
    usuario_id: int
    titulo: str = Field(max_length=150)
    tipo: str = Field(max_length=50)
    data_registro: date  # "2026-11-26"
    profissional: Optional[str] = Field(default=None, max_length=150)
    local: Optional[str] = Field(default=None, max_length=150)
    descricao: Optional[str] = None
    foto: Optional[str] = Field(default=None, max_length=255)


registrar_crud("trajetoria_checklists", "trajetoria_checklists", TrajetoriaChecklistIn,
               "usuario_id, ordem, id", filtros=("usuario_id",))
registrar_crud("trajetoria_itens", "trajetoria_itens", TrajetoriaItemIn,
               "checklist_id, ordem, id", filtros=("checklist_id", "concluida"))
registrar_crud("trajetoria_registros", "trajetoria_registros", TrajetoriaRegistroIn,
               "data_registro DESC, id DESC", filtros=("usuario_id", "tipo"))